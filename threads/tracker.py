import queue
import os
import traceback
import pandas as pd
import utils

from discord_webhook import DiscordWebhook
from PyQt5.QtCore import QThread, QRunnable, QThreadPool, QMutex, QMutexLocker
from tradingview import TradingViewWs

from .plan import PDZonePlan, RejectionPlan, BasePlan


def get_webhooks() -> list[str]:
    file_path = os.path.join(os.getcwd(), 'webhooks.txt')
    if not os.path.exists(file_path):
        return []
    
    with open(file_path, encoding='utf-8') as file:
        return file.read().splitlines()
    

class TrackerThread(QThread):
    def __init__(self):
        super().__init__()
        self.sessions: queue.Queue[TradingViewWs] = queue.Queue()
        self.mutex = QMutex()
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(999)
        
    def run(self):
        while 1:
            try:
                if self.sessions.empty():
                    continue

                session = self.sessions.get_nowait()
                
                self.pool.start(TrackerRunnable(self, session))
            finally:
                QThread.msleep(1000)
                
class TrackerRunnable(QRunnable):
    def __init__(self, parent: TrackerThread, session: TradingViewWs):
        super().__init__()
        self.parent = parent
        self.session = session

    def handle_candle_update(self, df: pd.DataFrame):
        parameters = (self.session, df)
        plans: list[BasePlan] = [PDZonePlan(*parameters), RejectionPlan(*parameters)]
        
        for plan in plans:
            if self.session.interval in ['15', '30'] and isinstance(plan, RejectionPlan):
                continue
            
            result = plan.get_result()
            if not result.result:
                continue
            
            zone_mapping = {
                -1: f'- {result.message}',
                1: f'+ {result.message}'
            }
            
            timeframe = utils.TIMEFRAME_MAPPING[self.session.interval]
            identify = f'{self.session.symbol_id}_{timeframe}'
            content = f'Symbol: {self.session.symbol_id}\nTimeframe: {timeframe}\n\n{zone_mapping[result.zone]}'
            
            previous_signal_time = plan.history.get(identify)
            if previous_signal_time is not None:
                if isinstance(plan, PDZonePlan) and previous_signal_time == result.base_candle['time']:
                    continue
                elif isinstance(plan, RejectionPlan):
                    previous_signal_time = plan.history[identify].get(result.zone, None)
                    if previous_signal_time is not None and previous_signal_time == result.base_candle['time']:
                        continue
                    
            webhooks = get_webhooks()
            
            for url in webhooks:
                try:
                    DiscordWebhook(url, content=f'```diff\n{content}\n```').execute()
                except Exception:
                    traceback.print_exc()
                
                QThread.msleep(1000)
                
            with QMutexLocker(self.parent.mutex):
                if isinstance(plan, PDZonePlan):
                    PDZonePlan.history.update({identify: result.base_candle['time']})
                elif isinstance(plan, RejectionPlan):
                    RejectionPlan.history.update({identify: {result.zone: result.base_candle['time']}})
                    
    def run(self):
        self.session.realtime_bar_chart(500, self.handle_candle_update)
        