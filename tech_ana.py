from symtable import Symbol
from turtle import color
import requests
import time
import pandas as pd
import ta
import mplfinance as mpf
import ccxt
import dotenv
import os

# load .env
dotenv.load_dotenv('.env')
api_key = os.environ.get("API_KEY")
api_secret = os.environ.get("API_SECRET")

exchange = ccxt.ftx({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True
})

# return finished caldles only (no current candle)


def get_candles(symbol: str, timeframe: str, limit: int = 999):  # 1h 4h 1d
    df = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(df)
    df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    #df = df.astype(float)
    #df.index = pd.to_datetime(df.index, unit='ms')
    return df


def signal(df: pd.DataFrame, rsi_length: int = 14, ema1_length: int = 10, ema2_length: int = 16, reversal_check_length: int = 50):
    # calculate indicator
    df['rsi'] = ta.momentum.rsi(df['close'], window=rsi_length)
    ema1 = ta.trend.EMAIndicator(df['close'], window=ema1_length)
    df['ema1'] = ema1.ema_indicator()
    ema2 = ta.trend.EMAIndicator(df['close'], window=ema2_length)
    df['ema2'] = ema2.ema_indicator()
    # df.dropna(inplace=True)

    # signal
    ema_cross = []
    rsi_ov = []
    for i, r in df.iterrows():
        # check ema cross
        if i > 0:  # skip index 0
            ema1_last = df.iloc[i-1, 7]
            ema2_last = df.iloc[i-1, 8]
            # cross up = 1
            if (ema1_last < ema2_last) & (r['ema1'] > r['ema2']):
                ema_cross.append(1)
            # cross down = 2
            elif (ema1_last > ema2_last) & (r['ema1'] < r['ema2']):
                ema_cross.append(2)
            else:
                ema_cross.append(0)
        else:
            ema_cross.append(0)
        # check rsi over
        if r['rsi'] > 70:  # ovb = 1
            rsi_ov.append(1)
        elif r['rsi'] < 30:  # ovs = 2
            rsi_ov.append(2)
        else:
            rsi_ov.append(0)
    df['ema_cross'] = pd.Series(ema_cross)
    df['rsi_ov'] = pd.Series(rsi_ov)
    # reversal
    reversal = []
    for i, r in df.iterrows():
        if (r['ema_cross'] == 1) & (i > reversal_check_length):  # down => up
            for j in range(i-reversal_check_length, i):
                if (df.iloc[j, 6] < 30):  # up
                    reversal.append(1)
                    break
                if (j == i-1):
                    reversal.append(0)
        elif (r['ema_cross'] == 2) & (i > reversal_check_length):  # up => down
            for j in range(i-reversal_check_length, i):
                if (df.iloc[j, 6] > 70):
                    reversal.append(2)  # down
                    break
                if (j == i-1):
                    reversal.append(0)
        else:
            reversal.append(0)
    df['reversal'] = pd.Series(reversal)
    return df


def plot(df: pd.DataFrame, symbol: str):
    # setup
    sig_up = df.query('reversal == 1')
    sig_down = df.query('reversal == 2')
    vl_up = dict(
        vlines=sig_up["datetime"].tolist(), linewidths=1, colors='g')
    vl_down = dict(
        vlines=sig_down["datetime"].tolist(), linewidths=1, colors='r')
    df = df.set_index('datetime')

    # Plot
    mpf.plot(df, type='candle', volume=False,
             title="\n"+symbol+"\nBottom Signals", style='yahoo', vlines=vl_up)
    mpf.plot(df, type='candle', volume=False,
             title="\n"+symbol+"\nTop Signals", style='yahoo', vlines=vl_down)


symbol = "SOL/USDT"
df = get_candles(symbol, '4h', 500)
df = signal(df, 14, 10, 20, 50)
df.to_csv("t.csv")
plot(df, symbol)


# EMA10 & 15 cross + rsi backward check + chg%
