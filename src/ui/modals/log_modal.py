"""Enhanced log modal with browser-console-like features for debugging."""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import RichLog, TabbedContent, TabPane, Static, Button, Input, OptionList
from textual.reactive import reactive
from textual.binding import Binding
from textual import on, events, message

from src.core.icons import Icons
from src.core.di import Container as DIContainer
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
        Binding("y", "yank_selected", "Yank Selected"),
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
            # Tab 1: Logs
            with TabPane("Logs", id="tab-logs"):
                with Vertical():
                    with Horizontal(id="logs-filter-bar"):
                        yield DebugInput(placeholder="Filter logs...", id="logs-filter-input")
                        yield Button(
                            Icons.COPY,
                            id="btn-copy-all-logs",
                            classes="icon-btn",
                            tooltip="Copy All Logs",
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

            # Tab 2: Network
            with TabPane("Network", id="tab-network"):
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

            # Tab 3: Performance
            with TabPane("Performance", id="tab-performance"):
                with Vertical():
                    with Horizontal(classes="pane-header"):
                        yield Static("[bold #cba6f7]Performance Metrics[/]")
                        yield Button(
                            Icons.COPY,
                            id="btn-copy-perf",
                            classes="icon-btn",
                            tooltip="Copy All Stats",
                        )
                    yield OptionList(id="performance-stats-list")

            # Tab 4: Player
            with TabPane("Player", id="tab-player"):
                with Vertical():
                    with Horizontal(classes="pane-header"):
                        yield Static("[bold #a6e3a1]Local Player Logs[/]")
                        yield Button(
                            Icons.COPY,
                            id="btn-copy-player-logs",
                            classes="icon-btn",
                            tooltip="Copy Logs",
                        )
                    yield RichLog(id="player-logs", highlight=True, markup=True, wrap=True)

            # Tab 5: Settings
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
        # Load everything immediately
        self._load_app_logs()
        self._load_network_history()
        self._load_performance_metrics()
        self._load_player_logs()
        self._load_settings()
        self.debug_logger.info("UI", "Debugger initialized")

    def on_unmount(self) -> None:
        self.debug_logger.unsubscribe(self._on_new_log_entry)
        self.debug_logger.unsubscribe_network(self._on_network_update)

    # --- Real-time Updates ---

    def _on_new_log_entry(self, entry: LogEntry) -> None:
        if not self.is_mounted:
            return
        if entry.level in (LogLevel.NETWORK, LogLevel.PERFORMANCE):
            return

        def _update():
            try:
                if self.log_level_filter != "all" and entry.level.value != self.log_level_filter:
                    return
                if (
                    self.log_filter_query
                    and self.log_filter_query not in entry.message.lower()
                    and self.log_filter_query not in entry.source.lower()
                ):
                    return
                log_widget = self.query_one("#app-logs", RichLog)
                log_widget.write(self.debug_logger.format_entry(entry))
            except:
                pass

        if self.app:
            self.app.call_from_thread(_update)

    def _on_network_update(self, request: NetworkRequest) -> None:
        if not self.is_mounted:
            return

        def _update():
            try:
                # If Network tab is active, refresh the history list
                if self.query_one("#debug-tabs", TabbedContent).active == "tab-network":
                    self._load_network_history()
            except:
                pass

        if self.app:
            self.app.call_from_thread(_update)

    # --- Data Loading ---

    def _load_app_logs(self) -> None:
        try:
            log_widget = self.query_one("#app-logs", RichLog)
            log_widget.clear()
            entries = self.debug_logger.get_log_entries(limit=200)
            if not entries:
                log_widget.write("[dim]No logs recorded yet.[/]")
                return
            for entry in entries:
                if entry.level in (LogLevel.NETWORK, LogLevel.PERFORMANCE):
                    continue
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
            list_view = self.query_one("#network-history-list", OptionList)
            old_idx = list_view.highlighted
            list_view.clear_options()

            reqs = self.debug_logger.get_network_history(limit=50)
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
                list_view.add_option(f"[{sc}]{status_icon}[/] {r.method} [cyan]{r.endpoint}[/]")

            if old_idx is not None and old_idx < list_view.option_count:
                list_view.highlighted = old_idx
        except:
            pass

    def _load_performance_metrics(self) -> None:
        try:
            list_view = self.query_one("#performance-stats-list", OptionList)
            list_view.clear_options()
            stats = self.debug_logger.get_performance_stats()
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

    def _load_player_logs(self) -> None:
        try:
            log = self.query_one("#player-logs", RichLog)
            log.clear()
            from src.network.local_player import LocalPlayer
            import os

            p = DIContainer.resolve(LocalPlayer)
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
            log_count = len(self.debug_logger._log_entries)
            net_count = len(self.debug_logger._network_requests)
            text = [
                f"[bold #89b4fa]Status:[/] {st}",
                f"[bold #89b4fa]Logger ID:[/] {id(self.debug_logger)}",
                f"[bold #89b4fa]Stats:[/] {log_count} logs, {net_count} requests",
                f"\n[bold #cba6f7]Configuration[/]",
                f"  Net Tracking: {'[green]ON[/]' if c.network_tracking else '[red]OFF[/]'}",
                f"  Perf Tracking: {'[green]ON[/]' if c.performance_tracking else '[red]OFF[/]'}",
                f"  Log Level: {c.log_level}",
            ]
            info.update("\n".join(text))
        except:
            pass

    # --- Handlers ---

    @on(Button.Pressed)
    def on_button_click(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if not bid:
            return
        if bid == "btn-copy-all-logs":
            self._copy_all_logs()
        elif bid == "btn-copy-network-list":
            self._copy_network_history()
        elif bid == "btn-copy-selected-net":
            self.action_yank_selected()
        elif bid == "btn-copy-network-detail":
            self._copy_network_detail()
        elif bid == "btn-copy-perf":
            self._copy_perf_stats()
        elif bid == "btn-copy-player-logs":
            self._copy_player_logs()
        elif bid == "btn-clear-logs":
            self.debug_logger.clear_logs()
            self._load_app_logs()
            self._load_settings()
        elif bid == "btn-clear-network":
            self.debug_logger.clear_network_history()
            self._load_network_history()
            self._load_settings()
        elif bid == "btn-refresh":
            self.action_refresh_current_tab()
        elif bid.startswith("filter-"):
            for b in self.query(".filter-btn"):
                b.remove_class("active")
            event.button.add_class("active")
            self.log_level_filter = bid.replace("filter-", "")
            self._load_app_logs()

    @on(OptionList.OptionHighlighted, "#network-history-list")
    def on_network_item_selected(self, event: OptionList.OptionHighlighted) -> None:
        self.selected_network_index = event.option_index
        self._update_detail_by_index(event.option_index)

    def _update_detail_by_index(self, index: int) -> None:
        reqs = self.debug_logger.get_network_history(limit=50)
        # Options are in reverse order
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
                [
                    self.debug_logger.format_entry(e)
                    for e in self.debug_logger.get_log_entries(limit=1000)
                ]
            )
        )

    def _copy_network_history(self):
        self.app.copy_to_clipboard(
            "\n".join([f"{r.method} {r.endpoint}" for r in self.debug_logger.get_network_history()])
        )

    def _copy_network_detail(self):
        if self.selected_network_index is not None:
            reqs = self.debug_logger.get_network_history(limit=50)
            if self.selected_network_index < len(reqs):
                req = list(reversed(reqs))[self.selected_network_index]
                self.app.copy_to_clipboard(json.dumps(req.params, indent=2, default=str))

    def _copy_perf_stats(self):
        s = self.debug_logger.get_performance_stats()
        self.app.copy_to_clipboard("\n".join([f"{k}: {v['avg_ms']:.1f}ms" for k, v in s.items()]))

    def _copy_player_logs(self):
        from src.network.local_player import LocalPlayer
        import os

        p = DIContainer.resolve(LocalPlayer)
        lp = os.path.join(p.cache_dir, "librespot.log")
        if os.path.exists(lp):
            with open(lp, "r") as f:
                self.app.copy_to_clipboard(f.read())

    # --- Navigation & Actions ---
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
        at = str(self.query_one(TabbedContent).active)
        m = {
            "tab-logs": self._load_app_logs,
            "tab-network": self._load_network_history,
            "tab-performance": self._load_performance_metrics,
            "tab-player": self._load_player_logs,
            "tab-settings": self._load_settings,
        }
        if at in m:
            m[at]()

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

    def action_clear_current_tab(self) -> None:
        at = str(self.query_one(TabbedContent).active)
        if at == "tab-logs":
            self.debug_logger.clear_logs()
            self._load_app_logs()
        elif at == "tab-network":
            self.debug_logger.clear_network_history()
            self._load_network_history()
            self.query_one("#network-details", Static).update(
                "[dim]Select a request on the left[/]"
            )
