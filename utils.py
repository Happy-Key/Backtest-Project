import os
import pandas as pd
import yfinance as yf
import sys
from yfinance.exceptions import YFRateLimitError

def get_market_data(ticker, start_date, end_date):
    """Fetches data from Yahoo Finance or loads it from a local Parquet cache."""
    # Ensure the data directory exists
    os.makedirs("data", exist_ok=True)
    
    filename = f"data/yfinance_{ticker}_{start_date}_{end_date}.parquet"
    
    if os.path.exists(filename):
        print(f"[{ticker}] Loading from local disk cache...")
        return pd.read_parquet(filename)
    else:
        print(f"[{ticker}] Cache miss. Fetching from Yahoo Finance...")
        df = yf.download(ticker, start=start_date, end=end_date)
        if df.empty:
            print("Fetch failure")
            return df
        df.to_parquet(filename)
        return df