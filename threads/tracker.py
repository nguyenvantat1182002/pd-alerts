import traceback
import pandas as pd
import talib
import numpy as np

from discord_webhook import DiscordWebhook
from typing import Callable
from PyQt5.QtCore import QThread
from tdv import TradingViewWs


history: dict[str, pd.Timestamp] = {}


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10, multiplier: float = 3.0):
    atr = talib.ATR(high, low, close, timeperiod=period)
    
    hl2 = (high + low) / 2
    upperband = hl2 + multiplier * atr
    lowerband = hl2 - multiplier * atr
    
    final_upperband = upperband.copy()
    final_lowerband = lowerband.copy()

    for i in range(1, len(close)):
        if close[i-1] <= final_upperband[i-1]:
            final_upperband[i] = min(upperband[i], final_upperband[i-1])
        else:
            final_upperband[i] = upperband[i]
            
        if close[i-1] >= final_lowerband[i-1]:
            final_lowerband[i] = max(lowerband[i], final_lowerband[i-1])
        else:
            final_lowerband[i] = lowerband[i]
            
    supertrend = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=int)
    
    for i in range(period, len(close)):
        if close[i] > final_upperband[i-1]:
            direction[i] = 1
        elif close[i] < final_lowerband[i-1]:
            direction[i] = -1
        else:
            direction[i] = direction[i-1]

        supertrend[i] = final_lowerband[i] if direction[i] == 1 else final_upperband[i]

    return supertrend, direction


def handle_candle_update(fetch_webhooks: Callable[[], list[str]], tdv: TradingViewWs, df: pd.DataFrame):
    df['ST'], df['ST_Direction'] = supertrend(df['high'], df['low'], df['close'])
    df['ST'] = np.round(df['ST'] * tdv.price_scale) / tdv.price_scale
    
    reference_candle = df.iloc[-3]
    base_candle = df.iloc[-2]
    timeframe_map = {
        '15': '15m',
        '30': '30m',
        '60': '1h',
        '240': '4h'
    }

    timeframe = timeframe_map[tdv.interval]
    content = f'Symbol: {tdv.symbol_id}\nTimeframe: {timeframe}\nMessage: '
    signal_detected = False
    
    if base_candle['ST_Direction'] > -1 and reference_candle['ST_Direction'] < 1:
        content += 'Price back to P'
        signal_detected = True
    elif base_candle['ST_Direction'] < 1 and reference_candle['ST_Direction'] > -1:
        content += 'Price back to D'
        signal_detected = True
        
    if signal_detected:
        identify = f'{tdv.symbol_id}_{timeframe}'
        if identify in history and history[identify] == base_candle['time']:
            return
        
        history.update({identify: base_candle['time']})
        
        webhooks = fetch_webhooks()
        
        for webhook in webhooks:
            try:
                DiscordWebhook(webhook, content=content).execute()
            except Exception:
                traceback.print_exc()
            
            QThread.msleep(1000)
        
class TrackerThread(QThread):
    def __init__(self):
        super().__init__()
        self.tdv: TradingViewWs = None
        self.fetch_webhooks: list[str] = lambda: []
        
    def run(self):
        self.tdv.realtime_bar_chart(300, lambda *args: handle_candle_update(self.fetch_webhooks, *args))
        