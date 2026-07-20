import streamlit as st
from utils import (
    require_login, get_watchlist, predict_next_day, load_models,
    get_currency_symbol, remove_from_watchlist, get_stock_history,
    get_or_train_model
)

require_login()

st.title("Your Watchlist")

all_models = load_models()
watchlist = get_watchlist(st.session_state['user'])

if not watchlist:
    st.info("Your watchlist is empty. Add stocks from the main Prediction page!")
else:
    cols = st.columns(3)
    for i, stock in enumerate(watchlist):
        with cols[i % 3]:
            hist = get_stock_history(stock, period="5d")

            if not hist.empty and len(hist) >= 2:
                last_price = hist['Close'].iloc[-1]
                price_change = hist['Close'].iloc[-1] - hist['Close'].iloc[-2]
                price_change_pct = (price_change / hist['Close'].iloc[-2]) * 100
                currency_symbol = get_currency_symbol(stock)

                st.subheader(stock)
                st.metric("Price", f"{currency_symbol}{last_price:.2f}", f"{price_change_pct:.2f}%")

                with st.spinner("Loading prediction..."):
                    model_dict = get_or_train_model(stock, all_models)

                if model_dict:
                    predicted_price, prediction_date = predict_next_day(stock, model_dict)
                    if predicted_price is not None:
                        pred_change_pct = ((predicted_price - last_price) / last_price) * 100
                        direction = "↑" if pred_change_pct > 0 else "↓"
                        st.write(f"Prediction: {direction} {currency_symbol}{predicted_price:.2f} ({pred_change_pct:.2f}%)")

                st.line_chart(hist['Close'])

                if st.button("Remove", key=f"remove_{stock}"):
                    remove_from_watchlist(st.session_state['user'], stock)
                    st.rerun()
            else:
                st.subheader(stock)
                st.warning("No data available")
                if st.button("Remove", key=f"remove_{stock}"):
                    remove_from_watchlist(st.session_state['user'], stock)
                    st.rerun()