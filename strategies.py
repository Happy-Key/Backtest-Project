import pandas as pd
import numpy as np

def MA_Crossover(df, short_window, long_window):
    df['Short_MA'] = df.groupby('ticker')['close'].rolling(short_window).mean().reset_index(level=0, drop=True)
    df['Long_MA'] = df.groupby('ticker')['close'].rolling(long_window).mean().reset_index(level=0, drop=True)
    df['signal'] = np.sign(df['Short_MA']-df['Long_MA'])
    df['signal'] = (df.signal+1)/2
    return df.signal

def Bollinger_Band(df, window, width):
    df['MA'] = df.groupby('ticker')['close'].rolling(window).mean().reset_index(level=0, drop=True)
    df['MSD'] = df.groupby('ticker')['close'].rolling(window).std().reset_index(level=0, drop=True)
    df['signal'] = np.select([df.close > df.MA + width*df.MSD, df.close < df.MA - width*df.MSD],[-1,1],0)
    return df.signal

def Momentum_Value_Basket(df, fundamental, numPicks, short_MA, long_MA):
    df = pd.merge(df, fundamental, on=['ticker','timestamp'], how='outer')
    df['EPS'] = df.groupby('ticker')['EPS'].ffill().reset_index(level=0, drop=True)
    df = df.dropna(subset=['close'])
    df['E/P'] = df.EPS / df.close
    df['momentum'] = df.close.rolling(short_MA).mean() / df.close.rolling(long_MA).mean() - 1
    for factor in ["E/P", "momentum"]:
        mean = df[factor].mean()
        std = df[factor].std()
        z_col = f"z_{factor}"
        df[z_col] = (df[factor] - mean) / std
        df[z_col] = df[z_col].clip(lower=-3.0, upper=3.0)
    df["composite_score"] = df["z_E/P"] + df["z_momentum"]
    df['signal'] = 0
    top_indices = df.groupby('timestamp')['composite_score'].nlargest(numPicks).index.get_level_values(-1)
    df.loc[top_indices, 'signal'] = 1
    df = df.dropna()
    return df['signal']