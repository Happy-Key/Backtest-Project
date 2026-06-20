import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from utils import get_market_data, read_parquet
import datetime

benchmark_rate = 0.0362
ann_borrow_premium = 0.015
ann_interest_premium = 0.015
ann_borrow_rate = benchmark_rate + ann_borrow_premium
ann_interest_rate = benchmark_rate - ann_interest_premium

def main():
    print("Tools loaded successfully! Fetching data...")
    data = fetch_data()
    data = format_data(data, "av")
    (train, test) = train_test_split(data)
    data = train
    df = add_log_return(data)
    df = MA_Crossover(df, 3, 10)
    df = df.dropna()

    df = analyze_results(df)

    #graph_log_return(df)
    graph_equity(df)
    
    ann_actions = 52
    print(f'Strategy ann-return: {df.strat_return.mean()*ann_actions}')
    print(f'Strategy ann. sharpe: {np.sqrt(ann_actions)*(df.strat_return).mean()/(df.strat_return).std()}')
    print(f'Optimal leverage: {kelly_leverage(ann_actions*df.strat_return.mean(),ann_actions*df.strat_return.var())}')
    print(f'Max drawdown: {100*(1-np.exp(df.drawdown.min()))}%')

def fetch_data():
    spec = {
        "source": "alphavantage",
        "ticker": "NOG",
        "series": "WEEKLY_ADJUSTED"
    }
    return get_market_data(spec, request=True)

def MA_Crossover(df, short_window, long_window):
    df['Short_MA'] = df['close'].rolling(window=short_window).mean()
    df['Long_MA'] = df['close'].rolling(window=long_window).mean()
    df['signal'] = np.sign(df['Short_MA']-df['Long_MA'])
    df['signal'] = df.signal.shift(1)
    df['signal'] = (df.signal+1)/2
    return df

def format_data(data, datatype):
    match datatype:
        case "av":
            data['close'] = data['adjusted close']
            data = data.drop(columns=['open', 'high', 'low', 'adjusted close', 'volume', 'dividend amount'])
            data['timestamp'] = pd.to_datetime(data['timestamp'])
    return data

def analyze_results(df):
    df['strat_return'] = df.signal*df.log_return
    df['cum_return'] = (df.strat_return).cumsum()
    df['market_cum_return'] = df.log_return.cumsum()
    df['peak'] = df.cum_return.cummax()
    df['drawdown'] = df.cum_return - df.peak
    df['strat_equity'] = np.exp(df.cum_return)
    df['market_equity'] = np.exp(df.log_return.cumsum())
    return df

def train_test_split(data, years=5):
    train = data.loc[data['timestamp'] < data['timestamp'].tail(1).item() - datetime.timedelta(days=365*years)]
    test = data.loc[data['timestamp'] >= data['timestamp'].tail(1).item() - datetime.timedelta(days=365*years)]
    return (train, test)

def add_log_return(df, num_returns=1):
    df['prev_close'] = df['close'].shift(1)
    df['log_return'] = np.log(df.close/df.prev_close)
    if num_returns > 1:
        for i in range(1, num_returns):
            df['log_return_lag' + str(i)] = df.log_return.shift(i)
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

def graph_log_return(df):
    # --- NOW WE GRAPH WITH PLOTLY ---

    # Create a blank figure
    fig = go.Figure()

    # Add the Strategy Equity line
    fig.add_trace(go.Scatter(
        x=df.timestamp, 
        y=df['cum_return'], 
        mode='lines', 
        name='Strategy',
        line=dict(color='limegreen', width=2)
    ))

    # Add the Buy & Hold (Market) Equity line for comparison
    fig.add_trace(go.Scatter(
        x=df.timestamp, 
        y=df['market_cum_return'], 
        mode='lines', 
        name='Buy & Hold (Benchmark)',
        line=dict(color='gray', width=1.5, dash='dash')
    ))

    # Customize the layout (labels, titles, interactive sliders)
    fig.update_layout(
        title='Strategy Performance vs. Buy & Hold',
        xaxis_title='Date',
        yaxis_title='Log returns',
        hovermode='x unified', # Shows values for both lines when hovering
        template='plotly_dark' # Dark mode makes financial charts easier to read
    )

    # Open the chart in your default web browser
    fig.show()

def graph_equity(df):
    fig = go.Figure()

    # Add the Strategy Equity line
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

    # Customize the layout (labels, titles, interactive sliders)
    fig.update_layout(
        title='Strategy Performance vs. Buy & Hold',
        xaxis_title='Date',
        yaxis_title='Equity ($)',
        hovermode='x unified', # Shows values for both lines when hovering
        template='plotly_dark' # Dark mode makes financial charts easier to read
    )

    # Open the chart in your default web browser
    fig.show()

#execution order shenanigans
main()