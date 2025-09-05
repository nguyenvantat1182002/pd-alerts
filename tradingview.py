import traceback
import time
import json
import random
import string
import re
import pandas as pd

from collections import OrderedDict
from typing import List, Union, Callable, Self
from websocket import WebSocketApp


class TradingViewWs():
    def __init__(self, symbol_id: str, interval: Union[int, str], timezone: str = 'Asia/Ho_Chi_Minh'):
        self.symbol_id = symbol_id
        self.interval = interval
        self.timezone = timezone
        self.candles: OrderedDict[float, List[float]] = OrderedDict()
        self.price_scale = 0
        self.ws = None

    def close(self):
        self.ws.close()
        
    def generate_session(self, type: str) -> str:
        string_length = 12
        letters = string.ascii_lowercase
        random_string = "".join(random.choice(letters) for _ in range(string_length))
        return type + random_string
    
    def prepend_header(self, text: str) -> str:
        return "~m~" + str(len(text)) + "~m~" + text
    
    def construct_message(self, func: str, param_list: list) -> str:
        return json.dumps({"m": func, "p": param_list}, separators=(",", ":"))
    
    def create_message(self, func: str, param_list: list) -> str:
        return self.prepend_header(self.construct_message(func, param_list))
    
    def send_message(self, ws: WebSocketApp, func: str, param_list: list):
        ws.send(self.create_message(func, param_list))
        
    def realtime_bar_chart(self, total_candle: int, callback: Callable[[Self, pd.DataFrame], None]):
        def on_open(ws: WebSocketApp):
            session = self.generate_session("qs_")
            chart_session = self.generate_session("cs_")
            
            self.send_message(ws, "set_auth_token", ["unauthorized_user_token"])
            self.send_message(ws, "chart_create_session", [chart_session, ""])
            self.send_message(ws, "quote_create_session", [session])
            self.send_message(ws, "quote_set_fields", [session, "ch", "chp", "current_session", "description", "local_description", "language", "exchange", "fractional", "is_tradable", "lp", "lp_time", "minmov", "minmove2", "original_name", "pricescale", "pro_name", "short_name", "type", "update_mode", "volume", "currency_code", "rchp", "rtc"])
            self.send_message(ws, "resolve_symbol", [chart_session, "symbol_1", "={\"symbol\":\"" + self.symbol_id + "\",\"adjustment\":\"splits\",\"session\":\"extended\"}"])
            self.send_message(ws, "create_series", [chart_session, "s1", "s1", "symbol_1", str(self.interval), total_candle])
            self.send_message(ws, "set_future_tickmarks_mode", [chart_session, "full_single_session"])
            
        def on_close(ws: WebSocketApp, close_status_code: int, close_msg: str):
            print(self.symbol_id, self.interval, close_status_code, close_msg)
            
            if close_status_code is None:
                return
            
            time.sleep(5)
            
            self.realtime_bar_chart(total_candle, callback)
            
        def on_message(ws: WebSocketApp, message: str):
            if message[7:].startswith('~h~'): # ping
                ws.send(self.prepend_header(message[7:]))
                
            if not self.price_scale:
                price_scale = re.findall(r'"pricescale":(\d+)', message)
                if not price_scale:
                    return
                self.price_scale = int(price_scale[0])
                    
            data = re.findall(r'"s":(\[.*?}\])', message)
            if not data:
                return
            
            data = data[-1]
            items = json.loads(data)
            
            if len(self.candles) >= total_candle:
                for _ in range(len(self.candles) - total_candle):
                    self.candles.popitem(last=False)
                    
            for item in items:
                self.candles.update({item['v'][0]: item['v']})
                
            df = pd.DataFrame(self.candles.values(), columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert(self.timezone)
            df['time'] = df['time'].dt.tz_localize(None)
            
            callback(df)

        def on_error(ws: WebSocketApp, error: Exception):
            print('Error', error)
            

        self.ws = WebSocketApp('wss://data.tradingview.com/socket.io/websocket',
                               header={"Origin": "https://data.tradingview.com"},
                               on_message=on_message,
                               on_close=on_close,
                               on_open=on_open,
                               on_error=on_error)
        self.ws.run_forever()
        