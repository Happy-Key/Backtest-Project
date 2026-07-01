from utils import *

def execute():
    filename = f'data/silver/SEC/AAPL_long.parquet'
    if os.path.exists(filename):
        data = pd.read_parquet(filename)
    data = data[data.tag == 'NetIncomeLoss']
    data = data[data.form.isin(['10-K','10-Q','10-K/A','10-Q/A'])].sort_values('filed')
    ttm(data[['start','end','val','filed']])
            

def ttm(df):
    tolerance = 5
    #start, end, val, filed
    df['start'] = pd.to_datetime(df['start'])
    df['end'] = pd.to_datetime(df['end'])
    df['duration'] = (df.end - df.start).dt.days
    og = df.copy()
    states = df.copy()

    for i in range(2):
        cross_df = df.merge(og, how='cross')
        df = cross_df[ (cross_df['end_x'] - cross_df['start_y']).dt.days.abs() <= tolerance ]
        df['start'] = pd.to_datetime(df['start_x'])
        df['end'] = pd.to_datetime(df['end_y'])
        df['duration'] = df.duration_x + df.duration_y + 1
        df['val'] = df.val_x + df.val_y
        df['filed'] = np.maximum(df.filed_x, df.filed_y)
        df = df[['start','end','val','filed','duration']]
        #suitable_intervals = pd.concat([suitable_intervals, df[df.duration >= 350]], ignore_index=True)
        df = df[df.duration < 800]
        states = pd.concat([states, df])
    df = states.copy()
    suitable_intervals = pd.DataFrame(df[(350 <= df.duration) & (df.duration < 400)])
    df = df[df.duration >= 400]
    for _ in range(2):
        cross_df = df.merge(og, how='cross')
        df = cross_df[ (cross_df['end_x'] - cross_df['end_y']).dt.days.abs() <= tolerance ]
        df['start'] = pd.to_datetime(np.minimum(df.start_x, df.start_y))
        df['end'] = pd.to_datetime(np.maximum(df.start_x, df.start_y))
        df['duration'] = np.abs(df.duration_x - df.duration_y - 1)
        df['val'] = np.abs(df.val_x - df.val_y)
        df['filed'] = np.maximum(df.filed_x, df.filed_y)
        df = df[['start','end','val','filed','duration']]
        suitable_intervals = pd.concat([suitable_intervals, df[(350 <= df.duration) & (df.duration < 400)]], ignore_index=True)
        df = df[df.duration >= 400]
    df = states.copy()
    for _ in range(2):
        cross_df = df.merge(og, how='cross')
        df = cross_df[ (cross_df['start_x'] - cross_df['start_y']).dt.days.abs() <= tolerance ]
        df['start'] = pd.to_datetime(np.minimum(df.end_x, df.end_y))
        df['end'] = pd.to_datetime(np.maximum(df.end_x, df.end_y))
        df['duration'] = np.abs(df.duration_x - df.duration_y - 1)
        df['val'] = np.abs(df.val_x - df.val_y)
        df['filed'] = np.maximum(df.filed_x, df.filed_y)
        df = df[['start','end','val','filed','duration']]
        suitable_intervals = pd.concat([suitable_intervals, df[(350 <= df.duration) & (df.duration < 400)]], ignore_index=True)
        df = df[df.duration >= 400]

    #suitable_intervals = suitable_intervals[suitable_intervals.duration < 400]
    suitable_intervals = suitable_intervals.sort_values('end', ascending=False)
    suitable_intervals = suitable_intervals.drop_duplicates(subset='filed')
    suitable_intervals = suitable_intervals.sort_values('filed')
    suitable_intervals['val'] = suitable_intervals.val / suitable_intervals.duration * 365
    suitable_intervals = suitable_intervals.reset_index()
    print(suitable_intervals.tail(15))

    trading_dates = pd.date_range(start=suitable_intervals["filed"].min(), end=suitable_intervals["filed"].max(), freq="B")
    daily_df = pd.DataFrame({"datetime": trading_dates})
    sparse_ttm = suitable_intervals[["filed", "val"]].rename(columns={"filed": "datetime"})
    sparse_ttm['datetime'] = pd.to_datetime(sparse_ttm['datetime'])
    wide_df = pd.merge_asof(daily_df, sparse_ttm, on="datetime", direction="backward")
    wide_df['val'] = wide_df.val.ffill()
    #print(wide_df.head(5))
    #print(wide_df.tail(5))
    return wide_df

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