"""Main debug modal container."""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import TabbedContent, TabPane, Static, Button, OptionList, RichLog
from textual.reactive import reactive
from textual.binding import Binding
from textual import on, events

from src.core.di import Container
from src.core.debug.service import DebugService
from src.core.debug.models import LogLevel, NetworkRequest, LogEntry
from src.ui.modals.base import BaseModal
from src.ui.modals.debug.tabs import LogsTab, NetworkTab, PerformanceTab, PlayerTab, SettingsTab
from src.ui.modals.debug.input import DebugInput

if TYPE_CHECKING:
    from src.ui.terminal_renderer import TerminalRenderer


class DebugModal(BaseModal):
    """Refactored debug modal using modular components."""

    BINDINGS = [
        Binding("ctrl+c", "clear_current_tab", "Clear Tab"),
        Binding("r", "refresh_current_tab", "Refresh"),
        Binding("H", "prev_category", "Prev Tab"),
        Binding("L", "next_category", "Next Tab"),
        Binding("j", "scroll_down", "Down"),
        Binding("k", "scroll_up", "Up"),
        Binding("y", "yank_selected", "Yank Selected"),
        Binding("escape", "dismiss", "Close"),
    ]

    log_filter_query = reactive("")
    log_level_filter = reactive("all")
    selected_network_index = reactive(None)

    def __init__(self):
        super().__init__()
        self.debug_svc = DebugService()
        self._tab_ids = ["tab-logs", "tab-network", "tab-performance", "tab-player", "tab-settings"]

    def compose(self) -> ComposeResult:
        with TabbedContent(id="debug-tabs"):
            with TabPane("Logs", id="tab-logs"):
                yield LogsTab(id="view-logs")
            with TabPane("Network", id="tab-network"):
                yield NetworkTab(id="view-network")
            with TabPane("Performance", id="tab-performance"):
                yield PerformanceTab(id="view-perf")
            with TabPane("Player", id="tab-player"):
                yield PlayerTab(id="view-player")
            with TabPane("Settings", id="tab-settings"):
                yield SettingsTab(id="view-settings")

    def on_mount(self) -> None:
        self.debug_svc.subscribe(self._on_new_log_entry)
        self.debug_svc.subscribe_network(self._on_network_update)
        self.action_refresh_current_tab()
        self.debug_svc.info("UI", "Refactored Debug Modal Mounted")

    def on_unmount(self) -> None:
        self.debug_svc.unsubscribe(self._on_new_log_entry)
        self.debug_svc.unsubscribe_network(self._on_network_update)

    # --- Real-time Updates ---

    def _on_new_log_entry(self, entry: LogEntry) -> None:
        if not self.is_mounted:
            return
        # Delegate to logs tab if active
        if self.query_one("#debug-tabs", TabbedContent).active == "tab-logs":
            # Real-time append to RichLog instead of full refresh
            try:
                if self.log_level_filter != "all" and entry.level.value != self.log_level_filter:
                    return
                if self.log_filter_query and self.log_filter_query not in entry.message.lower():
                    return
                if entry.level in (LogLevel.NETWORK, LogLevel.PERFORMANCE):
                    return

                log_widget = self.query_one("#app-logs", RichLog)
                self.app.call_from_thread(log_widget.write, self.debug_svc.format_entry(entry))
            except:
                pass

    def _on_network_update(self, request: NetworkRequest) -> None:
        if not self.is_mounted:
            return
        if self.query_one("#debug-tabs", TabbedContent).active == "tab-network":
            self.app.call_from_thread(self.query_one("#view-network").refresh_data)

    # --- Handlers ---

    @on(Button.Pressed)
    def on_button_click(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if not bid:
            return

        # Handle Global/Shared buttons
        if bid == "btn-refresh":
            self.action_refresh_current_tab()
        elif bid == "btn-clear-logs":
            self.debug_svc.clear_logs()
            self.action_refresh_current_tab()
        elif bid == "btn-clear-network":
            self.debug_svc.clear_network_history()
            self.action_refresh_current_tab()

        # Handle Copy buttons
        elif bid == "btn-copy-all-logs":
            self._copy_all_logs()
        elif bid == "btn-copy-network-list":
            self._copy_network_history()
        elif bid == "btn-copy-network-detail":
            self._copy_network_detail()
        elif bid == "btn-copy-perf":
            self._copy_perf_stats()
        elif bid == "btn-copy-player-logs":
            self._copy_player_logs()

        # Handle Filters
        elif bid.startswith("filter-"):
            for b in self.query(".filter-btn"):
                b.remove_class("active")
            event.button.add_class("active")
            self.log_level_filter = bid.replace("filter-", "")
            self.query_one("#view-logs").refresh_data()

    @on(OptionList.OptionHighlighted, "#network-history-list")
    def on_network_item_selected(self, event: OptionList.OptionHighlighted) -> None:
        self.selected_network_index = event.option_index
        self._update_detail_by_index(event.option_index)

    def _update_detail_by_index(self, index: int) -> None:
        reqs = self.debug_svc.get_network_history(limit=50)
        if reqs and index < len(reqs):
            req = list(reversed(reqs))[index]
            pane = self.query_one("#network-details", Static)
            sc = "#a6e3a1" if (req.status_code or 200) < 400 else "#f38ba8"
            details = [
                f"[bold #89b4fa]Summary[/]",
                f"  Method: {req.method}",
                f"  Endpoint: [cyan]{req.endpoint}[/]",
                f"  Status: [{sc}]{req.status_code or 'Pending'}[/]",
                f"  Duration: {f'{req.duration_ms:.2f}ms' if req.duration_ms else 'N/A'}",
                f"\n[bold #cba6f7]Request Data[/]",
                f"[dim]{json.dumps(req.params, indent=2, default=str)}[/]",
            ]
            if req.error:
                details.extend([f"\n[bold #f38ba8]Error[/]", f"[#f38ba8]{req.error}[/]"])
            pane.update("\n".join(details))

    # --- Copy Logic ---
    def _copy_all_logs(self):
        self.app.copy_to_clipboard(
            "\n".join(
                [self.debug_svc.format_entry(e) for e in self.debug_svc.get_log_entries(limit=1000)]
            )
        )

    def _copy_network_history(self):
        self.app.copy_to_clipboard(
            "\n".join([f"{r.method} {r.endpoint}" for r in self.debug_svc.get_network_history()])
        )

    def _copy_network_detail(self):
        if self.selected_network_index is not None:
            reqs = list(reversed(self.debug_svc.get_network_history(limit=50)))
            if self.selected_network_index < len(reqs):
                self.app.copy_to_clipboard(
                    json.dumps(reqs[self.selected_network_index].params, indent=2, default=str)
                )

    def _copy_perf_stats(self):
        s = self.debug_svc.get_performance_stats()
        self.app.copy_to_clipboard("\n".join([f"{k}: {v['avg_ms']:.1f}ms" for k, v in s.items()]))

    def _copy_player_logs(self):
        # Implementation in PlayerTab can be called or duplicated
        self.query_one("#view-player").refresh_data()  # Ensure fresh

    # --- Navigation ---
    @on(DebugInput.Navigate)
    def on_input_navigate(self, message: DebugInput.Navigate) -> None:
        at = self.query_one("#debug-tabs", TabbedContent).active
        if message.direction == "down":
            if at == "tab-network":
                self.query_one("#network-history-list").focus()
            elif at == "tab-performance":
                self.query_one("#performance-stats-list").focus()
        elif message.direction == "up":
            self.query_one("#logs-filter-input").focus()

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if not self.is_mounted:
            return
        self.action_refresh_current_tab()

    def action_prev_category(self) -> None:
        t = self.query_one(TabbedContent)
        i = self._tab_ids.index(str(t.active))
        t.active = self._tab_ids[(i - 1) % len(self._tab_ids)]

    def action_next_category(self) -> None:
        t = self.query_one(TabbedContent)
        i = self._tab_ids.index(str(t.active))
        t.active = self._tab_ids[(i + 1) % len(self._tab_ids)]

    def action_scroll_down(self) -> None:
        f = self.focused
        if isinstance(f, (OptionList, RichLog)):
            if isinstance(f, OptionList):
                f.action_cursor_down()
            else:
                f.scroll_down()

    def action_scroll_up(self) -> None:
        f = self.focused
        if isinstance(f, (OptionList, RichLog)):
            if isinstance(f, OptionList):
                f.action_cursor_up()
            else:
                f.scroll_up()

    def action_refresh_current_tab(self) -> None:
        active_tab = self.query_one("#debug-tabs", TabbedContent).active
        view_id = {
            "tab-logs": "#view-logs",
            "tab-network": "#view-network",
            "tab-performance": "#view-perf",
            "tab-player": "#view-player",
            "tab-settings": "#view-settings",
        }.get(active_tab)

        if view_id:
            self.query_one(view_id).refresh_data()

    def action_yank_selected(self) -> None:
        f = self.focused
        if isinstance(f, OptionList):
            idx = f.highlighted
            if idx is not None:
                from rich.text import Text

                self.app.copy_to_clipboard(
                    Text.from_markup(str(f.get_option_at_index(idx).prompt)).plain
                )
        else:
            self.app.notify("Select an item to yank", severity="warning")
