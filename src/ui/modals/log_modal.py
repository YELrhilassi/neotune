"""Enhanced log modal with browser-console-like features for debugging."""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import RichLog, TabbedContent, TabPane, Static, Button, OptionList, Input
from textual.reactive import reactive
from textual.binding import Binding
from textual import on, events, message

from src.core.di import Container
from src.core.debug_logger import DebugLogger, LogLevel, NetworkRequest, LogEntry
from src.ui.modals.base import BaseModal

if TYPE_CHECKING:
    from src.ui.terminal_renderer import TerminalRenderer


class DebugInput(Input):
    """A custom Input widget that supports Vim-like NORMAL and INSERT modes."""

    mode = reactive("NORMAL")

    async def _on_key(self, event: events.Key) -> None:
        if self.mode == "NORMAL":
            if event.character == "i":
                self.mode = "INSERT"
                event.stop()
                event.prevent_default()
                return
            elif event.character == "a":
                self.mode = "INSERT"
                self.cursor_position += 1
                event.stop()
                event.prevent_default()
                return
            elif event.character in ("H", "L"):
                # Bubble H/L to the parent modal for tab switching
                return
            elif event.character == "j" or event.key == "down":
                self.post_message(self.Navigate("down"))
                event.stop()
                event.prevent_default()
                return
            elif event.character == "k" or event.key == "up":
                self.post_message(self.Navigate("up"))
                event.stop()
                event.prevent_default()
                return

            if event.character and len(event.character) == 1:
                event.stop()
                event.prevent_default()
                return
        else:
            if event.key == "escape":
                self.mode = "NORMAL"
                event.stop()
                event.prevent_default()
                return

        await super()._on_key(event)

    def watch_mode(self, mode: str) -> None:
        self.set_class(mode == "INSERT", "-insert-mode")

    class Navigate(message.Message):
        def __init__(self, direction: str):
            super().__init__()
            self.direction = direction


class LogModal(BaseModal):
    """Enhanced log modal with multiple tabs and browser-console features."""

    BINDINGS = [
        Binding("ctrl+c", "clear_current_tab", "Clear Tab"),
        Binding("r", "refresh_current_tab", "Refresh"),
        Binding("H", "prev_category", "Prev Tab"),
        Binding("L", "next_category", "Next Tab"),
        Binding("j", "scroll_down", "Down"),
        Binding("k", "scroll_up", "Up"),
        Binding("escape", "dismiss", "Close"),
    ]

    log_filter_query = reactive("")
    log_level_filter = reactive("all")
    selected_network_index = reactive(None)

    def __init__(self):
        super().__init__()
        self.debug_logger = DebugLogger()
        self._tab_ids = ["tab-logs", "tab-network", "tab-performance", "tab-player", "tab-settings"]

    def compose(self) -> ComposeResult:
        with TabbedContent(id="debug-tabs"):
            with TabPane("Logs", id="tab-logs"):
                with Vertical():
                    with Horizontal(id="logs-filter-bar"):
                        yield DebugInput(placeholder="Filter logs...", id="logs-filter-input")
                        yield Button("All", id="filter-all", classes="filter-btn active")
                        yield Button("Info", id="filter-info", classes="filter-btn")
                        yield Button("Warn", id="filter-warning", classes="filter-btn")
                        yield Button("Error", id="filter-error", classes="filter-btn")
                    yield RichLog(id="app-logs", highlight=True, markup=True, wrap=True)

            with TabPane("Network", id="tab-network"):
                with Horizontal(id="network-container"):
                    with Vertical(id="network-list-side"):
                        yield Static("[bold #89b4fa] Requests[/]", id="network-header-text")
                        yield OptionList(id="network-list")
                    with Vertical(id="network-detail-side"):
                        yield Static("[bold #cba6f7] Details[/]", id="network-detail-header")
                        yield Static("[dim]Select a request on the left[/]", id="network-details")

            with TabPane("Performance", id="tab-performance"):
                with Vertical():
                    yield Static("[bold #cba6f7]Performance Metrics[/]", id="perf-title")
                    yield OptionList(id="perf-list")

            with TabPane("Player", id="tab-player"):
                with Vertical():
                    yield Static("[bold #a6e3a1]Local Player Logs[/]", id="player-title")
                    yield RichLog(id="player-logs", highlight=True, markup=True, wrap=True)

            with TabPane("Settings", id="tab-settings"):
                with Vertical():
                    yield Static("[bold #fab387]Debug Settings[/]", id="settings-title")
                    with Horizontal(id="settings-buttons"):
                        yield Button("Clear All Logs", id="btn-clear-logs", variant="error")
                        yield Button(
                            "Clear Network History", id="btn-clear-network", variant="error"
                        )
                        yield Button("Refresh Data", id="btn-refresh", variant="primary")
                    yield Static("", id="settings-info")

    def on_mount(self) -> None:
        self.debug_logger.subscribe(self._on_new_log_entry)
        self.debug_logger.subscribe_network(self._on_network_update)
        self.action_refresh_current_tab()

    def on_unmount(self) -> None:
        self.debug_logger.unsubscribe(self._on_new_log_entry)
        self.debug_logger.unsubscribe_network(self._on_network_update)

    def _on_new_log_entry(self, entry: LogEntry) -> None:
        if not self.is_mounted:
            return
        if self.log_level_filter != "all" and entry.level.value != self.log_level_filter:
            return
        if (
            self.log_filter_query
            and self.log_filter_query not in entry.message.lower()
            and self.log_filter_query not in entry.source.lower()
        ):
            return
        try:
            log_widget = self.query_one("#app-logs", RichLog)
            log_widget.write(self.debug_logger.format_entry(entry))
            if self.debug_logger.config.auto_scroll:
                log_widget.scroll_end(animate=False)
        except:
            pass

    def _on_network_update(self, request: NetworkRequest) -> None:
        if not self.is_mounted:
            return
        self.app.call_from_thread(self._load_network_history)
        if self.selected_network_index is not None:
            history = self.debug_logger.get_network_history()
            if (
                self.selected_network_index < len(history)
                and history[self.selected_network_index].id == request.id
            ):
                self.app.call_from_thread(self._update_network_details, self.selected_network_index)

    def _load_app_logs(self) -> None:
        try:
            log_widget = self.query_one("#app-logs", RichLog)
            log_widget.clear()
            entries = self.debug_logger.get_log_entries(limit=500)
            for entry in entries:
                if self.log_level_filter != "all" and entry.level.value != self.log_level_filter:
                    continue
                if (
                    self.log_filter_query
                    and self.log_filter_query not in entry.message.lower()
                    and self.log_filter_query not in entry.source.lower()
                ):
                    continue
                log_widget.write(self.debug_logger.format_entry(entry))
        except:
            pass

    def _load_network_history(self) -> None:
        try:
            lst = self.query_one("#network-list", OptionList)
            old_idx = lst.highlighted
            lst.clear_options()
            reqs = self.debug_logger.get_network_history(limit=100)
            if not reqs:
                lst.add_option("[dim]No requests tracked[/]")
                return
            for r in reqs:
                ts = datetime.fromtimestamp(r.timestamp).strftime("%H:%M:%S")
                if r.error:
                    line = f"[{ts}] [#f38ba8]✗ {r.method} {r.endpoint}[/]"
                elif r.status_code:
                    c = "#a6e3a1" if r.status_code < 400 else "#f38ba8"
                    line = f"[{ts}] [{c}]✓ {r.method} {r.endpoint} - {r.status_code}[/]"
                else:
                    line = f"[{ts}] [#89b4fa]⋯ {r.method} {r.endpoint}[/]"
                lst.add_option(line)
            if old_idx is not None and old_idx < lst.option_count:
                lst.highlighted = old_idx
        except:
            pass

    def _update_network_details(self, index: int) -> None:
        try:
            reqs = self.debug_logger.get_network_history(limit=100)
            if not reqs or index >= len(reqs):
                return
            r = reqs[index]
            pane = self.query_one("#network-details", Static)
            sc = "#a6e3a1" if (r.status_code or 200) < 400 else "#f38ba8"
            details = [
                f"[bold #89b4fa]Summary[/]",
                f"  [bold]Method:[/] {r.method}",
                f"  [bold]Endpoint:[/] [cyan]{r.endpoint}[/]",
                f"  [bold]Status:[/] [{sc}]{r.status_code or 'Pending'}[/]",
                f"  [bold]Duration:[/] {f'{r.duration_ms:.2f}ms' if r.duration_ms else 'N/A'}",
                f"  [bold]Size:[/] {f'{r.response_size} bytes' if r.response_size else 'N/A'}",
                f"\n[bold #cba6f7]Request Data[/]",
            ]
            try:
                details.append(f"[dim]{json.dumps(r.params, indent=2, default=str)}[/]")
            except:
                details.append(f"[dim]{str(r.params)}[/]")
            if r.error:
                details.extend([f"\n[bold #f38ba8]Error Message[/]", f"[#f38ba8]{r.error}[/]"])
            pane.update("\n".join(details))
        except:
            pass

    def _load_performance_metrics(self) -> None:
        try:
            lst = self.query_one("#perf-list", OptionList)
            lst.clear_options()
            stats = self.debug_logger.get_performance_stats()
            if not stats:
                lst.add_option("[dim]No performance data available[/]")
                return
            for op, m in stats.items():
                lst.add_option(f"[bold #89b4fa]{op}[/]")
                lst.add_option(
                    f"  Count: {m['count']} | Avg: {m['avg_ms']:.1f}ms | Last: {m['last_ms']:.1f}ms"
                )
                lst.add_option("")
        except:
            pass

    def _load_player_logs(self) -> None:
        try:
            log = self.query_one("#player-logs", RichLog)
            log.clear()
            from src.network.local_player import LocalPlayer
            import os

            p = Container.resolve(LocalPlayer)
            lp = os.path.join(p.cache_dir, "librespot.log")
            if os.path.exists(lp):
                with open(lp, "r") as f:
                    for line in f.readlines()[-100:]:
                        log.write(f"[#6c7086]{line.strip()}[/]")
            else:
                log.write("[dim]Player log file not found.[/]")
        except:
            pass

    def _load_settings(self) -> None:
        try:
            info = self.query_one("#settings-info", Static)
            c = self.debug_logger.config
            st = "[bold #a6e3a1]ENABLED[/]" if c.enabled else "[bold #f38ba8]DISABLED[/]"
            info.update(
                "\n".join(
                    [
                        f"[bold #89b4fa]Status:[/] {st}",
                        f"\n[bold #cba6f7]Active Config[/]",
                        f"  Network Tracking: {c.network_tracking}",
                        f"  Perf Tracking: {c.performance_tracking}",
                        f"  Log Level: {c.log_level}",
                        f"  Auto Scroll: {c.auto_scroll}",
                    ]
                )
            )
        except:
            pass

    @on(DebugInput.Changed, "#logs-filter-input")
    def on_filter_input_changed(self, event: Input.Changed) -> None:
        self.log_filter_query = event.value.lower()
        self._load_app_logs()

    @on(DebugInput.Navigate)
    def on_input_navigate(self, message: DebugInput.Navigate) -> None:
        if message.direction == "down":
            at = self.query_one("#debug-tabs", TabbedContent).active
            if at == "tab-network":
                self.query_one("#network-list").focus()
            elif at == "tab-performance":
                self.query_one("#perf-list").focus()
        elif message.direction == "up":
            self.query_one("#logs-filter-input").focus()

    @on(Button.Pressed)
    def handle_buttons(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if not bid:
            return
        if bid.startswith("filter-"):
            for b in self.query(".filter-btn"):
                b.remove_class("active")
            event.button.add_class("active")
            self.log_level_filter = bid.replace("filter-", "")
            self._load_app_logs()
        elif bid == "btn-clear-logs":
            self.debug_logger.clear_logs()
            self._load_app_logs()
        elif bid == "btn-clear-network":
            self.debug_logger.clear_network_history()
            self._load_network_history()
        elif bid == "btn-refresh":
            self.action_refresh_current_tab()

    @on(OptionList.OptionHighlighted, "#network-list")
    def on_network_selected(self, event: OptionList.OptionHighlighted) -> None:
        self.selected_network_index = event.option_index
        self._update_network_details(event.option_index)

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        active_id = str(event.pane.id) if event.pane.id else ""
        fm = {
            "tab-logs": "#logs-filter-input",
            "tab-network": "#network-list",
            "tab-performance": "#perf-list",
            "tab-player": "#player-logs",
        }
        target = fm.get(active_id)
        if target:
            try:
                self.query_one(target).focus()
            except:
                pass
        self.action_refresh_current_tab()

    def action_prev_category(self) -> None:
        tabs = self.query_one(TabbedContent)
        active = str(tabs.active)
        idx = self._tab_ids.index(active)
        tabs.active = self._tab_ids[(idx - 1) % len(self._tab_ids)]

    def action_next_category(self) -> None:
        tabs = self.query_one(TabbedContent)
        active = str(tabs.active)
        idx = self._tab_ids.index(active)
        tabs.active = self._tab_ids[(idx + 1) % len(self._tab_ids)]

    def action_scroll_down(self) -> None:
        f = self.focused
        if isinstance(f, OptionList):
            f.action_cursor_down()
        elif isinstance(f, RichLog):
            f.scroll_down()

    def action_scroll_up(self) -> None:
        f = self.focused
        if isinstance(f, OptionList):
            f.action_cursor_up()
        elif isinstance(f, RichLog):
            f.scroll_up()

    def action_refresh_current_tab(self) -> None:
        active = str(self.query_one(TabbedContent).active)
        rm = {
            "tab-logs": self._load_app_logs,
            "tab-network": self._load_network_history,
            "tab-performance": self._load_performance_metrics,
            "tab-player": self._load_player_logs,
            "tab-settings": self._load_settings,
        }
        func = rm.get(active)
        if func:
            func()

    def action_clear_current_tab(self) -> None:
        active = str(self.query_one(TabbedContent).active)
        if active == "tab-logs":
            self.debug_logger.clear_logs()
            self._load_app_logs()
        elif active == "tab-network":
            self.debug_logger.clear_network_history()
            self._load_network_history()
            self.query_one("#network-details", Static).update(
                "[dim]Select a request on the left[/]"
            )
