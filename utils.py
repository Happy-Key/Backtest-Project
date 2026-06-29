import os
import pandas as pd
import yfinance as yf
import requests
import io
import sys
import json
from pathlib import Path
from twelvedata import TDClient
import datetime
import time
from sec_cik_mapper import StockMapper

AV_API_KEY = "[REDACTED_API_KEY]"
TD_API_KEY = "[REDACTED_API_KEY]"
SEC_USER_AGENT = "[REDACTED_SEC_USER_AGENT]"

def get_sec_company_facts(user_agent, ticker):
    map = pd.read_parquet('data/cik_map.parquet')
    cik = map.loc[map['Ticker'] == ticker, 'CIK'].values[0]
    padded_cik = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded_cik}.json"
    headers = {
        'User-Agent': user_agent,
        'Host': 'data.sec.gov'
        }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"SEC API returned status code {response.status_code}. Ensure your User-Agent is valid."
        )
    data = response.json()
    with open(f'data/bronze/SEC/{ticker}_facts.json', 'w') as f:
        json.dump(data, f)
    return data
    
def sec_facts_to_long(ticker):
    filename = f'data/bronze/SEC/{ticker}_facts.json'
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
    else:
        print(f'[{ticker}] SEC Company Facts not in database.')
        if (input(f'Fetch [{ticker}] Company Facts? (y/n)') != 'y'): return
        data = get_sec_company_facts(SEC_USER_AGENT, ticker)
    all_records = []
    facts = data.get("facts", {})
    for tags in facts.values():
        for tag, tag_data in tags.items():
            units = tag_data.get("units", {})
            for unit_rows in units.values():
                for row in unit_rows:
                    row["tag"] = tag
                    row["ticker"] = ticker
                    all_records.append(row)

    df = pd.DataFrame(all_records)
    df.to_parquet(f"data/silver/SEC/{ticker}_long.parquet")
    return df

def get_market_data(s, getFresh=False, confirmation=True):
    search_result = search_data(s, getFresh)
    if (not isinstance(search_result, str)):
        return search_result
    filename = search_result
    if confirmation:
        if input('Data not found in cache. Request data? (y/n)') != 'y':
            raise RuntimeError('Data unavailable')
    print(f"[{s['ticker']}] Cache miss. Fetching from {s['source']}...")
    match s["source"]:
        case "yfinance":
            df = yf.download(s['ticker'], start=s['start_date'], end=s['end_date'], auto_adjust=True, group_by='ticker')
        case "alphavantage":
            df = request_av_data(s)
        case "twelvedata":
            df = request_td_data(s)
        case _:
            raise RuntimeError('Unknown source')
    if df.empty:
        raise RuntimeError('Fetch failure')
    df.to_parquet(filename)
    if confirmation:
        if input('Continue with program? (y/n)') != 'y':
            sys.exit(0)
    return df

def summon_universe(list_path):
    with open(list_path, "r", encoding="utf-8") as file:
        ticker_list = str.split(file.read(),',')
    tickers_more = 1
    for ticker in ticker_list:
        tickers_more -= 1
        spec = {
            "source": "alphavantage",
            "ticker": ticker,
            "series": "EARNINGS",
            "datatype": "json"
        }
        get_market_data(spec, confirmation=False)
        spec = {
            "source": "twelvedata",
            "ticker": ticker,
        }
        get_market_data(spec, confirmation=False)
        if tickers_more <= 0:
            tickers_more = int(input("how many more?"))
            if tickers_more <= 0: break
        time.sleep(10)

def search_data(s, getFresh):
    data_dir = Path("./data")
    
    protoname = file_name_by_spec(s)
    filename = "data/" + protoname + f"_{datetime.date.today()}.parquet"

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
        return filename

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
            data['unadjusted_close'] = data['close']
            data['timestamp'] = pd.to_datetime(data['datetime'])
            data = data.drop(columns=['volume', 'datetime'])
    return data

def request_av_data(spec):
    time_series_data = ["DAILY", "DAILY_ADJUSTED", "WEEKLY", "WEEKLY_ADJUSTED"]
    url = ["https://www.alphavantage.co/query?function=",
           "TIME_SERIES_" if spec['series'] in time_series_data else "",
           spec['series'],
           "&symbol=",
           spec['ticker'],
           "&apikey=",
           AV_API_KEY,
           "&datatype=csv" if spec['datatype'] == "csv" else "",
           ]
    url = "".join(url)
    response = requests.get(url)
    match spec['datatype']:
        case "csv":
            df = pd.read_csv(io.StringIO(response.text))
        case "json":
            data = response.json()
            if ('quarterlyEarnings' not in data.keys()):
                print(data)
                raise RuntimeError("freak")
            df = pd.DataFrame(data["quarterlyEarnings"])
    
    df = df.iloc[::-1].reset_index(drop=True)
    return df

def request_td_data(spec):
    td = TDClient(apikey=TD_API_KEY)
    ts = td.time_series(
        symbol=spec['ticker'],
        outputsize=5000,
        interval="1day",
    )
    df = ts.as_pandas()
    df = df.iloc[::-1].reset_index()
    return df

def file_name_by_spec(s):
    os.makedirs("data/"+s['source'], exist_ok=True)
    match s['source']:
        case "yfinance":
            protoname = f"{s['source']}/{s['ticker']}_{s['start_date']}"
        case "alphavantage":
            protoname = f"{s['source']}/{s['ticker']}_{s['series']}"
        case "twelvedata":
            protoname = f"{s['source']}/{s['ticker']}"
        case _:
            raise RuntimeError("Unknown source")
    return protoname

def download_cik_mapper():
    mapper = StockMapper()
    mapper.raw_dataframe.to_parquet('data/cik_map.parquet')

def read_parquet(path):
    os.makedirs("temp", exist_ok=True)
    df = pd.read_parquet("data/" + path + ".parquet")
    df.to_csv("temp/" + str.split(path,"/")[-1] + ".csv")