import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from utils import *
import strategies
import datetime

#constants
fixed_fee_rate = 0.005
benchmark_rate = 0.0362
ann_borrow_premium = 0.015
ann_interest_premium = 0.015
ann_borrow_rate = benchmark_rate + ann_borrow_premium
ann_interest_rate = benchmark_rate - ann_interest_premium

#specifics
ticker_name = 'short600'
strategy_name = 'Basket'
ann_actions = 252
source_name = 'twelvedata'

def main():
    data = fetch_data_from_list("lists/short600.txt")
    #data = fetch_data()
    data.sort_values(['ticker','timestamp'])
    (train, test) = train_test_split(data)
    data = train
    df = add_log_return(data)
    match strategy_name:
        case 'Buy and Hold':
            df['signal'] = 1
        case 'MA Crossover':
            df['signal'] = strategies.MA_Crossover(df, 20, 200)
        case 'BBand':
            df['signal'] = strategies.Bollinger_Band(df, 200, 2.5)
        case 'Combined':
            df['signal1'] = strategies.MA_Crossover(df, 20, 200)
            df['signal2'] = strategies.Bollinger_Band(df, 200, 2.5)
            df['signal'] = np.clip(df.signal1 + df.signal2,-1,1)
        case 'Basket':
            fundamental = pd.read_parquet("data/gold/fundamental/wide.parquet")
            fundamental['timestamp'] = pd.to_datetime(fundamental['datetime'])
            df['signal'] = strategies.Momentum_Value_Basket(df, fundamental, 10, 20, 252)
    df['signal'] = df.signal.fillna(0)
    df['signal'] = df.groupby('ticker').signal.shift(1)
    df = df.dropna()
    df['total_signal'] = df.groupby('timestamp')['signal'].transform('sum')
    df['signal'] = np.where(df.total_signal == 0, 0, df.signal / df.total_signal)
    df = add_fees(df, fixed_fee_rate)
    df = df.dropna()
    analysis = analyze_results(df)
    
    print(f'Strategy ann-return: {analysis.strat_return.mean()*ann_actions}')
    print(f'Strategy ann. sharpe: {ann_sharpe(analysis.strat_return, ann_actions)}')
    print(f'Optimal leverage: {kelly_leverage(ann_actions*analysis.strat_return.mean(),ann_actions*analysis.strat_return.var())}')
    print(f'Max drawdown: {100*(1-np.exp(analysis.drawdown.min()))}%')
    print(f'Ann. return lost to fees: {analysis.fee.mean()*ann_actions}')

    if input('Graph Data? (y/n)') == 'y':
        graph_results(analysis, 'log-return', f'[{ticker_name}] {strategy_name} vs. Buy and Hold')

def analyze_results(df):
    df['strat_return'] = df.signal*df.log_return + df.fee
    df['market_return'] = df.log_return
    analysis = df[['timestamp']].drop_duplicates().sort_values('timestamp')
    analysis = analysis.merge(df.groupby('timestamp')['strat_return'].sum(), on='timestamp')
    analysis['cum_return'] = analysis.strat_return.cumsum()
    analysis = analysis.merge(df.groupby('timestamp')['market_return'].mean(), on='timestamp')
    analysis['market_cum_return'] = analysis.market_return.cumsum()
    analysis['peak'] = analysis.cum_return.cummax()
    analysis['drawdown'] = analysis.cum_return - analysis.peak
    analysis['strat_equity'] = np.exp(analysis.cum_return)
    analysis['market_equity'] = np.exp(analysis.market_cum_return)
    analysis = analysis.merge(df.groupby('timestamp')['fee'].sum(), on='timestamp')
    return analysis

def add_fees(df, absoluteFee):
    df['feeLogReturn'] = np.log((df['unadjusted_close']-absoluteFee) / df['unadjusted_close']) 
    df['fee'] = df.signal.diff().fillna(0).abs() * df.feeLogReturn
    df = df.drop(columns=['feeLogReturn'])
    return df

def train_test_split(data, years=5):
    train = data.loc[data['timestamp'] < data['timestamp'].tail(1).item() - datetime.timedelta(days=365*years)]
    test = data.loc[data['timestamp'] >= data['timestamp'].tail(1).item() - datetime.timedelta(days=365*years)]
    return (train, test)

def add_log_return(df, num_returns=1):
    df['prev_close'] = df.groupby('ticker')['close'].shift(1)
    df['log_return'] = np.log(df.close/df.prev_close)
    if num_returns > 1:
        for i in range(1, num_returns):
            df['log_return_lag' + str(i)] = df.groupby('ticker').log_return.shift(i)
    return df

def kelly_leverage(mean, var):
    deposit_leverage = (mean - np.log(1+ann_interest_rate)) / var
    borrow_leverage = (mean - np.log(1+ann_borrow_rate)) / var
    if borrow_leverage > 1:
        leverage = borrow_leverage
    elif deposit_leverage < 1:
        leverage = deposit_leverage
    else:
        leverage = 1
    return leverage

def ann_sharpe(returns, annual_actions):
    return np.sqrt(annual_actions)*(returns).mean()/(returns).std()

def fetch_data():
    spec = {
        "source": source_name,
        "ticker": ticker_name,
        "series": "WEEKLY_ADJUSTED",
        "datatype": "csv",
        "start_date": "2000-01-01",
        "end_date": datetime.date.today()
    }
    data = format_data(get_market_data(spec), source_name)
    data['ticker'] = ticker_name
    return data

def fetch_data_from_list(list_path):
    with open(list_path, "r", encoding="utf-8") as file:
        ticker_list = str.split(file.read(),',')
        accumulated_tickers = []
        for ticker in ticker_list:
            spec = {
                    "source": source_name,
                    "ticker": ticker,
                    "series": "WEEKLY_ADJUSTED",
                    "datatype": "csv",
                    "start_date": "2000-01-01",
                    "end_date": datetime.date.today()
                }
            temp = format_data(get_market_data(spec), source_name)
            temp['ticker'] = ticker
            accumulated_tickers.append(temp)
        df = pd.concat(accumulated_tickers, ignore_index=True)
        return df
            

def graph_results(df, graph_type, name):
    fig = go.Figure()

    match graph_type:
        case 'log-return':
            graph_log_return(df, fig)
        case 'equity':
            graph_equity(df, fig)
        case _:
            raise RuntimeError("Invalid Graph Type")
    
    fig.update_layout(
        title=name,
        xaxis_title='Date',
        hovermode='x unified', # Shows values for both lines when hovering
        template='plotly_dark'
    )

    fig.show()

def graph_log_return(df, fig):
    fig.add_trace(go.Scatter(
        x=df.timestamp, 
        y=df['cum_return'], 
        mode='lines', 
        name='Strategy',
        line=dict(color='limegreen', width=2)
    ))
    fig.add_trace(go.Scatter(
        x=df.timestamp, 
        y=df['market_cum_return'], 
        mode='lines', 
        name='Buy & Hold (Benchmark)',
        line=dict(color='gray', width=1.5, dash='dash')
    ))
    fig.update_layout(
        yaxis_title='Log return',
    )

def graph_equity(df, fig):
    fig.add_trace(go.Scatter(
        x=df.timestamp, 
        y=df['strat_equity'], 
        mode='lines', 
        name='Strategy',
        line=dict(color='limegreen', width=2)
    ))

    fig.add_trace(go.Scatter(
        x=df.timestamp, 
        y=np.exp(df['peak']), 
        mode='lines', 
        name='High-Water Mark',
        line=dict(color='red', width=2),
        fill='tonexty',
        fillcolor='rgba(255, 0, 0, 0.2)'
    ))

    # Add the Buy & Hold (Market) Equity line for comparison
    fig.add_trace(go.Scatter(
        x=df.timestamp, 
        y=df['market_equity'], 
        mode='lines', 
        name='Buy & Hold (Benchmark)',
        line=dict(color='gray', width=1.5, dash='dash')
    ))

    fig.update_layout(
        yaxis_title='Equity ($)',
    )

#execution order shenanigans
main()
#read_parquet("yfinance_SPY_1999-01-01_2026-06-20_2026-06-20")