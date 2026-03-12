"""Actions module for NeoTune.

This module contains action functions that replace the old hooks pattern.
Actions are plain functions that perform operations and can be called from
commands, UI components, or event handlers.
"""

from src.actions.auth_actions import logout
from src.actions.health_check import perform_health_check

__all__ = ["logout", "perform_health_check"]
