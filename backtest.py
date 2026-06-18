import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from utils import get_market_data, read_parquet

def main():
    print("Tools loaded successfully! Fetching data...")
    data = fetch_data()
    data = format_data(data, "av")
    df = add_log_return(data)
    df = MA_Crossover(df, 3, 10)
    df = df.dropna()

    df['strat_return'] = df.signal*df.log_return
    df['cum_return'] = (df.strat_return).cumsum()
    df['market_cum_return'] = df.log_return.cumsum()
    df['strat_equity'] = np.exp(df.cum_return)
    df['market_equity'] = np.exp(df.log_return.cumsum())

    graph_curves(df, 'cum_return', 'market_cum_return')

    print(f'Strategy log-return: {sum(df.strat_return)}')
    print(f'Strategy ann. sharpe: {np.sqrt(52)*(df.strat_return).mean()/(df.strat_return).std()}')
    print(f'Market log-return: {sum(df.log_return)}')
    print(f'Market ann. sharpe: {np.sqrt(52)*(df.log_return).mean()/(df.log_return).std()}')

def fetch_data():
    spec = {
        "source": "alphavantage",
        "ticker": "AAPL",
        "series": "WEEKLY_ADJUSTED"
    }
    return get_market_data(spec)

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
    return data

def add_log_return(df, num_returns=1):
    df['prev_close'] = df['close'].shift(1)
    df['log_return'] = np.log(df.close/df.prev_close)
    if (num_returns > 1):
        for i in range(num_returns):
            df['log_return_lag' + str(i)] = df.log_return.shift(i)
    return df

def graph_curves(df, strategy_metric, benchmark):
    # --- NOW WE GRAPH WITH PLOTLY ---

    # Create a blank figure
    fig = go.Figure()

    # Add the Strategy Equity line
    fig.add_trace(go.Scatter(
        x=df.timestamp, 
        y=df[strategy_metric], 
        mode='lines', 
        name='Strategy',
        line=dict(color='limegreen', width=2)
    ))

    # Add the Buy & Hold (Market) Equity line for comparison
    fig.add_trace(go.Scatter(
        x=df.timestamp, 
        y=df[benchmark], 
        mode='lines', 
        name='Buy & Hold (Benchmark)',
        line=dict(color='gray', width=1.5, dash='dash')
    ))

    # Customize the layout (labels, titles, interactive sliders)
    fig.update_layout(
        title='Strategy Performance vs. Buy & Hold',
        xaxis_title='Date',
        yaxis_title='Portfolio Value ($)',
        hovermode='x unified', # Shows values for both lines when hovering
        template='plotly_dark' # Dark mode makes financial charts easier to read
    )

    # Open the chart in your default web browser
    fig.show()

#execution order shenanigans
main()