import os
import json

from typing import Optional
from dataclasses import dataclass


ASSETS_PATH = os.path.join(os.getcwd(), 'assets.json')
TIMEFRAME_MAPPING = {
    '15m': '15',
    '30m': '30',
    '1h': '60',
    '4h': '240',
    '15': '15m',
    '30': '30m',
    '60': '1h',
    '240': '4h'
}


@dataclass
class Asset:
    name: str
    exchanges: list[str]
    market_open: str
    
    @staticmethod
    def get(name: str) -> Optional['Asset']:
        assets = Asset.read()
        return assets.get(name)
    
    @staticmethod
    def read() -> dict[str, 'Asset']:
        assets = {}

        if os.path.exists(ASSETS_PATH):
            with open(ASSETS_PATH, encoding='utf-8') as file:
                data: dict = json.load(file)

                for k, v in data.items():
                    assets.update({k: Asset(k, **v)})
                    
        return assets
    