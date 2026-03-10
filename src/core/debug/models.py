"""Data models for the debugging and tracking system."""

import json
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, Optional


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
    response_body: Optional[Any] = None
    headers: Optional[Dict[str, str]] = None


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
