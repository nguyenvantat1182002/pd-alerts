import utils
import pandas as pd
import talib
import numpy as np

from tradingview import TradingViewWs
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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


@dataclass
class PlanResult:
    zone: int
    base_candle: pd.Series
    result: bool
    message: str = field(default=None)
    
class BasePlan(ABC):
    name = 'BasePlan'
    
    def __init__(self, session: TradingViewWs, df: pd.DataFrame):
        self.session = session
        self.df = df
        
    @abstractmethod
    def get_result(self) -> PlanResult:
        pass
    
class PDZonePlan(BasePlan):
    name = 'PDZonePlan'
    
    def __init__(self, session, df):
        super().__init__(session, df)
        
    def get_result(self):
        self.df['ST'], self.df['ST_Direction'] = supertrend(self.df['high'], self.df['low'], self.df['close'])
        self.df['ST'] = np.round(self.df['ST'] * self.session.price_scale) / self.session.price_scale
        
        reference_candle = self.df.iloc[-3]
        base_candle = self.df.iloc[-2]
        
        result = PlanResult(0, base_candle, False)
        
        if base_candle['ST_Direction'] > -1 and reference_candle['ST_Direction'] < 1:
            result.zone = -1
            result.result = True
            result.message = 'Price returns to PREMIUM zone'
        elif base_candle['ST_Direction'] < 1 and reference_candle['ST_Direction'] > -1:
            result.zone = 1
            result.result = True
            result.message = 'Price returns to DISCOUNT zone'
            
        return result
    
class RejectionPlan(BasePlan):
    name = 'RejectionPlan'
    
    def __init__(self, session, df):
        super().__init__(session, df)

    def get_result(self):
        _, symbol = self.session.symbol_id.split(':')
        asset = utils.Asset.get(symbol)
        
        current_candle = self.df.iloc[-1]
        freq_mapping = {
            '60': ['4h', 'D', 'W'],
            '240': ['D', 'W'],
            '4h': '4H',
            'D': 'DAY',
            'W': 'WEEK'
        }
        market_open_mapping = {
            '4h': 4,
            '7h': 7
        }
        
        result = PlanResult(0, current_candle, False)
        
        for freq in freq_mapping[self.session.interval]:
            groups = list(self.df.groupby(pd.Grouper(key='time', freq=freq, offset=asset.market_open)).groups.keys())
            groups = list(map(lambda x: x + pd.Timedelta(days=1, hours=market_open_mapping[asset.market_open]), groups)) if freq == 'W' else groups
            
            period_start = groups[-2 if not freq == 'W' else -3]
            period_end = groups[-1 if not freq == 'W' else -2]
            period_df = self.df[(self.df['time'] >= period_start) & (self.df['time'] <= period_end)]

            first_session_candle = period_df.iloc[-1]
            
            result.base_candle = first_session_candle
            
            period_df = period_df.head(len(period_df) - 1)
            previous_high_candle = period_df.nlargest(1, 'high').iloc[-1]
            previous_low_candle = period_df.nsmallest(1, 'low').iloc[-1]
            
            current_session_candles = self.df[self.df['time'] >= first_session_candle['time']]
            
            if not current_session_candles[current_session_candles['low'] < previous_low_candle['low']].empty \
                    and current_candle['close'] > first_session_candle['open']:
                result.zone = 1
                result.result = True
                result.message = f'Price rejects THE PREVIOUS {freq_mapping[freq]} LOW'
            elif not current_session_candles[current_session_candles['high'] > previous_high_candle['high']].empty \
                    and current_candle['close'] < first_session_candle['open']:
                result.zone = -1
                result.result = True
                result.message = f'Price rejects THE PREVIOUS {freq_mapping[freq]} HIGH'
                
        return result