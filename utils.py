import os
import pandas as pd
import yfinance as yf
import requests
import io
import sys
from pathlib import Path
from twelvedata import TDClient
import datetime

AV_API_KEY = "[REDACTED_API_KEY]"
TD_API_KEY = "[REDACTED_API_KEY]"

def get_market_data(s, getFresh=False):
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
    else:
        if input('Data not found in cache. Request data? (y/n)') != 'y':
            raise RuntimeError('Data unavailable')
        print(f"[{s['ticker']}] Cache miss. Fetching from {s['source']}...")
        match s["source"]:
            case "yfinance":
                df = yf.download(s['ticker'], start=s['start_date'], end=s['end_date'], auto_adjust=True, group_by='ticker')
            case "alphavantage":
                df = fetch_av_data(s)
            case "twelvedata":
                df = fetch_td_data(s)
            case _:
                raise RuntimeError('Unknown source')
        if df.empty:
            raise RuntimeError('Fetch failure')
        df.to_parquet(filename)
        if input('Continue with program? (y/n)') != 'y':
            sys.exit(0)
        return df
    
def format_data(data, datatype):
    match datatype:
        case "alphavantage":
            data['unadjusted_close'] = data['close']
            data['close'] = data['adjusted close']
            data = data.drop(columns=['open', 'high', 'low', 'adjusted close', 'volume', 'dividend amount'])
            data['timestamp'] = pd.to_datetime(data['timestamp'])
        case "yfinance":
            data = data.reset_index()
            data.columns = data.columns.droplevel(1) 
            data.index.name = ''
            data['close'] = data['Close']
            data['timestamp'] = data['Date']
            data = data.drop(columns=['Open', 'High', 'Low', 'Close', 'Volume', 'Date'])
        case "twelvedata":
            data = data.iloc[::-1]
            data['unadjusted_close'] = data['close']
            data = data.reset_index()
            data['timestamp'] = pd.to_datetime(data['datetime'])
            data = data.drop(columns=['volume', 'datetime'])
    return data

def fetch_av_data(spec):
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_{spec['series']}&symbol={spec['ticker']}&apikey={AV_API_KEY}&datatype=csv"
    response = requests.get(url)
    df = pd.read_csv(io.StringIO(response.text))
    df = df.iloc[::-1].reset_index(drop=True)
    return df

def fetch_td_data(spec):
    td = TDClient(apikey=TD_API_KEY)
    ts = td.time_series(
        symbol=spec['ticker'],
        outputsize=5000,
        interval="1day",
    )
    df = ts.as_pandas()
    return df

def file_name_by_spec(s):
    match s["source"]:
        case "yfinance":
            protoname = f"{s['source']}_{s['ticker']}_{s['start_date']}_"
        case "alphavantage":
            protoname = f"{s['source']}_{s['ticker']}_{s['series']}_"
        case "twelvedata":
            protoname = f"{s['source']}_{s['ticker']}_"
        case _:
            raise RuntimeError("Unknown source")
    return protoname
    
def read_parquet(path):
    os.makedirs("temp", exist_ok=True)
    df = pd.read_parquet("data/" + path + ".parquet")
    df.to_csv("temp/" + path + ".csv")

#read_parquet("twelvedata_SPY_2026-06-22")