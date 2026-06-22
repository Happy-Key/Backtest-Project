import pandas as pd
import numpy as np

def MA_Crossover(df, short_window, long_window):
    df['Short_MA'] = df['close'].rolling(short_window).mean()
    df['Long_MA'] = df['close'].rolling(long_window).mean()
    df['signal'] = np.sign(df['Short_MA']-df['Long_MA'])
    df['signal'] = (df.signal+1)/2
    return df

def Bollinger_Band(df, window, width):
    df['MA'] = df['close'].rolling(window).mean()
    df['MSD'] = df['close'].rolling(window).std()
    df['signal'] = np.select([df.close > df.MA + width*df.MSD, df.close < df.MA - width*df.MSD],[-1,1],0)
    return df