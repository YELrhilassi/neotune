"""Command service with Command pattern implementation."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
import threading

from src.core.di import Container
from src.core.logging_config import get_logger
from src.core.debug_logger import DebugLogger
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork
from src.config.user_prefs import UserPreferences
from src.network.local_player import LocalPlayer
from src.actions.auth_actions import logout
from src.actions.health_check import perform_health_check

logger = get_logger("commands")


class Command(ABC):
    """Abstract base class for commands."""

    @abstractmethod
    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        """Execute the command.

        Args:
            app_instance: The application instance
            args: Variable positional arguments
            kwargs: Variable keyword arguments
        """
        pass


class CommandRegistry:
    """Registry for managing and executing commands."""

    def __init__(self) -> None:
        self._commands: Dict[str, Command] = {}
        self.debug_logger = DebugLogger()

    def register(self, name: str, command: Command) -> None:
        """Register a command.

        Args:
            name: Command identifier
            command: Command instance to register
        """
        self._commands[name] = command
        logger.debug(f"Registered command: {name}")

    def unregister(self, name: str) -> None:
        """Unregister a command.

        Args:
            name: Command identifier to remove
        """
        if name in self._commands:
            del self._commands[name]
            logger.debug(f"Unregistered command: {name}")

    def execute(self, name: str, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        """Execute a command by name.

        Args:
            name: Command identifier
            app_instance: Application instance
            args: Variable positional arguments
            kwargs: Variable keyword arguments

        Raises:
            KeyError: If command is not registered
        """
        if name not in self._commands:
            logger.warning(f"Unknown command: {name}")
            self.debug_logger.warning("Commands", f"Unknown command: {name}")
            raise KeyError(f"Command '{name}' not registered")

        self.debug_logger.info("Commands", f"Executing command: {name}")
        self._commands[name].execute(app_instance, *args, **kwargs)

    def get_command_names(self) -> List[str]:
        """Get list of all registered command names.

        Returns:
            List of command names
        """
        return list(self._commands.keys())

    def is_registered(self, name: str) -> bool:
        """Check if command is registered.

        Args:
            name: Command identifier

        Returns:
            True if command is registered
        """
        return name in self._commands


def _run_network_cmd(
    app_instance: Any,
    func: Callable,
    success_msg_func: Optional[Callable[[Any], Optional[str]]] = None,
) -> None:
    """Run a network command in background thread.

    Args:
        app_instance: Application instance
        func: Network function to call
        success_msg_func: Optional function to generate success message from result
    """

    def _worker() -> None:
        try:
            result = app_instance.safe_network_call(func)
            if result is not None and success_msg_func:
                msg = success_msg_func(result)
                if msg:
                    app_instance.call_from_thread(app_instance.notify, msg)
            # Force update playback after user command
            app_instance.call_from_thread(app_instance.update_now_playing, force=True)
        except Exception as e:
            logger.error(f"Network command failed: {e}")

    threading.Thread(target=_worker, daemon=True).start()


# Command Implementations


class PlayPauseCommand(Command):
    """Toggle play/pause playback."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        network = Container.resolve(SpotifyNetwork)
        _run_network_cmd(
            app_instance,
            network.toggle_play_pause,
            lambda r: "Playing" if r else "Paused",
        )


class NextTrackCommand(Command):
    """Skip to next track."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        network = Container.resolve(SpotifyNetwork)
        _run_network_cmd(app_instance, network.next_track, lambda r: "Next track")


class PrevTrackCommand(Command):
    """Go to previous track."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        network = Container.resolve(SpotifyNetwork)
        _run_network_cmd(app_instance, network.prev_track, lambda r: "Previous track")


class ToggleShuffleCommand(Command):
    """Toggle shuffle state."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        network = Container.resolve(SpotifyNetwork)
        _run_network_cmd(
            app_instance,
            network.toggle_shuffle,
            lambda r: f"Shuffle {'On' if r else 'Off'}",
        )


class CycleRepeatCommand(Command):
    """Cycle through repeat states."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        network = Container.resolve(SpotifyNetwork)
        _run_network_cmd(
            app_instance,
            network.cycle_repeat,
            lambda r: f"Repeat: {r.capitalize()}" if r else None,
        )


class ShowDeviceCommand(Command):
    """Show device selector."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        from src.ui.modals.audio_modals import DeviceSelector

        network = Container.resolve(SpotifyNetwork)
        store = Container.resolve(Store)

        def _fetch_devices() -> None:
            devices_data = app_instance.safe_network_call(network.get_devices)
            if not devices_data or not devices_data.get("devices"):
                app_instance.call_from_thread(
                    app_instance.notify,
                    "No available devices found",
                    severity="warning",
                )
                return

            devices = devices_data["devices"]
            active_id = next((d["id"] for d in devices if d["is_active"]), None)

            def on_device_selected(device_id: Optional[str]) -> None:
                if device_id:
                    selected_device = next((d for d in devices if d["id"] == device_id), None)
                    if selected_device:
                        store.set("preferred_device_id", device_id)
                        store.set("preferred_device_name", selected_device["name"])

                    def _transfer() -> None:
                        try:
                            app_instance.safe_network_call(
                                network.transfer_playback, device_id, force_play=True
                            )
                            app_instance.call_from_thread(app_instance.notify, "Switched output.")
                            app_instance.call_from_thread(app_instance.update_now_playing)
                        except Exception as e:
                            logger.error(f"Transfer playback failed: {e}")

                    threading.Thread(target=_transfer, daemon=True).start()

            app_instance.call_from_thread(
                app_instance.push_screen,
                DeviceSelector(devices, active_id),
                on_device_selected,
            )

        threading.Thread(target=_fetch_devices, daemon=True).start()


class ShowAudioCommand(Command):
    """Show audio configuration selector."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        from src.ui.modals.audio_modals import AudioConfigSelector

        network = Container.resolve(SpotifyNetwork)
        prefs = Container.resolve(UserPreferences)

        def on_config_selected(new_config: Optional[dict]) -> None:
            if new_config:
                prefs.audio_config.update(new_config)
                app_instance.local_player.stop()
                token = network.get_access_token()
                app_instance.local_player.start(prefs.audio_config, access_token=token)
                app_instance.notify(
                    f"Backend switched to {new_config['backend']}. Restarting player..."
                )

        app_instance.push_screen(AudioConfigSelector(prefs.audio_config), on_config_selected)


class ThemeSelectorCommand(Command):
    """Open theme selector."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        from src.ui.modals.theme_selector import ThemeSelector

        prefs = Container.resolve(UserPreferences)

        def on_theme_selected(theme_name: Optional[str]) -> None:
            if theme_name:
                prefs.save_theme(theme_name)
                app_instance.apply_theme(theme_name)
                app_instance.notify(f"Theme '{theme_name}' applied.")

        app_instance.push_screen(ThemeSelector(prefs.theme), on_theme_selected)


class CommandPromptCommand(Command):
    """Open command prompt."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        from src.ui.modals.command_prompt import CommandPrompt

        app_instance.push_screen(CommandPrompt())


class SearchPromptCommand(Command):
    """Open search/telescope."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        from src.ui.modals.telescope import TelescopePrompt

        app_instance.push_screen(TelescopePrompt())


class ToggleSidebarCommand(Command):
    """Toggle sidebar visibility."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        try:
            sidebar = app_instance.query_one("#sidebar")
            sidebar.display = not sidebar.display
            if not sidebar.display:
                app_instance.query_one("#track-list").focus()
        except Exception as e:
            logger.error(f"Toggle sidebar failed: {e}")


class RefreshCommand(Command):
    """Refresh application data."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        try:
            app_instance.refresh_data()
            app_instance.update_now_playing()
            app_instance.notify("Refreshed")
        except Exception as e:
            logger.error(f"Refresh failed: {e}")


class RestartDaemonCommand(Command):
    """Restart playback daemon."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        network = Container.resolve(SpotifyNetwork)
        try:
            player = Container.resolve(LocalPlayer)
            token = network.get_access_token()
            player.restart(access_token=token)
            app_instance.notify("Restarted playback player.")
        except Exception as e:
            logger.error(f"Restart daemon failed: {e}")


class RecommendationsCommand(Command):
    """Trigger recommendations (Radio) for current track or selected track."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        from src.ui.components.track_table import TrackList

        try:
            track_list = app_instance.query_one(TrackList)
            # 1. Try to get currently highlighted track in table
            track_data = track_list.get_highlighted_track_data()

            # 2. Fallback to current playback
            if not track_data:
                playback = app_instance.store.get("current_playback")
                if playback and playback.get("item"):
                    track_data = playback["item"]

            if not track_data:
                app_instance.notify("No track selected for Radio", severity="warning")
                return

            track_id = track_data.get("id")
            track_name = track_data.get("name", "Unknown Track")

            if not track_id:
                app_instance.notify("Invalid track ID for Radio", severity="error")
                return

            app_instance.notify(f"Starting Radio for: {track_name}")

            def _fetch_recommendations():
                network = Container.resolve(SpotifyNetwork)
                tracks = network.discovery.get_recommendations(seed_tracks=[track_id])

                if tracks:
                    app_instance.call_from_thread(app_instance.store.set, "current_tracks", tracks)
                    app_instance.call_from_thread(
                        app_instance.store.set,
                        "last_active_context",
                        f"radio:{track_id}",
                        persist=True,
                    )
                    # Automatically play first track
                    from src.hooks.track_actions import play_track

                    if play_track(tracks[0]["uri"], app_instance):
                        app_instance.call_from_thread(app_instance.update_now_playing)
                else:
                    app_instance.call_from_thread(
                        app_instance.notify, "No recommendations found", severity="warning"
                    )

            threading.Thread(target=_fetch_recommendations, daemon=True).start()

        except Exception as e:
            logger.error(f"Recommendations command failed: {e}")


class LogoutCommand(Command):
    """Logout and clear sessions."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        from src.ui.modals.confirmation import ConfirmationModal

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                logout(app_instance)

        app_instance.push_screen(
            ConfirmationModal("Are you sure you want to logout and clear all sessions?"),
            on_confirm,
        )


class HealthCheckCommand(Command):
    """Run health check."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        perform_health_check(app_instance)


class QuitCommand(Command):
    """Quit the application."""

    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        app_instance.action_quit()


class CommandService:
    """Service for executing commands.

    Uses Command pattern with registry for maintainable command handling.
    """

    def __init__(self) -> None:
        self.registry = CommandRegistry()
        self._register_default_commands()

    def _register_default_commands(self) -> None:
        """Register all default commands."""
        commands: List[tuple[str, Command]] = [
            ("play_pause", PlayPauseCommand()),
            ("next_track", NextTrackCommand()),
            ("prev_track", PrevTrackCommand()),
            ("toggle_shuffle", ToggleShuffleCommand()),
            ("cycle_repeat", CycleRepeatCommand()),
            ("show_device", ShowDeviceCommand()),
            ("show_audio", ShowAudioCommand()),
            ("toggle_sidebar", ToggleSidebarCommand()),
            ("refresh", RefreshCommand()),
            ("restart_daemon", RestartDaemonCommand()),
            ("recommendations", RecommendationsCommand()),
            ("logout", LogoutCommand()),
            ("health", HealthCheckCommand()),
            ("theme_selector", ThemeSelectorCommand()),
            ("command_prompt", CommandPromptCommand()),
            ("search_prompt", SearchPromptCommand()),
            ("quit", QuitCommand()),
        ]

        for name, command in commands:
            self.registry.register(name, command)

    def execute(self, action: str, app_instance: Any) -> None:
        """Execute a command by action name.

        Args:
            action: Command identifier
            app_instance: Application instance
        """
        try:
            self.registry.execute(action, app_instance)
        except KeyError:
            app_instance.notify(f"Unknown action: {action}", severity="warning")
            logger.warning(f"Attempted to execute unknown action: {action}")

    def get_available_commands(self) -> List[str]:
        """Get list of available command names.

        Returns:
            List of command identifiers
        """
        return self.registry.get_command_names()


__all__ = [
    "Command",
    "CommandRegistry",
    "CommandService",
]
