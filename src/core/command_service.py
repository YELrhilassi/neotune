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
        import time

        try:
            result = func()
            if result is not None and success_msg_func:
                msg = success_msg_func(result)
                if msg:
                    app.call_from_thread(app.notify, msg)

            # Spotify API takes a moment to update the active playback state
            # after commands like skip/pause are issued. Give it a tiny buffer
            time.sleep(0.5)
            app.call_from_thread(app.update_now_playing, force=True)
            time.sleep(1.0)
            app.call_from_thread(app.update_now_playing, force=True)
        except Exception as e:
            logger.error(f"Command failed: {e}")

    threading.Thread(target=_worker, daemon=True).start()


class PlayPauseCommand(Command):
    def execute(self, app, *args, **kwargs):
        # Optimistic UI Update
        playback = app.store.get("current_playback")
        if playback:
            playback["is_playing"] = not playback.get("is_playing", False)
            app.store.set("current_playback", playback)

        nw = Container.resolve(SpotifyNetwork)
        _run_network_cmd(app, nw.toggle_play_pause, lambda r: "Playing" if r else "Paused")


class NextTrackCommand(Command):
    def execute(self, app, *args, **kwargs):
        app.notify("Skipping track...", severity="information")

        # Optimistic UI Update (just visually pause the progress bar so it feels fast)
        playback = app.store.get("current_playback")
        if playback:
            playback["progress_ms"] = 0
            app.store.set("current_playback", playback)

        nw = Container.resolve(SpotifyNetwork)
        _run_network_cmd(app, nw.next_track, lambda r: "Next track")


class PrevTrackCommand(Command):
    def execute(self, app, *args, **kwargs):
        app.notify("Previous track...", severity="information")

        # Optimistic UI Update
        playback = app.store.get("current_playback")
        if playback:
            playback["progress_ms"] = 0
            app.store.set("current_playback", playback)

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
                    app.call_from_thread(app.store.set, "pagination_state", {})
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

                        # Update Device State
                        app.store.set("preferred_device_name", device_name)

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

                # Update Config State
                prefs.audio_config.update(config)
                app.store.set("audio_config", prefs.audio_config)
                app.notify(f"Audio backend set to: {config['backend']}")

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


class FuzzySearchCommand(Command):
    def execute(self, app, *args, **kwargs):
        from src.ui.modals.fuzzy_finder import FuzzyFinderPrompt

        def _on_fuzzy_selected(item):
            if not item:
                return

            def _process_selection():
                import time

                try:
                    from src.ui.components.content_tree.content_tree import ContentTree
                    from src.ui.components.track_table import TrackList

                    ct = app.query_one(ContentTree)
                    tl = app.query_one(TrackList)

                    id_val = item["id"]
                    item_type = item.get("type")

                    # Try to physically highlight the node in the tree if it exists
                    def _focus_tree_node(target_id):
                        try:

                            def _walk_nodes(node):
                                if getattr(node, "data", None) and node.data.get("id") == target_id:
                                    return node
                                for child in getattr(node, "children", []):
                                    res = _walk_nodes(child)
                                    if res:
                                        return res
                                return None

                            target = _walk_nodes(ct.root)
                            if target:
                                ct.cursor_node = target
                                p = target.parent
                                while p and p != ct.root:
                                    p.expand()
                                    p = p.parent
                                ct.scroll_to_node(target)
                        except Exception as e:
                            pass

                    if item_type in ["playlist", "context"]:
                        app.store.set("last_active_node_id", id_val, persist=True)
                        app.call_from_thread(_focus_tree_node, id_val)

                        # Load the tracks
                        if id_val == "liked_songs_leaf":
                            ct.load_liked_songs()
                        elif id_val == "recently_played_leaf":
                            ct.load_recently_played()
                        elif id_val == "made_for_you_leaf":
                            ct.load_made_for_you()
                        elif id_val == "featured_leaf":
                            ct.load_featured_hub()
                        else:
                            # For playlists, check if it has tracks by directly checking the cache or API?
                            # Just loading it is fine for now
                            ct.load_playlist_tracks(id_val)

                        # Wait a bit and check if tracks are empty. If so, and it's a spotify playlist, load spotify playlists view and highlight it
                        time.sleep(1.0)
                        tracks = app.store.get("current_tracks")
                        if not tracks:
                            if item.get("source") == "spotify":
                                ct.load_spotify_user_playlists_to_table("spotify")
                                time.sleep(1.0)
                                app.call_from_thread(tl.focus_item_by_uri, item.get("uri"))
                            elif item.get("source") == "personal":
                                app.call_from_thread(_focus_tree_node, id_val)
                                app.call_from_thread(ct.focus)

                    elif item_type == "track":
                        # We want to load the context where this track lives
                        ctx_uri = item.get("context_uri")
                        ctx_pid = (
                            ctx_uri.split(":")[-1] if ctx_uri and "playlist:" in ctx_uri else None
                        )
                        track_uri = item.get("uri")

                        artists = (
                            ", ".join([a for a in item.get("artists", [])])
                            if item.get("artists")
                            else ""
                        )
                        display_name = f"{item.get('name', 'Unknown')} by {artists}"

                        def on_track_action_selected(action: Optional[str]):
                            if not action:
                                return

                            def _worker():
                                if action == "play":
                                    from src.hooks.usePlayTrack import usePlayTrack

                                    if usePlayTrack(track_uri, app, context_uri=ctx_uri):
                                        app.call_from_thread(app.update_now_playing, force=True)
                                elif action == "radio":
                                    from src.hooks.useTrackRadio import useTrackRadio

                                    useTrackRadio(track_uri, app)
                                elif action == "save":
                                    from src.hooks.useSaveTrack import useSaveTrack

                                    useSaveTrack(track_uri, app)
                                elif action == "remove":
                                    from src.hooks.useRemoveTrack import useRemoveTrack

                                    useRemoveTrack(track_uri, app)
                                elif action == "go_to":
                                    # User explicitly requested to navigate to the context
                                    if ctx_uri == "spotify:collection:tracks":
                                        app.call_from_thread(_focus_tree_node, "liked_songs_leaf")
                                        app.call_from_thread(ct.load_liked_songs)
                                    elif ctx_pid:
                                        app.call_from_thread(_focus_tree_node, ctx_pid)
                                        app.call_from_thread(
                                            lambda: ct.load_playlist_tracks(ctx_pid)
                                        )

                                    # Try to focus track
                                    def _focus_loop():
                                        for _ in range(30):
                                            time.sleep(0.1)
                                            if not app.store.get("loading_states", {}).get(
                                                "track_list", True
                                            ):
                                                break
                                        time.sleep(0.2)

                                        max_attempts = 20
                                        attempts = 0
                                        while attempts < max_attempts:
                                            import concurrent.futures

                                            future = concurrent.futures.Future()
                                            app.call_from_thread(
                                                lambda: future.set_result(
                                                    tl.focus_item_by_uri(track_uri)
                                                )
                                            )
                                            found = future.result(timeout=2.0)

                                            if found:
                                                break

                                            state = app.store.get("pagination_state") or {}
                                            if not state.get("has_more") or state.get("loading"):
                                                time.sleep(0.5)
                                                if not state.get("loading") and not state.get(
                                                    "has_more"
                                                ):
                                                    break
                                                continue

                                            app.call_from_thread(tl._load_next_page)
                                            for _ in range(20):
                                                time.sleep(0.1)
                                                s = app.store.get("pagination_state") or {}
                                                if not s.get("loading"):
                                                    break

                                            time.sleep(0.1)
                                            attempts += 1

                                    threading.Thread(target=_focus_loop, daemon=True).start()

                            threading.Thread(target=_worker, daemon=True).start()

                        def _push_modal():
                            from src.ui.modals.track_menu import TrackMenuPopup

                            app.push_screen(
                                TrackMenuPopup(track_uri, display_name, show_go_to=True),
                                on_track_action_selected,
                            )

                        app.call_from_thread(_push_modal)

                except Exception as e:
                    app.call_from_thread(app.notify, f"Failed to navigate: {e}")

            import threading

            threading.Thread(target=_process_selection, daemon=True).start()

        app.safe_push_screen(FuzzyFinderPrompt(), _on_fuzzy_selected)


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
                app.store.set("theme", theme)

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
            ("fuzzy_search", FuzzySearchCommand()),
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
