"""Centralized debug logging and network tracking service."""

import json
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from functools import wraps

from src.core.logging_config import get_logger
from src.core.di import Container
from src.state.store import Store
from src.core.debug.models import LogLevel, NetworkRequest, LogEntry, DebugConfig

logger = get_logger("debug")


class DebugService:
    """Service for managing application logs and tracking."""

    _instance: Optional["DebugService"] = None

    def __new__(cls) -> "DebugService":
        if cls._instance is None:
            cls._instance = super(DebugService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._initialized = True
        self.config = DebugConfig(enabled=True)
        self._log_entries: deque = deque(maxlen=1000)
        self._network_requests: deque = deque(maxlen=100)
        self._performance_metrics: Dict[str, List[float]] = {}
        self._subscribers: List[Callable[[LogEntry], None]] = []
        self._network_subscribers: List[Callable[[NetworkRequest], None]] = []
        self._start_times: Dict[str, float] = {}

        # Self-tracking
        self.info("DebugService", f"Initialized (ID: {id(self)})")

    def configure(self, config: DebugConfig) -> None:
        """Update service configuration."""
        self.config = config
        self.info("DebugService", "Configuration updated")

    def _should_log(self, level: LogLevel) -> bool:
        if not self.config.enabled:
            return False

        level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.NETWORK: 1,
            LogLevel.PERFORMANCE: 1,
            LogLevel.INFO: 2,
            LogLevel.WARNING: 3,
            LogLevel.ERROR: 4,
        }

        try:
            config_val = (
                LogLevel(self.config.log_level.lower())
                if isinstance(self.config.log_level, str)
                else LogLevel.INFO
            )
        except ValueError:
            config_val = LogLevel.INFO

        config_level = level_order.get(config_val, 2)
        if level in (LogLevel.NETWORK, LogLevel.PERFORMANCE):
            return getattr(self.config, f"{level.value}_tracking", True)

        return level_order.get(level, 0) >= config_level

    def log(self, level: LogLevel, source: str, message: str, data: Optional[Dict] = None) -> None:
        if not self._should_log(level):
            return
        entry = LogEntry(
            timestamp=time.time(), level=level, source=source, message=message, data=data
        )
        self._log_entries.append(entry)
        self._notify_subscribers(entry)
        self._write_to_file(entry)

    def debug(self, src: str, msg: str, data: Optional[Dict] = None):
        self.log(LogLevel.DEBUG, src, msg, data)

    def info(self, src: str, msg: str, data: Optional[Dict] = None):
        self.log(LogLevel.INFO, src, msg, data)

    def warning(self, src: str, msg: str, data: Optional[Dict] = None):
        self.log(LogLevel.WARNING, src, msg, data)

    def error(self, src: str, msg: str, data: Optional[Dict] = None):
        self.log(LogLevel.ERROR, src, msg, data)

    def network_start(self, req_id: str, method: str, endpoint: str, params: Optional[Dict] = None):
        if not self.config.enabled or not self.config.network_tracking:
            return
        self._start_times[req_id] = time.time()
        req = NetworkRequest(
            id=req_id, timestamp=time.time(), method=method, endpoint=endpoint, params=params or {}
        )
        self._network_requests.append(req)
        self._notify_network_subscribers(req)
        # Noise reduction: NETWORK and PERFORMANCE events don't go to standard logs

    def network_end(
        self,
        req_id: str,
        status_code: Optional[int] = None,
        size: Optional[int] = None,
        error: Optional[str] = None,
        body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        if not self.config.enabled or not self.config.network_tracking:
            return
        start = self._start_times.pop(req_id, None)
        dur = (time.time() - start) * 1000 if start else None
        target = next((r for r in self._network_requests if r.id == req_id), None)
        if target:
            target.duration_ms = dur
            target.status_code = status_code
            target.response_size = size
            target.error = error
            target.response_body = body
            target.headers = headers
            self._notify_network_subscribers(target)

    def track_performance(self, op: str, dur: float):
        if not self.config.enabled or not self.config.performance_tracking:
            return
        if op not in self._performance_metrics:
            self._performance_metrics[op] = []
        self._performance_metrics[op].append(dur)
        if len(self._performance_metrics[op]) > 100:
            self._performance_metrics[op] = self._performance_metrics[op][-100:]
        # Reduced noise: don't log to standard logs

    def get_log_entries(self, limit: int = 100):
        return list(self._log_entries)[-limit:]

    def get_network_history(self, limit: int = 50):
        return list(self._network_requests)[-limit:]

    def get_performance_stats(self):
        return {
            op: {
                "count": len(t),
                "avg_ms": sum(t) / len(t),
                "min_ms": min(t),
                "max_ms": max(t),
                "last_ms": t[-1],
            }
            for op, t in self._performance_metrics.items()
            if t
        }

    def clear_logs(self):
        self._log_entries.clear()

    def clear_network_history(self):
        self._network_requests.clear()

    def subscribe(self, cb):
        self._subscribers.append(cb)

    def unsubscribe(self, cb):
        if cb in self._subscribers:
            self._subscribers.remove(cb)

    def subscribe_network(self, cb):
        self._network_subscribers.append(cb)

    def unsubscribe_network(self, cb):
        if cb in self._network_subscribers:
            self._network_subscribers.remove(cb)

    def _notify_subscribers(self, entry: LogEntry):
        try:
            store = Container.resolve(Store)
            store.set("debug_log_count", len(self._log_entries))
        except:
            pass
        for cb in self._subscribers:
            try:
                cb(entry)
            except:
                pass

    def _notify_network_subscribers(self, req: NetworkRequest):
        try:
            store = Container.resolve(Store)
            store.set("debug_net_count", len(self._network_requests))
        except:
            pass
        for cb in self._network_subscribers:
            try:
                cb(req)
            except:
                pass

    def _write_to_file(self, entry: LogEntry):
        if not self.config.log_to_file:
            return
        try:
            p = Path(self.config.log_file_path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            ts = datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            line = f"[{ts}] [{entry.level.value.upper()}] [{entry.source}] {entry.message}\n"
            with open(p, "a") as f:
                f.write(line)
        except:
            pass

    def format_entry(self, entry: LogEntry) -> str:
        ts = datetime.fromtimestamp(entry.timestamp).strftime("%H:%M:%S.%f")[:-3]
        colors = {
            LogLevel.DEBUG: "#6c7086",
            LogLevel.INFO: "#89b4fa",
            LogLevel.WARNING: "#fab387",
            LogLevel.ERROR: "#f38ba8",
            LogLevel.NETWORK: "#a6e3a1",
            LogLevel.PERFORMANCE: "#cba6f7",
        }
        color = colors.get(entry.level, "#cdd6f4")
        line = f"[{color}][{ts}][{entry.level.value.upper()}][{entry.source}][/] {entry.message}"
        if entry.data and not self.config.compact_mode:
            try:
                line += f"\n[dim]{json.dumps(entry.data, indent=2, default=str)}[/]"
            except:
                line += f"\n[dim]{str(entry.data)}[/]"
        return line
