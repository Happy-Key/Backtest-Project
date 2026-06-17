import pandas as pd
import yfinance as yf
from utils import get_market_data

print("Tools loaded successfully! Fetching data...")

# 1. Download historical data for Apple
ticker = "AAPL"
data = get_market_data(ticker, "2020-01-01", "2026-06-01")

# 2. Look at the first few rows of data
print("\n--- Market Data Preview ---")
print(data.head())

# 3. Calculate a basic 5-day moving average
data['5_Day_MA'] = data['Close'].rolling(window=5).mean()

print("\n--- Data with Moving Average ---")
print(data[['Close', '5_Day_MA']].dropna().head())