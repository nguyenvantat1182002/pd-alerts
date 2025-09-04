import pandas as pd
from typing import Optional


class SignalHistory:
    data: dict[str, pd.Timestamp] = {}

    @staticmethod
    def update(key: str, value: pd.Timestamp):
        SignalHistory.data.update({key: value})

    @staticmethod
    def get(key: str) -> Optional[pd.Timestamp]:
        return SignalHistory.data.get(key)
    