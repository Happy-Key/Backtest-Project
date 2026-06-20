import pandas as pd
import numpy as np

def MA_Crossover(df, short_window, long_window):
    df['Short_MA'] = df['close'].rolling(window=short_window).mean()
    df['Long_MA'] = df['close'].rolling(window=long_window).mean()
    df['signal'] = np.sign(df['Short_MA']-df['Long_MA'])
    df['signal'] = df.signal.shift(1)
    df['signal'] = (df.signal+1)/2
    return df

