import json
from datetime import date, datetime

import numpy as np
import pandas as pd
from pydantic import BaseModel


class CustomJSONEncoder(json.JSONEncoder):
    """
    Unified JSON Encoder to handle:
    - numpy types (int, float, array)
    - pandas types (Timestamp, NaT, DataFrame, Series)
    - datetime / date
    - NaN / Inf values (converts to None)
    - pydantic Models
    - sets
    """

    def default(self, obj):
        if pd.isna(obj):  # Handles np.nan, pd.NaT, None safely
            return None
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (datetime, date, pd.Timestamp)):
            return obj.isoformat()
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        if isinstance(obj, (pd.Series, pd.DataFrame)):
            return obj.to_dict()
        if isinstance(obj, float):
            if np.isnan(obj) or np.isinf(obj):
                return None
        return super().default(obj)


def json_dumps(obj, **kwargs):
    """Unified json.dumps wrapper"""
    kwargs.setdefault("cls", CustomJSONEncoder)
    return json.dumps(obj, **kwargs)
