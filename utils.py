import os
import pandas as pd
import yfinance as yf
import requests
import io
from pathlib import Path
import datetime

AV_API_KEY = "[REDACTED_API_KEY]"

def get_market_data(s, request=False, getFresh=False):
    """Fetches data from Yahoo Finance or loads it from a local Parquet cache."""
    # Ensure the data directory exists
    os.makedirs("data", exist_ok=True)
    data_dir = Path("./data")
    
    protoname = file_name_by_spec(s)
    filename = "data/" + protoname + f"{datetime.date.today()}.parquet"

    files = data_dir.glob(protoname + "*.parquet")
    filelist = []
    for file_path in files:
        filelist.append(file_path)
    filelist.sort()
    
    if os.path.exists(filename):
        print(f"[{s['ticker']}] Loading fresh data...")
        return pd.read_parquet(filename)
    elif (not getFresh) and len(filelist) > 0:
        print(f"[{s['ticker']}] Loading STALE data...")
        return pd.read_parquet(str(filelist[-1]))
    elif request:
        print(f"[{s['ticker']}] Cache miss. Fetching from {s['source']}...")
        match s["source"]:
            case "yfinance":
                df = yf.download(s["ticker"], start=s["start_date"], end=s["end_date"])
            case "alphavantage":
                df = fetch_av_data(s)
            case _:
                raise RuntimeError("Unknown source")
        if df.empty:
            print("Fetch failure")
            return df
        df.to_parquet(filename)
        return df
    else:
        raise RuntimeError("Data unavailable")
    
def fetch_av_data(spec):
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_{spec['series']}&symbol={spec['ticker']}&apikey={AV_API_KEY}&datatype=csv"
    response = requests.get(url)
    df = pd.read_csv(io.StringIO(response.text))
    df = df.iloc[::-1].reset_index(drop=True)
    return df

def file_name_by_spec(s):
    match s["source"]:
        case "yfinance":
            protoname = f"{s['source']}_{s['ticker']}_{s['start_date']}_{s['end_date']}_"
        case "alphavantage":
            protoname = f"{s['source']}_{s['ticker']}_{s['series']}_"
        case _:
            raise RuntimeError("Unknown source")
    return protoname
    
def read_parquet(path):
    os.makedirs("temp", exist_ok=True)
    df = pd.read_parquet("data/" + path + ".parquet")
    df.to_csv("temp/" + path + ".csv")