import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import tempfile
import datetime

# ---------------- PAGE CONFIG ----------------
st.set_page_config("Stock AI Trading", layout="wide")

# ---------------- MONGODB ----------------
@st.cache_resource
def get_db():
    client = MongoClient(
        "mongodb://localhost:27018",
        serverSelectionTimeoutMS=3000
    )
    client.server_info()
    return client["stock_ai"]

try:
    db = get_db()
    users_col = db["users"]
    portfolio_col = db["portfolio"]
except ServerSelectionTimeoutError:
    st.error("❌ MongoDB not running on port 27018")
    st.stop()

# ---------------- LOGIN ----------------
if "user" not in st.session_state:
    st.session_state.user = None

st.sidebar.title("🔐 Login")

email = st.sidebar.text_input("Email")
password = st.sidebar.text_input("Password", type="password")

col1, col2 = st.sidebar.columns(2)

with col1:
    if st.button("Login"):
        user = users_col.find_one({"email": email})
        if user and user["password"] == password:
            st.session_state.user = email
            st.success("Login successful")
        else:
            st.error("Invalid credentials")

with col2:
    if st.button("Register"):
        if users_col.find_one({"email": email}) is None:
            users_col.insert_one({"email": email, "password": password})
            st.success("Registered successfully")
        else:
            st.warning("User already exists")

if not st.session_state.user:
    st.stop()

st.sidebar.success(f"Logged in as {st.session_state.user}")

# ---------------- STOCK INPUT ----------------
st.title("📈 Stock AI Trading Dashboard")

ticker = st.text_input("Enter Stock Symbol (e.g. AAPL, TCS.NS)", "AAPL")

data = yf.download(ticker, period="6mo")

if data.empty:
    st.error("No stock data found")
    st.stop()

price = float(data["Close"].iloc[-1])
sma20 = float(data["Close"].rolling(20).mean().iloc[-1])

best_entry = round(sma20, 2)
target = round(best_entry * 1.10, 2)
stop_loss = round(best_entry * 0.95, 2)

usd_to_inr = 83.0

# ---------------- SIGNAL ----------------
signal = "HOLD"
if price <= best_entry:
    signal = "BUY"
elif price >= target:
    signal = "SELL"

# ---------------- DISPLAY METRICS ----------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Price (USD)", f"${price:,.2f}")
c2.metric("Price (INR)", f"₹{price * usd_to_inr:,.2f}")
c3.metric("Best Entry", f"${best_entry}")
c4.metric("Signal", signal)

# ---------------- GRAPH ----------------
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(data.index, data["Close"], label="Price")
ax.axhline(best_entry, color="green", linestyle="--", label="Best Entry")
ax.axhline(target, color="blue", linestyle="--", label="Target")
ax.axhline(stop_loss, color="red", linestyle="--", label="Stop Loss")
ax.legend()
ax.set_title(f"{ticker} Price Chart")
st.pyplot(fig)

# ---------------- SAVE TO PORTFOLIO ----------------
if st.button("💾 Add to Portfolio"):
    portfolio_col.insert_one({
        "user": st.session_state.user,
        "ticker": ticker,
        "price": price,
        "entry": best_entry,
        "target": target,
        "stop_loss": stop_loss,
        "date": datetime.datetime.now()
    })
    st.success("Added to portfolio")

# ---------------- SHOW PORTFOLIO ----------------
st.subheader("📊 Your Portfolio")

portfolio = list(portfolio_col.find({"user": st.session_state.user}))
if portfolio:
    df = pd.DataFrame(portfolio)
    st.dataframe(df[["ticker", "price", "entry", "target", "stop_loss"]])
else:
    st.info("Portfolio empty")

# ---------------- PDF REPORT ----------------
if st.button("📄 Download Trade Report (PDF)"):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(temp_file.name, pagesize=A4)

    c.drawString(50, 800, "Stock AI Trading Report")
    c.drawString(50, 770, f"User: {st.session_state.user}")
    c.drawString(50, 740, f"Stock: {ticker}")
    c.drawString(50, 710, f"Price: ${price:.2f}")
    c.drawString(50, 680, f"Best Entry: ${best_entry}")
    c.drawString(50, 650, f"Target: ${target}")
    c.drawString(50, 620, f"Stop Loss: ${stop_loss}")
    c.drawString(50, 590, f"Signal: {signal}")

    c.save()

    with open(temp_file.name, "rb") as f:
        st.download_button(
            "⬇ Download PDF",
            f,
            file_name="trade_report.pdf",
            mime="application/pdf"
        )
