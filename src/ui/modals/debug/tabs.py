"""Modular tab components for the debug modal."""

import json
import os
from datetime import datetime
from typing import Any, Optional

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import RichLog, TabPane, Static, Button, OptionList, ListView, ListItem
from textual.reactive import reactive
from textual import on, events

from src.core.icons import Icons
from src.core.di import Container as DIContainer
from src.state.store import Store
from src.core.debug.models import LogLevel, NetworkRequest, LogEntry
from src.core.debug.service import DebugService
from src.ui.modals.debug.input import DebugInput


class BaseDebugTab(Vertical):
    """Base class for debug tabs."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.debug_svc = DebugService()

    def refresh_data(self) -> None:
        """Refresh the tab's data."""
        pass


class LogsTab(BaseDebugTab):
    """Tab for application logs."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="logs-filter-bar"):
            yield DebugInput(placeholder="Filter logs...", id="logs-filter-input")
            yield Button(
                Icons.COPY, id="btn-copy-all-logs", classes="icon-btn", tooltip="Copy All Logs"
            )
            yield Button(
                Icons.CLIPBOARD,
                id="btn-copy-selected-log",
                classes="icon-btn",
                tooltip="Copy Latest",
            )
            yield Button("All", id="filter-all", classes="filter-btn active")
            yield Button("Info", id="filter-info", classes="filter-btn")
            yield Button("Warn", id="filter-warning", classes="filter-btn")
            yield Button("Error", id="filter-error", classes="filter-btn")
        yield RichLog(id="app-logs", highlight=True, markup=True, wrap=True)

    def refresh_data(self) -> None:
        try:
            log_widget = self.query_one("#app-logs", RichLog)
            log_widget.clear()
            entries = self.debug_svc.get_log_entries(limit=200)
            if not entries:
                log_widget.write("[dim]No logs recorded yet.[/]")
                return

            # Note: Modal container handles filtering if needed,
            # or we could move filter state here.
            for entry in entries:
                if entry.level in (LogLevel.NETWORK, LogLevel.PERFORMANCE):
                    continue
                log_widget.write(self.debug_svc.format_entry(entry))
        except:
            pass


class NetworkTab(BaseDebugTab):
    """Tab for network request tracking."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="network-container"):
            with Vertical(id="network-list-side"):
                with Horizontal(classes="pane-header"):
                    yield Static("[bold #89b4fa] Requests[/]")
                    yield Button(
                        Icons.COPY,
                        id="btn-copy-network-list",
                        classes="icon-btn",
                        tooltip="Copy History",
                    )
                    yield Button(
                        Icons.CLIPBOARD,
                        id="btn-copy-selected-net",
                        classes="icon-btn",
                        tooltip="Copy Selected",
                    )
                yield OptionList(id="network-history-list")
            with Vertical(id="network-detail-side"):
                with Horizontal(classes="pane-header"):
                    yield Static("[bold #cba6f7] Details[/]")
                    yield Button(
                        Icons.COPY,
                        id="btn-copy-network-detail",
                        classes="icon-btn",
                        tooltip="Copy Full Detail",
                    )
                yield Static("[dim]Select a request on the left[/]", id="network-details")

    def refresh_data(self) -> None:
        try:
            list_view = self.query_one("#network-history-list", OptionList)
            old_idx = list_view.highlighted
            list_view.clear_options()

            reqs = self.debug_svc.get_network_history(limit=50)
            if not reqs:
                list_view.add_option("[dim]No requests tracked[/]")
                return

            for r in reversed(reqs):
                status_icon = (
                    "✓" if r.status_code and r.status_code < 400 else "✗" if r.error else "⋯"
                )
                sc = (
                    "#a6e3a1"
                    if r.status_code and r.status_code < 400
                    else "#f38ba8"
                    if r.error
                    else "#89b4fa"
                )
                ts = datetime.fromtimestamp(r.timestamp).strftime("%H:%M:%S")
                list_view.add_option(
                    f"[dim]{ts}[/] [{sc}]{status_icon}[/] {r.method} [cyan]{r.endpoint}[/]"
                )

            if old_idx is not None and old_idx < list_view.option_count:
                list_view.highlighted = old_idx
        except:
            pass


class PerformanceTab(BaseDebugTab):
    """Tab for performance metrics."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="pane-header"):
            yield Static("[bold #cba6f7]Performance Metrics[/]")
            yield Button(
                Icons.COPY, id="btn-copy-perf", classes="icon-btn", tooltip="Copy All Stats"
            )
        yield OptionList(id="performance-stats-list")

    def refresh_data(self) -> None:
        try:
            list_view = self.query_one("#performance-stats-list", OptionList)
            list_view.clear_options()
            stats = self.debug_svc.get_performance_stats()
            if not stats:
                list_view.add_option("[dim]No performance data available[/]")
                return
            for op, m in sorted(stats.items()):
                list_view.add_option(f"[bold #89b4fa]{op}[/] [dim]({m['count']} calls)[/]")
                list_view.add_option(
                    f"  Avg: [green]{m['avg_ms']:.1f}ms[/] | Last: {m['last_ms']:.1f}ms"
                )
        except:
            pass


class PlayerTab(BaseDebugTab):
    """Tab for local player logs."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="pane-header"):
            yield Static("[bold #a6e3a1]Local Player Logs[/]")
            yield Button(
                Icons.COPY, id="btn-copy-player-logs", classes="icon-btn", tooltip="Copy Logs"
            )
        yield RichLog(id="player-logs", highlight=True, markup=True, wrap=True)

    def refresh_data(self) -> None:
        try:
            log_widget = self.query_one("#player-logs", RichLog)
            log_widget.clear()
            from src.network.local_player import LocalPlayer

            p = DIContainer.resolve(LocalPlayer)
            lp = os.path.join(p.cache_dir, "librespot.log")
            if os.path.exists(lp):
                with open(lp, "r") as f:
                    for line in f.readlines()[-100:]:
                        log_widget.write(f"[#6c7086]{line.strip()}[/]")
            else:
                log_widget.write("[dim]Player log file not found.[/]")
        except:
            pass


class SettingsTab(BaseDebugTab):
    """Tab for debugger settings and stats."""

    def compose(self) -> ComposeResult:
        yield Static("[bold #fab387]Debug Settings[/]", id="settings-title")
        with Horizontal(id="settings-buttons"):
            yield Button("Clear All Logs", id="btn-clear-logs", variant="error")
            yield Button("Clear Network History", id="btn-clear-network", variant="error")
            yield Button("Clear App Cache", id="btn-clear-app-cache", variant="error")
            yield Button("Refresh Data", id="btn-refresh", variant="primary")
        yield Static("", id="settings-info")

    def refresh_data(self) -> None:
        try:
            info = self.query_one("#settings-info", Static)
            c = self.debug_svc.config
            st = "[bold #a6e3a1]ENABLED[/]" if c.enabled else "[bold #f38ba8]DISABLED[/]"

            store = DIContainer.resolve(Store)
            log_count = store.get("debug_log_count") or 0
            net_count = store.get("debug_net_count") or 0

            text = [
                f"[bold #89b4fa]Status:[/] {st}",
                f"[bold #89b4fa]Logger ID:[/] {id(self.debug_svc)}",
                f"[bold #89b4fa]Stats (from Store):[/] {log_count} logs, {net_count} requests",
                f"\n[bold #cba6f7]Configuration[/]",
                f"  Net Tracking: {'[green]ON[/]' if c.network_tracking else '[red]OFF[/]'}",
                f"  Perf Tracking: {'[green]ON[/]' if c.performance_tracking else '[red]OFF[/]'}",
                f"  Log Level: {c.log_level}",
            ]
            info.update("\n".join(text))
        except:
            pass
