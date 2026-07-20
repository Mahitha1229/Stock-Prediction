import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
from utils import require_login, get_technical_indicators, validate_ticker, resolve_ticker, render_ticker_picker
require_login()

st.title("Custom Technical Analysis")

selected_stock = render_ticker_picker("ticker_input_ta")

if selected_stock:
    if not validate_ticker(selected_stock):
        suggestions = resolve_ticker(selected_stock)
        if suggestions:
            st.error(f"Couldn't find data for '{selected_stock}'. Did you mean one of these?")
            cols = st.columns(min(len(suggestions), 5))
            for i, match in enumerate(suggestions[:5]):
                label = f"{match['symbol']} — {match['name']}"
                if cols[i].button(label, key=f"suggest_ta_{match['symbol']}"):
                    st.session_state["ticker_input_ta"] = match["symbol"]
                    st.rerun()
        else:
            st.error(f"Couldn't find data for '{selected_stock}'. Check the ticker symbol.")
        st.stop()

    st.subheader(f"Technical Indicators for {selected_stock}")
    stock = yf.Ticker(selected_stock)
    hist = stock.history(period="60d")

    if not hist.empty:
        data = get_technical_indicators(hist)
        st.dataframe(data[['Close', 'RSI', 'Stochastic', 'ROC', 'ADX']].tail())

        tab1, tab2, tab3 = st.tabs(["Price & Volume", "Momentum Indicators", "Volatility"])

        with tab1:
            fig, ax = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [3, 1]})
            ax[0].plot(data.index, data['Close'], label='Close Price')
            ax[0].set_title(f"{selected_stock} Price")
            ax[0].grid(True, alpha=0.3)
            ax[0].legend()
            ax[1].bar(data.index, data['Volume'], label='Volume')
            ax[1].set_title("Volume")
            ax[1].grid(True, alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig)

        with tab2:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            ax1.plot(data.index, data['RSI'], color='purple')
            ax1.axhline(y=70, color='r', linestyle='-', alpha=0.3)
            ax1.axhline(y=30, color='g', linestyle='-', alpha=0.3)
            ax1.fill_between(data.index, data['RSI'], 70, where=(data['RSI'] >= 70), color='r', alpha=0.3)
            ax1.fill_between(data.index, data['RSI'], 30, where=(data['RSI'] <= 30), color='g', alpha=0.3)
            ax1.set_title("Relative Strength Index (RSI)")
            ax1.grid(True, alpha=0.3)

            ax2.plot(data.index, data['Stochastic'], color='blue')
            ax2.axhline(y=80, color='r', linestyle='-', alpha=0.3)
            ax2.axhline(y=20, color='g', linestyle='-', alpha=0.3)
            ax2.fill_between(data.index, data['Stochastic'], 80, where=(data['Stochastic'] >= 80), color='r', alpha=0.3)
            ax2.fill_between(data.index, data['Stochastic'], 20, where=(data['Stochastic'] <= 20), color='g', alpha=0.3)
            ax2.set_title("Stochastic Oscillator")
            ax2.grid(True, alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig)

        with tab3:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(data.index, data['ROC'], label='Rate of Change', color='orange')
            ax.axhline(y=0, color='k', linestyle='-', alpha=0.3)
            ax.set_title("Rate of Change (ROC)")
            ax.grid(True, alpha=0.3)
            ax.legend()
            st.pyplot(fig)
    else:
        st.error("No data available for this stock.")