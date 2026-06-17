import pandas as pd
import yfinance as yf
from utils import get_market_data
import datetime

print("Tools loaded successfully! Fetching data...")

# 1. Download historical data for Apple
source = "alphavantage"
ticker = "AAPL"
spec = {
    "name": f"100d-leading",
    "size": "compact"
}
data = get_market_data(source, ticker, spec, False)

# 2. Look at the first few rows of data
print("\n--- Market Data Preview ---")
print(data.head())

# 3. Calculate a basic 5-day moving average
data['5_Day_MA'] = data['close'].rolling(window=5).mean()

print("\n--- Data with Moving Average ---")
print(data[['close', '5_Day_MA']].dropna().head())