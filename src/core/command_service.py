"""Command service with Command pattern implementation."""

import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, cast

from src.core.di import Container
from src.core.logging_config import get_logger
from src.core.debug_logger import DebugLogger
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork
from src.config.user_prefs import UserPreferences
from src.network.local_player import LocalPlayer
from src.hooks.track_actions import play_track
from src.actions.auth_actions import logout
from src.actions.health_check import perform_health_check

logger = get_logger("commands")


class Command(ABC):
    @abstractmethod
    def execute(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        pass


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: Dict[str, Command] = {}
        self.debug_logger = DebugLogger()

    def register(self, name: str, command: Command) -> None:
        self._commands[name] = command

    def execute(self, name: str, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        if name not in self._commands:
            self.debug_logger.warning("Commands", f"Unknown command: {name}")
            return
        self.debug_logger.info("Commands", f"Executing: {name}")
        self._commands[name].execute(app_instance, *args, **kwargs)

    def get_command_names(self) -> List[str]:
        return list(self._commands.keys())


def _run_network_cmd(app, func, success_msg_func=None):
    def _worker():
        try:
            result = func()
            if result is not None and success_msg_func:
                msg = success_msg_func(result)
                if msg:
                    app.call_from_thread(app.notify, msg)
            app.call_from_thread(app.update_now_playing, force=True)
        except Exception as e:
            logger.error(f"Command failed: {e}")

    threading.Thread(target=_worker, daemon=True).start()


class PlayPauseCommand(Command):
    def execute(self, app, *args, **kwargs):
        nw = Container.resolve(SpotifyNetwork)
        _run_network_cmd(app, nw.toggle_play_pause, lambda r: "Playing" if r else "Paused")


class NextTrackCommand(Command):
    def execute(self, app, *args, **kwargs):
        nw = Container.resolve(SpotifyNetwork)
        _run_network_cmd(app, nw.next_track, lambda r: "Next track")


class PrevTrackCommand(Command):
    def execute(self, app, *args, **kwargs):
        nw = Container.resolve(SpotifyNetwork)
        _run_network_cmd(app, nw.prev_track, lambda r: "Previous track")


class ToggleShuffleCommand(Command):
    def execute(self, app, *args, **kwargs):
        nw = Container.resolve(SpotifyNetwork)
        _run_network_cmd(app, nw.toggle_shuffle, lambda r: f"Shuffle {'On' if r else 'Off'}")


class CycleRepeatCommand(Command):
    def execute(self, app, *args, **kwargs):
        nw = Container.resolve(SpotifyNetwork)
        _run_network_cmd(app, nw.cycle_repeat, lambda r: f"Repeat: {r.capitalize()}")


class RecommendationsCommand(Command):
    """Triggers 'Radio' (r) for the current or selected context."""

    def execute(self, app, *args, **kwargs):
        from src.ui.components.track_table import TrackList

        try:
            tl = app.query_one(TrackList)
            item = tl.get_highlighted_track_data()
            if not item:
                pb = app.store.get("current_playback")
                if pb:
                    item = pb.get("item")

            if not item:
                app.notify("No item selected for Radio", severity="warning")
                return

            uri = item.get("uri")
            name = item.get("name", "Unknown")
            app.notify(f"Starting Radio for: {name}")

            def _worker():
                nw = Container.resolve(SpotifyNetwork)
                seed_tracks = None
                seed_artists = None

                if uri:
                    if ":track:" in uri:
                        seed_tracks = [uri.split(":")[-1]]
                    elif ":artist:" in uri:
                        seed_artists = [uri.split(":")[-1]]
                    elif ":album:" in uri:
                        alb = nw.library.get_album_metadata(uri.split(":")[-1])
                        if alb and alb.get("artists"):
                            seed_artists = [alb["artists"][0]["id"]]
                    elif ":playlist:" in uri:
                        tracks = nw.library.get_playlist_tracks(uri.split(":")[-1], limit=1)
                        if tracks:
                            seed_tracks = [tracks[0]["track"]["id"]]

                tracks = nw.discovery.get_recommendations(
                    limit=50, seed_tracks=seed_tracks, seed_artists=seed_artists
                )
                if tracks:
                    app.call_from_thread(app.store.set, "current_tracks", tracks)
                    app.call_from_thread(
                        app.store.set, "last_active_context", f"radio:{uri}", persist=True
                    )
                    if play_track(tracks[0]["uri"], app):
                        app.call_from_thread(app.update_now_playing)
                else:
                    app.call_from_thread(app.notify, "No recommendations found", severity="warning")

            threading.Thread(target=_worker, daemon=True).start()
        except:
            pass


class ShowDeviceCommand(Command):
    def execute(self, app, *args, **kwargs):
        from src.ui.modals.audio_modals import DeviceSelector

        def _worker():
            nw = Container.resolve(SpotifyNetwork)
            devices_data = app.safe_network_call(nw.get_devices)
            if devices_data and devices_data.get("devices"):
                devices = devices_data["devices"]
                active_id = next((d["id"] for d in devices if d["is_active"]), None)

                def _on_device_selected(device_id):
                    if device_id:
                        # Find device name
                        device_name = next(
                            (d["name"] for d in devices if d["id"] == device_id), "Unknown"
                        )
                        app.store.set("preferred_device_name", device_name)

                        # Update Device Store
                        from src.state.feature_stores import DeviceStore

                        Container.resolve(DeviceStore).update(
                            preferred_id=device_id, preferred_name=device_name
                        )

                        def _transfer_worker():
                            nw = Container.resolve(SpotifyNetwork)
                            nw.transfer_playback(device_id)
                            app.call_from_thread(app.notify, f"Switched to {device_name}")
                            app.call_from_thread(app.update_now_playing, force=True)

                        threading.Thread(target=_transfer_worker, daemon=True).start()

                app.call_from_thread(
                    app.safe_push_screen, DeviceSelector(devices, active_id), _on_device_selected
                )
            else:
                app.call_from_thread(app.notify, "No devices found", severity="warning")

        threading.Thread(target=_worker, daemon=True).start()


class ShowAudioCommand(Command):
    def execute(self, app, *args, **kwargs):
        from src.ui.modals.audio_modals import AudioConfigSelector

        prefs = Container.resolve(UserPreferences)

        def _on_config_selected(config):
            if config:
                # Update preferences
                prefs.audio_config.update(config)
                app.notify(f"Audio backend set to: {config['backend']}")

                # Update Config Store
                from src.state.feature_stores import ConfigStore

                Container.resolve(ConfigStore).update(audio=prefs.audio_config)

                # Restart player if running

                player = Container.resolve(LocalPlayer)
                nw = Container.resolve(SpotifyNetwork)
                if player.is_running():
                    token = nw.get_access_token()
                    player.restart(access_token=token)

        app.safe_push_screen(AudioConfigSelector(prefs.audio_config), _on_config_selected)


class SearchCommand(Command):
    def execute(self, app, *args, **kwargs):
        from src.ui.modals.telescope import TelescopePrompt

        app.safe_push_screen(TelescopePrompt())


class RestartDaemonCommand(Command):
    def execute(self, app, *args, **kwargs):
        player = Container.resolve(LocalPlayer)
        nw = Container.resolve(SpotifyNetwork)
        app.notify("Restarting playback daemon...")
        token = nw.get_access_token()
        player.restart(access_token=token)


class CommandPromptCommand(Command):
    def execute(self, app, *args, **kwargs):
        from src.ui.modals.command_prompt import CommandPrompt

        app.safe_push_screen(CommandPrompt())


class ThemeSelectorCommand(Command):
    def execute(self, app, *args, **kwargs):
        from src.ui.modals.theme_selector import ThemeSelector

        prefs = Container.resolve(UserPreferences)

        def _on_theme_selected(theme):
            if theme:
                prefs.theme = theme
                app.apply_theme(theme)
                app.notify(f"Theme set to: {theme}")
                # Update UI store for any other interested components
                from src.state.feature_stores import ConfigStore

                Container.resolve(ConfigStore).update(theme=theme)

        app.safe_push_screen(ThemeSelector(prefs.theme), _on_theme_selected)


class CommandService:
    def __init__(self):
        self.registry = CommandRegistry()
        self._register_defaults()

    def _register_defaults(self):
        cmds = [
            ("play_pause", PlayPauseCommand()),
            ("next_track", NextTrackCommand()),
            ("prev_track", PrevTrackCommand()),
            ("toggle_shuffle", ToggleShuffleCommand()),
            ("cycle_repeat", CycleRepeatCommand()),
            ("recommendations", RecommendationsCommand()),
            ("show_device", ShowDeviceCommand()),
            ("show_audio", ShowAudioCommand()),
            ("search_prompt", SearchCommand()),
            ("restart_daemon", RestartDaemonCommand()),
            ("command_prompt", CommandPromptCommand()),
            ("theme_selector", ThemeSelectorCommand()),
            (
                "refresh",
                type("Refresh", (Command,), {"execute": lambda s, a, *args: a.refresh_data()})(),
            ),
            (
                "toggle_sidebar",
                type(
                    "TS",
                    (Command,),
                    {
                        "execute": lambda s, a, *args: setattr(
                            a.query_one("#sidebar"), "display", not a.query_one("#sidebar").display
                        )
                    },
                )(),
            ),
            ("logout", type("Logout", (Command,), {"execute": lambda s, a, *args: logout(a)})()),
            ("quit", type("Quit", (Command,), {"execute": lambda s, a, *args: a.action_quit()})()),
        ]
        for n, c in cmds:
            self.registry.register(n, c)

    def execute(self, action, app):
        self.registry.execute(action, app)
