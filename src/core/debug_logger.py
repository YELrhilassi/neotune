"""Integrated debugging and network tracking module."""

import json
import time
from collections import deque
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from functools import wraps

from src.core.logging_config import get_logger

logger = get_logger("debug")


class LogLevel(Enum):
    """Log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    NETWORK = "network"
    PERFORMANCE = "performance"


@dataclass
class NetworkRequest:
    """Represents a network request for tracking."""

    id: str
    timestamp: float
    method: str
    endpoint: str
    params: Dict[str, Any]
    duration_ms: Optional[float] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
    response_size: Optional[int] = None


@dataclass
class LogEntry:
    """Represents a single log entry."""

    timestamp: float
    level: LogLevel
    source: str
    message: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class DebugConfig:
    """Configuration for debugging features."""

    enabled: bool = True
    network_tracking: bool = True
    performance_tracking: bool = True
    log_to_file: bool = False
    log_file_path: str = "~/.config/spotify-tui/debug.log"
    max_log_entries: int = 1000
    max_network_history: int = 100
    log_level: str = "info"
    auto_scroll: bool = True
    show_timestamps: bool = True
    compact_mode: bool = False

    def from_lua(self, config: Dict[str, Any]) -> None:
        """Load configuration from Lua table."""
        for key in asdict(self).keys():
            if config.get(key) is not None:
                setattr(self, key, config.get(key))


class DebugLogger:
    """Centralized debug logging and network tracking."""

    _instance: Optional["DebugLogger"] = None

    def __new__(cls) -> "DebugLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.config = DebugConfig()
        self._log_entries: deque = deque(maxlen=1000)
        self._network_requests: deque = deque(maxlen=100)
        self._performance_metrics: Dict[str, List[float]] = {}
        self._subscribers: List[Callable[[LogEntry], None]] = []
        self._network_subscribers: List[Callable[[NetworkRequest], None]] = []
        self._start_times: Dict[str, float] = {}

    def configure(self, config: DebugConfig) -> None:
        """Configure the debug logger."""
        self.config = config
        self._log_entries = deque(maxlen=config.max_log_entries)
        self._network_requests = deque(maxlen=config.max_network_history)
        self.info("DebugLogger", "Debug logging configured")

    def is_enabled(self) -> bool:
        """Check if debugging is enabled."""
        return self.config.enabled

    def _should_log(self, level: LogLevel) -> bool:
        """Check if a log level should be logged based on config."""
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

        # Safe lookup for log level
        try:
            config_val = LogLevel(self.config.log_level.lower())
        except ValueError:
            config_val = LogLevel.INFO

        config_level = level_order.get(config_val, 2)
        return level_order.get(level, 0) >= config_level

    def _create_entry(
        self, level: LogLevel, source: str, message: str, data: Optional[Dict] = None
    ) -> LogEntry:
        """Create a log entry."""
        return LogEntry(
            timestamp=time.time(), level=level, source=source, message=message, data=data
        )

    def _notify_subscribers(self, entry: LogEntry) -> None:
        """Notify all subscribers of a new log entry."""
        for subscriber in self._subscribers:
            try:
                subscriber(entry)
            except Exception as e:
                logger.error(f"Error notifying log subscriber: {e}")

    def _notify_network_subscribers(self, request: NetworkRequest) -> None:
        """Notify all subscribers of a network request."""
        for subscriber in self._network_subscribers:
            try:
                subscriber(request)
            except Exception as e:
                logger.error(f"Error notifying network subscriber: {e}")

    def _write_to_file(self, entry: LogEntry) -> None:
        """Write log entry to file if enabled."""
        if not self.config.log_to_file:
            return

        try:
            log_path = Path(self.config.log_file_path).expanduser()
            log_path.parent.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")[
                :-3
            ]
            line = f"[{timestamp}] [{entry.level.value.upper()}] [{entry.source}] {entry.message}"
            if entry.data:
                line += f" | Data: {json.dumps(entry.data, default=str)}"
            line += "\n"

            with open(log_path, "a") as f:
                f.write(line)
        except Exception as e:
            logger.error(f"Error writing to debug log file: {e}")

    def log(self, level: LogLevel, source: str, message: str, data: Optional[Dict] = None) -> None:
        """Log a message."""
        if not self._should_log(level):
            return

        entry = self._create_entry(level, source, message, data)
        self._log_entries.append(entry)
        self._notify_subscribers(entry)
        self._write_to_file(entry)

    def debug(self, source: str, message: str, data: Optional[Dict] = None) -> None:
        """Log a debug message."""
        self.log(LogLevel.DEBUG, source, message, data)

    def info(self, source: str, message: str, data: Optional[Dict] = None) -> None:
        """Log an info message."""
        self.log(LogLevel.INFO, source, message, data)

    def warning(self, source: str, message: str, data: Optional[Dict] = None) -> None:
        """Log a warning message."""
        self.log(LogLevel.WARNING, source, message, data)

    def error(self, source: str, message: str, data: Optional[Dict] = None) -> None:
        """Log an error message."""
        self.log(LogLevel.ERROR, source, message, data)

    def network_start(
        self, request_id: str, method: str, endpoint: str, params: Optional[Dict] = None
    ) -> None:
        """Start tracking a network request."""
        if not self.config.enabled or not self.config.network_tracking:
            return

        self._start_times[request_id] = time.time()

        request = NetworkRequest(
            id=request_id,
            timestamp=time.time(),
            method=method,
            endpoint=endpoint,
            params=params or {},
        )

        self._network_requests.append(request)
        self._notify_network_subscribers(request)

        self.log(
            LogLevel.NETWORK,
            "Network",
            f"Request started: {method} {endpoint}",
            {"request_id": request_id, "params": params},
        )

    def network_end(
        self,
        request_id: str,
        status_code: Optional[int] = None,
        response_size: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """End tracking a network request."""
        if not self.config.enabled or not self.config.network_tracking:
            return

        start_time = self._start_times.pop(request_id, None)
        duration_ms = (time.time() - start_time) * 1000 if start_time else None

        # Find and update the request
        target_req = None
        for req in self._network_requests:
            if req.id == request_id:
                req.duration_ms = duration_ms
                req.status_code = status_code
                req.response_size = response_size
                req.error = error
                target_req = req
                break

        if target_req:
            self._notify_network_subscribers(target_req)

        if error:
            self.log(
                LogLevel.NETWORK,
                "Network",
                f"Request failed: {error}",
                {"request_id": request_id, "duration_ms": duration_ms},
            )
        else:
            self.log(
                LogLevel.NETWORK,
                "Network",
                f"Request completed: {status_code} in {duration_ms:.2f}ms",
                {
                    "request_id": request_id,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "size": response_size,
                },
            )

    def track_performance(self, operation: str, duration_ms: float) -> None:
        """Track performance metrics."""
        if not self.config.enabled or not self.config.performance_tracking:
            return

        if operation not in self._performance_metrics:
            self._performance_metrics[operation] = []

        self._performance_metrics[operation].append(duration_ms)

        # Keep only last 100 measurements
        if len(self._performance_metrics[operation]) > 100:
            self._performance_metrics[operation] = self._performance_metrics[operation][-100:]

        self.log(
            LogLevel.PERFORMANCE,
            "Performance",
            f"Operation '{operation}' took {duration_ms:.2f}ms",
            {"operation": operation, "duration_ms": duration_ms},
        )

    def get_log_entries(
        self, level: Optional[LogLevel] = None, source: Optional[str] = None, limit: int = 100
    ) -> List[LogEntry]:
        """Get filtered log entries."""
        entries = list(self._log_entries)

        if level:
            entries = [e for e in entries if e.level == level]
        if source:
            entries = [e for e in entries if e.source == source]

        return entries[-limit:]

    def get_network_history(self, limit: int = 50) -> List[NetworkRequest]:
        """Get network request history."""
        return list(self._network_requests)[-limit:]

    def get_performance_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics."""
        stats = {}
        for operation, times in self._performance_metrics.items():
            if times:
                stats[operation] = {
                    "count": len(times),
                    "avg_ms": sum(times) / len(times),
                    "min_ms": min(times),
                    "max_ms": max(times),
                    "last_ms": times[-1],
                }
        return stats

    def clear_logs(self) -> None:
        """Clear all log entries."""
        self._log_entries.clear()
        self.info("DebugLogger", "Logs cleared")

    def clear_network_history(self) -> None:
        """Clear network request history."""
        self._network_requests.clear()
        self.info("DebugLogger", "Network history cleared")

    def subscribe(self, callback: Callable[[LogEntry], None]) -> None:
        """Subscribe to log updates."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[LogEntry], None]) -> None:
        """Unsubscribe from log updates."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def subscribe_network(self, callback: Callable[[NetworkRequest], None]) -> None:
        """Subscribe to network request updates."""
        self._network_subscribers.append(callback)

    def unsubscribe_network(self, callback: Callable[[NetworkRequest], None]) -> None:
        """Unsubscribe from network request updates."""
        if callback in self._network_subscribers:
            self._network_subscribers.remove(callback)

    def format_entry(self, entry: LogEntry) -> str:
        """Format a log entry for display."""
        if self.config.compact_mode:
            return f"[{entry.level.value.upper()}] {entry.source}: {entry.message}"

        timestamp = datetime.fromtimestamp(entry.timestamp).strftime("%H:%M:%S.%f")[:-3]

        level_colors = {
            LogLevel.DEBUG: "#6c7086",
            LogLevel.INFO: "#89b4fa",
            LogLevel.WARNING: "#fab387",
            LogLevel.ERROR: "#f38ba8",
            LogLevel.NETWORK: "#a6e3a1",
            LogLevel.PERFORMANCE: "#cba6f7",
        }

        color = level_colors.get(entry.level, "#cdd6f4")

        lines = [
            f"[{color}][{timestamp}][{entry.level.value.upper()}][{entry.source}][/] {entry.message}"
        ]

        if entry.data and not self.config.compact_mode:
            try:
                data_str = json.dumps(entry.data, indent=2, default=str)
                lines.append(f"[dim]{data_str}[/]")
            except:
                lines.append(f"[dim]{str(entry.data)}[/]")

        return "\n".join(lines)


def network_track(method: str, endpoint: str):
    """Decorator to track network requests."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            debug = DebugLogger()
            request_id = f"{method}_{endpoint}_{time.time()}"

            debug.network_start(request_id, method, endpoint, kwargs)

            try:
                result = func(*args, **kwargs)
                debug.network_end(request_id, status_code=200)
                return result
            except Exception as e:
                debug.network_end(request_id, error=str(e))
                raise

        return wrapper

    return decorator


# Global instance
get_debug_logger = DebugLogger
