"""
╔══════════════════════════════════════════════════════════════════════════╗
║  WealthQuant — PredictionStore                                           ║
║                                                                          ║
║  MISSION: Institutional-grade prediction locking and versioning.         ║
║                                                                          ║
║  Rules:                                                                  ║
║    - Every prediction gets a UUID, created_at, valid_until, state        ║
║    - States: GENERATING → LOCKED → LIVE → EXPIRED → EVALUATED           ║
║    - Never regenerate a prediction while it is LIVE                      ║
║    - Lock is bound to the current candle boundary (interval-aware)       ║
║    - Thread-safe: all mutations protected by threading.Lock              ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import copy
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("wealthquant.prediction_store")

# ── Timezone ──────────────────────────────────────────────────────────────
try:
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")
except ImportError:
    try:
        import pytz

        IST = pytz.timezone("Asia/Kolkata")
    except ImportError:
        IST = timezone(timedelta(hours=5, minutes=30))


# ── Prediction States ─────────────────────────────────────────────────────
class PredictionState:
    GENERATING = "GENERATING"
    LOCKED = "LOCKED"
    LIVE = "LIVE"
    EXPIRED = "EXPIRED"
    EVALUATED = "EVALUATED"


# ── Interval → minutes map ────────────────────────────────────────────────
_INTERVAL_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "1d": 1440,
}


def _now_ist() -> datetime:
    """Current datetime in IST."""
    try:
        return datetime.now(IST)
    except Exception:
        return datetime.utcnow() + timedelta(hours=5, minutes=30)


def _next_candle_close(interval: str, base_dt: datetime | None = None) -> datetime:
    """
    Compute the next candle close timestamp for the given interval.
    Example: at 09:17 IST with interval=15m → next close = 09:30 IST
    """
    now = base_dt or _now_ist()
    minutes = _INTERVAL_MINUTES.get(interval, 15)
    # Floor to current candle boundary
    total_minutes = now.hour * 60 + now.minute
    current_candle_start_minutes = (total_minutes // minutes) * minutes
    next_close_minutes = current_candle_start_minutes + minutes
    # Build the next close datetime
    next_close = now.replace(
        hour=next_close_minutes // 60,
        minute=next_close_minutes % 60,
        second=0,
        microsecond=0,
    )
    return next_close


def _candle_id(interval: str, base_dt: datetime | None = None) -> str:
    """
    Returns a string key identifying the current candle boundary.
    Used as a stable hash to detect candle transitions.
    Example: '15m:2026-07-19T09:15'
    """
    now = base_dt or _now_ist()
    minutes = _INTERVAL_MINUTES.get(interval, 15)
    total_minutes = now.hour * 60 + now.minute
    candle_start = (total_minutes // minutes) * minutes
    candle_dt = now.replace(
        hour=candle_start // 60,
        minute=candle_start % 60,
        second=0,
        microsecond=0,
    )
    return f"{interval}:{candle_dt.strftime('%Y-%m-%dT%H:%M')}"


# ── Prediction Record ─────────────────────────────────────────────────────
class PredictionRecord:
    """Represents a single locked prediction for a symbol+interval."""

    __slots__ = (
        "prediction_id",
        "symbol",
        "interval",
        "created_at",
        "valid_until",
        "candle_id",
        "state",
        "data",
        "latency_ms",
    )

    def __init__(
        self,
        symbol: str,
        interval: str,
        data: dict,
        latency_ms: float = 0.0,
        base_dt: datetime | None = None,
    ):
        self.prediction_id = str(uuid.uuid4())
        self.symbol = symbol
        self.interval = interval
        self.created_at = _now_ist()
        self.valid_until = _next_candle_close(interval, base_dt=base_dt)
        self.candle_id = _candle_id(interval, base_dt=base_dt)
        self.state = PredictionState.LIVE
        self.data = copy.deepcopy(data) if data else {}
        self.latency_ms = latency_ms

    def is_live(self) -> bool:
        """True if prediction is still valid for the current candle."""
        return (
            self.state == PredictionState.LIVE
            and _now_ist() < self.valid_until
            and self.candle_id == _candle_id(self.interval)
        )

    def age_seconds(self) -> float:
        """How many seconds since this prediction was generated."""
        delta = _now_ist() - self.created_at
        return delta.total_seconds()

    def seconds_remaining(self) -> float:
        """How many seconds until this prediction expires."""
        delta = self.valid_until - _now_ist()
        return max(0.0, delta.total_seconds())

    def to_metadata(self) -> dict:
        """Return prediction versioning metadata for API responses."""
        return {
            "prediction_id": self.prediction_id,
            "created_at": self.created_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "prediction_state": self.state,
            "prediction_version": f"{self.symbol}-{self.interval}-{self.candle_id}",
            "age_seconds": round(self.age_seconds(), 1),
            "seconds_remaining": round(self.seconds_remaining(), 1),
            "latency_ms": round(self.latency_ms, 1),
        }

    def expire(self):
        """Mark this prediction as expired."""
        self.state = PredictionState.EXPIRED
        logger.debug(
            f"[PredictionStore] {self.symbol}/{self.interval} "
            f"prediction {self.prediction_id[:8]} → EXPIRED"
        )

    def mark_evaluated(self):
        """Mark this prediction as evaluated (outcome known)."""
        self.state = PredictionState.EVALUATED


# ── Prediction Store ──────────────────────────────────────────────────────
class PredictionStore:
    """
    Global in-memory store for locked predictions.

    Key guarantee: if a prediction is LIVE, it will NOT be regenerated
    until the candle closes (interval boundary is crossed).
    """

    def __init__(self):
        self._store: dict[str, PredictionRecord] = {}  # key: "{symbol}:{interval}"
        self._lock = threading.RLock()
        self._stats = {
            "total_generated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }
        logger.info("[PredictionStore] Initialized — prediction locking active.")

    def _key(self, symbol: str, interval: str, namespace: str = "default") -> str:
        return f"{namespace}:{symbol.upper()}:{interval}"

    def get_live(
        self, symbol: str, interval: str, namespace: str = "default"
    ) -> PredictionRecord | None:
        """
        Return the current live prediction for symbol+interval, or None
        if no live prediction exists (caller must generate a new one).
        """
        key = self._key(symbol, interval, namespace)
        with self._lock:
            rec = self._store.get(key)
            if rec and rec.is_live():
                self._stats["cache_hits"] += 1
                return rec
            elif rec:
                rec.expire()
            self._stats["cache_misses"] += 1
            return None

    def lock(
        self,
        symbol: str,
        interval: str,
        data: dict,
        latency_ms: float = 0.0,
        namespace: str = "default",
    ) -> PredictionRecord:
        """
        Create and lock a new prediction record.
        Called immediately after a fresh prediction is generated.
        """
        key = self._key(symbol, interval, namespace)
        rec = PredictionRecord(symbol, interval, data, latency_ms)
        with self._lock:
            # Expire old prediction if any
            old = self._store.get(key)
            if old:
                old.expire()
            self._store[key] = rec
            self._stats["total_generated"] += 1
        logger.info(
            f"[PredictionStore] 🔒 LOCKED {symbol}/{interval} | "
            f"id={rec.prediction_id[:8]} | "
            f"valid_until={rec.valid_until.strftime('%H:%M:%S IST')} | "
            f"latency={latency_ms:.0f}ms"
        )
        return rec

    def get_metadata(
        self, symbol: str, interval: str, namespace: str = "default"
    ) -> dict | None:
        """Return prediction metadata without the full data payload."""
        key = self._key(symbol, interval, namespace)
        with self._lock:
            rec = self._store.get(key)
            return rec.to_metadata() if rec else None

    def expire_all_stale(self):
        """Expire any stale predictions (call periodically from scheduler)."""
        with self._lock:
            for rec in self._store.values():
                if rec.state == PredictionState.LIVE and not rec.is_live():
                    rec.expire()

    def expire_immediately(
        self,
        symbol: str,
        interval: str = "5m",
        reason: str = "EMERGENCY_OVERRIDE",
        namespace: str = "default",
    ) -> bool:
        """Emergency override: expire a live prediction immediately before valid_until."""
        key = self._key(symbol, interval, namespace)
        with self._lock:
            rec = self._store.get(key)
            if rec:
                rec.expire()
                logger.warning(
                    f"[PredictionStore] 🚨 EMERGENCY OVERRIDE for {namespace}:{symbol}/{interval} "
                    f"Reason: {reason}"
                )
                return True
        return False

    def stats(self) -> dict:
        """Return store health statistics."""
        with self._lock:
            total = self._stats["cache_hits"] + self._stats["cache_misses"]
            hit_ratio = (
                round(self._stats["cache_hits"] / total, 4) if total > 0 else 0.0
            )
            live_count = sum(
                1 for r in self._store.values() if r.state == PredictionState.LIVE
            )
            return {
                **self._stats,
                "hit_ratio": hit_ratio,
                "live_count": live_count,
                "total_slots": len(self._store),
            }

    def all_live(self) -> list[dict]:
        """Return metadata for all currently live predictions."""
        with self._lock:
            return [
                rec.to_metadata()
                for rec in self._store.values()
                if rec.state == PredictionState.LIVE and rec.is_live()
            ]


# ── Singleton ─────────────────────────────────────────────────────────────
prediction_store = PredictionStore()
