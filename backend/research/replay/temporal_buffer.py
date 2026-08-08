"""
WealthQuant V10.0 — Point-in-Time Temporal Buffer
=================================================
Enforces strict temporal isolation. For any given replay timestamp T_k,
only data with timestamp <= T_k is exposed to the simulation.
Prevents look-ahead bias completely.
"""

import logging
from datetime import datetime

import pandas as pd

logger = logging.getLogger("replay.temporal")


class PointInTimeBuffer:
    """
    In-memory point-in-time filter for historical data streams.
    """

    def __init__(
        self, full_ohlcv: pd.DataFrame, full_options: pd.DataFrame | None = None
    ):
        self.full_ohlcv = (
            full_ohlcv.sort_index() if not full_ohlcv.empty else pd.DataFrame()
        )
        self.full_options = (
            full_options.sort_index()
            if full_options is not None and not full_options.empty
            else pd.DataFrame()
        )

    def get_slice_at(self, cutoff_time: datetime) -> dict[str, pd.DataFrame]:
        """
        Extract only historical rows up to cutoff_time (inclusive).
        Strictly excludes any row with timestamp > cutoff_time.
        """
        ohlcv_slice = (
            self.full_ohlcv[self.full_ohlcv.index <= cutoff_time]
            if not self.full_ohlcv.empty
            else pd.DataFrame()
        )
        options_slice = (
            self.full_options[self.full_options.index <= cutoff_time]
            if not self.full_options.empty
            else pd.DataFrame()
        )

        return {
            "ohlcv": ohlcv_slice,
            "options": options_slice,
            "cutoff_time": cutoff_time,
        }
