"""Decorators for debugging and tracking."""

import time
import uuid
from functools import wraps
from typing import Optional, Dict
from src.core.debug.service import DebugService


def network_track(method: str, endpoint: str):
    """Decorator to track network requests."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            svc = DebugService()
            req_id = f"rt_{str(uuid.uuid4())[:8]}"
            svc.network_start(req_id, method, endpoint, kwargs)
            try:
                result = func(*args, **kwargs)
                svc.network_end(req_id, status_code=200)
                return result
            except Exception as e:
                svc.network_end(req_id, error=str(e))
                raise

        return wrapper

    return decorator
