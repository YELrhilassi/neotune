"""Compatibility layer for DebugLogger."""

from src.core.debug.models import LogLevel, NetworkRequest, LogEntry, DebugConfig
from src.core.debug.service import DebugService
from src.core.debug.decorators import network_track

# Alias DebugService as DebugLogger for backward compatibility
DebugLogger = DebugService
get_debug_logger = DebugService
