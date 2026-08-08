"""
test_scheduler.py — Pillar 4: Scheduler Non-Reentrancy & Task Health Tests
"""

from pipeline.scheduler import scheduler as wq_scheduler


def test_scheduler_status():
    """Verify scheduler status method returns valid metrics dict."""
    status = wq_scheduler.status()
    assert isinstance(status, dict)
    assert "is_running" in status
    assert "last_ingestion" in status
    assert "rows_added_today" in status


def test_recorder_latencies_bounded_deque():
    """Verify scheduler latency tracking uses a bounded deque (maxlen=1000)."""
    state = wq_scheduler._state
    assert hasattr(state, "recorder_latencies")

    # Append 1,500 test latency numbers
    for i in range(1500):
        state.recorder_latencies.append(float(i))

    assert len(state.recorder_latencies) <= 1000
    assert state.recorder_latencies[-1] == 1499.0
