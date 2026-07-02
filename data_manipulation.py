from utils import *

def execute():
    df = pd.DataFrame(columns=['ticker','datetime'])
    df.to_parquet('data/gold/fundamental/wide.parquet')
    
    df = pd.read_parquet('data/gold/fundamental/wide.parquet')
    df = add_EPS_to_gold(df, 'AAMI')
    df = df.dropna(subset=df.columns.difference(['ticker','datetime']), how='all')
    df.to_parquet('data/gold/fundamental/wide.parquet')

def add_EPS_to_gold(gold, ticker):
    net_income_tags = {
        "NetIncomeLoss": 1,
        "ProfitLoss": 2,
        "NetIncomeLossAvailableToCommonStockholdersBasic": 3,
    }
    gold = add_gold_data(gold,ticker,'UnifiedIncome',net_income_tags, True)
    gold = add_gold_data(gold,ticker,'NumberOfShares',{'WeightedAverageNumberOfDilutedSharesOutstanding':1,
                                                                     'WeightedAverageNumberOfSharesOutstandingDiluted':2 }, False)
    gold = add_gold_data(gold,ticker,'PulledEPS',{'EarningsPerShareDiluted':1,
                                                                 'EarningsPerShareBasicAndDiluted':2}, True)
    gold['EPS'] = gold.UnifiedIncome / gold.NumberOfShares
    gold['EPS_MAD'] = np.abs(gold.EPS - gold.PulledEPS)
    #gold.to_csv('temp/test.csv')
    diff_tol = 1.0
    if (gold.EPS_MAD.max() > diff_tol):
        print(f'Maximum EPS deviation of {gold.EPS_MAD.max()} on {ticker} exceeds {diff_tol}')
        #if (input('Continue? (y/n)') != 'y'): raise RuntimeError('EPS Deviation too great, system stopped.')
    return gold.drop(columns=['UnifiedIncome','NumberOfShares','PulledEPS','EPS_MAD'])

def add_gold_data(gold_df, ticker, final_tag_name, valid_tag_hierarchy, isInterval):
    filename = f'data/silver/SEC/{ticker}_long.parquet'
    if os.path.exists(filename):
        data = pd.read_parquet(filename)
    else:
        data = sec_facts_to_long(ticker)
    data = data[data.tag.isin(valid_tag_hierarchy)]
    data['priority'] = data['tag'].map(valid_tag_hierarchy)
    data = data.sort_values('priority', ascending=True)
    data = data.drop_duplicates(subset=['start','end','val','filed'], keep='first')
    data = data[data.form.isin(['10-K','10-Q','10-K/A','10-Q/A'])].sort_values('filed')
    gold_col = ttm(data[['start','end','val','filed']]) if isInterval else smart_select(data[['end','val','filed']])
    gold_col['ticker'] = ticker
    gold_col.rename(columns={'val':final_tag_name}, inplace=True)
    print(gold_col)
    if gold_df[gold_df['ticker'] == ticker].empty:
        return pd.concat([gold_df, gold_col], axis=0, join='outer', ignore_index=False, keys=None)
    return gold_df.merge(gold_col, on=['ticker','datetime'], how='outer')

def smart_select(df):
    #end, val, filed
    df['end'] = pd.to_datetime(df['end'])
    df = df.sort_values('filed', ascending=True)
    df = df[df["end"] > df["end"].shift(1).cummax()]
    df['datetime'] = df.filed
    return df[['datetime','val']]

def ttm(df, tolerance=5, depth=2):
    #start, end, val, filed
    df['start'] = pd.to_datetime(df['start'])
    df['end'] = pd.to_datetime(df['end'])
    df['duration'] = (df.end - df.start).dt.days
    exploded_start = pd.concat([df.assign(start=df["start"] + pd.Timedelta(days=i-tolerance/2)) for i in range(tolerance)],
                               ignore_index=True)
    exploded_start['start'] = exploded_start.start.dt.normalize()
    exploded_end = pd.concat([df.assign(end=df["end"] + pd.Timedelta(days=i-tolerance/2)) for i in range(tolerance)],
                               ignore_index=True)
    exploded_end['end'] = exploded_end.end.dt.normalize()
    states = df.copy()
    for _ in range(depth):
        df = pd.merge(df, exploded_start, left_on='end', right_on='start', how='inner')
        df['start'] = pd.to_datetime(df['start_x'])
        df['end'] = pd.to_datetime(df['end_y'])
        df['duration'] = df.duration_x + df.duration_y + 1
        df['val'] = df.val_x + df.val_y
        df['filed'] = np.maximum(df.filed_x, df.filed_y)
        df = df[['start','end','val','filed','duration']]
        df = df[df.duration < 800]
        states = pd.concat([states, df])
    df = states.copy()
    suitable_intervals = pd.DataFrame(df[(350 <= df.duration) & (df.duration < 400)])
    df = df[df.duration >= 400]
    for _ in range(depth):
        df = pd.merge(df, exploded_end, on='end', how='inner')
        df['start'] = pd.to_datetime(df.start_x)
        df['end'] = pd.to_datetime(df.start_y)
        df['duration'] = np.abs(df.duration_x - df.duration_y - 1)
        df['val'] = df.val_x - df.val_y
        df['filed'] = np.maximum(df.filed_x, df.filed_y)
        df = df[['start','end','val','filed','duration']]
        suitable_intervals = pd.concat([suitable_intervals, df[(350 <= df.duration) & (df.duration < 400)]], ignore_index=True)
        df = df[df.duration >= 400]
    df = states.copy()
    for _ in range(depth):
        df = pd.merge(df, exploded_start, on='start', how='inner')
        df['start'] = pd.to_datetime(df.end_y)
        df['end'] = pd.to_datetime(df.end_x)
        df['duration'] = np.abs(df.duration_x - df.duration_y - 1)
        df['val'] = df.val_x - df.val_y
        df['filed'] = np.maximum(df.filed_x, df.filed_y)
        df = df[['start','end','val','filed','duration']]
        suitable_intervals = pd.concat([suitable_intervals, df[(350 <= df.duration) & (df.duration < 400)]], ignore_index=True)
        df = df[df.duration >= 400]

    suitable_intervals = suitable_intervals.sort_values('end', ascending=False)
    suitable_intervals = suitable_intervals.drop_duplicates(subset='filed', keep='first')
    suitable_intervals = suitable_intervals.sort_values('filed')
    suitable_intervals['val'] = suitable_intervals.val / suitable_intervals.duration * 365
    suitable_intervals = suitable_intervals.reset_index(drop=True)
    suitable_intervals = suitable_intervals[suitable_intervals["end"] >= suitable_intervals["end"].cummax()]
    df = suitable_intervals[['filed','val']]
    return df.rename(columns={'filed':'datetime'})

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