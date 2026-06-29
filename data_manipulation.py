from utils import *
import time

def execute():
    facts_to_long_by_list('lists/tickers_S&P600.txt')

def get_company_facts_from_list(list_path):
    with open(list_path, "r", encoding="utf-8") as file:
        ticker_list = str.split(file.read(),',')
    tickers_more = 1
    for ticker in ticker_list:
        if tickers_more <= 0:
            tickers_more = int(input("how many more?"))
            if tickers_more <= 0: break
        if os.path.exists(f'data/bronze/SEC/{ticker}_facts.json'):
            continue
        get_sec_company_facts(SEC_USER_AGENT, ticker)
        time.sleep(0.3)
        tickers_more -= 1

def facts_to_long_by_list(list_path):
    with open(list_path, "r", encoding="utf-8") as file:
        ticker_list = str.split(file.read(),',')
    for ticker in ticker_list:
        if os.path.exists(f'data/silver/SEC/{ticker}_long.parquet'):
            continue
        sec_facts_to_long(ticker)
        
execute()