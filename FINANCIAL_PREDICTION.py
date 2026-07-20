import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt

from utils import (
    create_db, login_page, load_models,
    get_technical_indicators, predict_next_day,
    add_to_watchlist, get_watchlist, get_currency_symbol,
    validate_ticker, get_stock_history, get_or_train_model,
    resolve_ticker, render_ticker_picker
)

st.set_page_config(page_title="AI/ML Finance Market Predictor", page_icon="📈", layout="wide")

create_db()

if "user" not in st.session_state:
    st.session_state["user"] = None

if st.session_state["user"] is None:
    login_page()
    st.stop()
else:
    st.sidebar.write(f"Logged in as: {st.session_state['user']}")
    if st.sidebar.button("Logout"):
        st.session_state["user"] = None
        st.rerun()

all_models = load_models()
trained_tickers = list(all_models.keys()) if all_models else []

st.title("AI/ML Finance Market Predictor")

selected_stock = render_ticker_picker("ticker_input", curated_tickers=trained_tickers or None)
st.caption("Any ticker not in the curated list gets an on-demand model, trained in a few seconds and then cached.")

if selected_stock:
    if not validate_ticker(selected_stock):
        suggestions = resolve_ticker(selected_stock)
        if suggestions:
            st.error(f"Couldn't find data for '{selected_stock}'. Did you mean one of these?")
            cols = st.columns(min(len(suggestions), 5))
            for i, match in enumerate(suggestions[:5]):
                label = f"{match['symbol']} — {match['name']}"
                if cols[i].button(label, key=f"suggest_{match['symbol']}"):
                    st.session_state["ticker_input"] = match["symbol"]
                    st.rerun()
        else:
            st.error(f"Couldn't find data for '{selected_stock}'. Check the ticker symbol (Yahoo Finance format).")
        st.stop()

    stock = yf.Ticker(selected_stock)
    try:
        info = stock.info
        col1, col2 = st.columns([3, 1])

        with col1:
            st.subheader(f"{info.get('shortName', selected_stock)}")
            hist = get_stock_history(selected_stock, period="1y")

            if not hist.empty and len(hist) >= 2:
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.plot(hist.index, hist['Close'], label='Close Price')
                ax.set_title(f"{selected_stock} Stock Price (Last Year)")
                ax.set_xlabel("Date")
                ax.set_ylabel("Price")
                ax.legend()
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)

                st.write("### Recent Price Information")
                last_price = hist['Close'].iloc[-1]
                price_change = hist['Close'].iloc[-1] - hist['Close'].iloc[-2]
                price_change_pct = (price_change / hist['Close'].iloc[-2]) * 100

                currency_symbol = get_currency_symbol(selected_stock)

                col_price1, col_price2, col_price3 = st.columns(3)
                col_price1.metric("Last Close Price", f"{currency_symbol}{last_price:.2f}")
                col_price2.metric("Change", f"{currency_symbol}{price_change:.2f}", f"{price_change_pct:.2f}%")
                col_price3.metric("Volume", f"{hist['Volume'].iloc[-1]:,.0f}")

                spinner_msg = (
                    "Generating prediction..." if selected_stock in all_models
                    else "Training a model for this stock (first time only — cached after)..."
                )
                with st.spinner(spinner_msg):
                    model_dict = get_or_train_model(selected_stock, all_models)

                if model_dict:
                    predicted_price, prediction_date = predict_next_day(selected_stock, model_dict)
                    if predicted_price is not None:
                        pred_change = predicted_price - last_price
                        pred_change_pct = (pred_change / last_price) * 100
                        st.subheader(f"Prediction for {prediction_date}")
                        st.metric("Predicted Price", f"{currency_symbol}{predicted_price:.2f}", f"{pred_change_pct:.2f}%")
                        if model_dict.get('on_demand'):
                            st.caption("⚡ On-demand model (XGBoost + Random Forest ensemble)")
                        else:
                            st.caption("🎯 Curated model (LSTM + XGBoost + Random Forest ensemble)")
                    else:
                        st.warning(prediction_date)
                else:
                    st.warning(f"Not enough historical data to train a reliable model for {selected_stock} yet.")
            else:
                st.error("Not enough historical data available for this stock.")

        with col2:
            st.subheader("Company Info")
            if 'sector' in info:
                st.write(f"**Sector:** {info['sector']}")
            if 'industry' in info:
                st.write(f"**Industry:** {info['industry']}")
            if 'marketCap' in info and info['marketCap']:
                st.write(f"**Market Cap:** {info['marketCap']:,.0f}")
            if 'trailingPE' in info and info['trailingPE']:
                st.write(f"**P/E Ratio:** {info['trailingPE']:.2f}")
            if 'dividendYield' in info and info['dividendYield'] is not None:
                st.write(f"**Dividend Yield:** {info['dividendYield']:.2f}%")

            if st.button("Add to Watchlist"):
                add_to_watchlist(st.session_state['user'], selected_stock)
                st.success(f"{selected_stock} added to watchlist!")

    except Exception as e:
        st.error(f"Error fetching stock data: {e}")

st.sidebar.write("### Your Watchlist")
for stock in get_watchlist(st.session_state['user']):
    st.sidebar.write(f"- {stock}")