import os
import pandas as pd
import yfinance as yf
import requests
import io
from pathlib import Path
import datetime

AV_API_KEY = "[REDACTED_API_KEY]"

def get_market_data(source, ticker, spec, getFresh):
    """Fetches data from Yahoo Finance or loads it from a local Parquet cache."""
    # Ensure the data directory exists
    os.makedirs("data", exist_ok=True)
    data_dir = Path("./data")
    
    protoname = f"{source}_{ticker}_{spec['name']}_"
    filename = "data/" + protoname + f"{datetime.date.today()}.parquet"

    files = data_dir.glob(protoname + "*.parquet")
    filelist = []
    for file_path in files:
        filelist.append(file_path)
    filelist.sort()
    
    if os.path.exists(filename):
        print(f"[{ticker}] Loading fresh data...")
        return pd.read_parquet(filename)
    elif (not getFresh) and len(filelist) > 0:
        print(f"[{ticker}] Loading STALE data...")
        return pd.read_parquet(str(filelist[-1]))
    else:
        print(f"[{ticker}] Cache miss. Fetching from {source}...")
        match source:
            case "yfinance":
                df = yf.download(ticker, start=spec["start_date"], end=spec["end_date"])
            case "alphavantage":
                df = fetch_av_data(ticker, spec)
            case _:
                raise RuntimeError("Unknown source")
        if df.empty:
            print("Fetch failure")
            return df
        df.to_parquet(filename)
        return df
    
def fetch_av_data(ticker, spec):
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&outputsize={spec['size']}&apikey={AV_API_KEY}&datatype=csv"
    response = requests.get(url)
    df = pd.read_csv(io.StringIO(response.text))
    df = df.iloc[::-1].reset_index(drop=True)
    return df