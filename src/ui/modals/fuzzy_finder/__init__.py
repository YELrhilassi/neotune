import re

from textual import events, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Input, OptionList

from src.core.di import Container
from src.core.icons import Icons
from src.core.utils import strip_icons
from src.state.store import Store
from src.ui.components.track_table import TrackList
from src.ui.modals.base import BaseModal


from textual.message import Message


class FuzzyInput(Input):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mode = "INSERT"

    async def _on_key(self, event: events.Key) -> None:
        if self.mode == "NORMAL":
            # Handle Mode Entry
            if event.character == "i":
                self.mode = "INSERT"
                self.post_message(self.ModeChanged("INSERT"))
                event.stop()
                event.prevent_default()
                return
            elif event.character == "a":
                self.mode = "INSERT"
                self.cursor_position += 1
                self.post_message(self.ModeChanged("INSERT"))
                event.stop()
                event.prevent_default()
                return

            # Navigation Keys (Navigation within the modal, not the text)
            if event.character == "j" or event.key == "down":
                self.post_message(self.Navigate("down"))
                event.stop()
                event.prevent_default()
                return
            elif event.character == "k" or event.key == "up":
                self.post_message(self.Navigate("up"))
                event.stop()
                event.prevent_default()
                return
            elif event.key == "enter":
                self.post_message(self.Navigate("select"))
                event.stop()
                event.prevent_default()
                return
            elif event.key == "escape":
                return

            # Strictly block all other printable characters in NORMAL mode
            if event.character and len(event.character) == 1:
                event.stop()
                event.prevent_default()
                return
        else:
            # INSERT mode
            if event.key == "escape":
                self.mode = "NORMAL"
                self.post_message(self.ModeChanged("NORMAL"))
                event.stop()
                event.prevent_default()
                return
            elif event.key == "down":
                self.post_message(self.Navigate("down"))
                event.stop()
                event.prevent_default()
                return
            elif event.key == "up":
                self.post_message(self.Navigate("up"))
                event.stop()
                event.prevent_default()
                return
            # Let Enter through so on_input_submitted triggers

        # If not handled, let the base class process it
        await super()._on_key(event)

    def on_blur(self, event: events.Blur) -> None:
        if self.mode != "NORMAL":
            self.mode = "NORMAL"
            self.post_message(self.ModeChanged("NORMAL"))

    class ModeChanged(Message):
        def __init__(self, mode: str):
            super().__init__()
            self.mode = mode

    class Navigate(Message):
        def __init__(self, direction: str):
            super().__init__()
            self.direction = direction


class FuzzyFinderPrompt(BaseModal[str]):
    BINDINGS = [
        Binding("escape", "handle_escape", "Normal Mode / Close"),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
    ]

    input_mode = reactive("INSERT")

    def __init__(self):
        super().__init__()
        self.store = Store()
        self.all_items = []
        self.filtered_items = []

    def compose(self) -> ComposeResult:
        from textual.widgets import Label

        with Vertical(id="fuzzy-container", classes="fuzzy-modal"):
            with Horizontal(id="fuzzy-header", classes="insert-mode"):
                yield Label(Icons.SEARCH, id="fuzzy-icon")
                yield FuzzyInput(placeholder="Search playlists & library...", id="fuzzy-input")
                yield Label("[dim] [i/a] Insert • [j/k] Move [/]", id="fuzzy-hints")
            yield OptionList(id="fuzzy-results")

    def on_mount(self):
        self.input = self.query_one("#fuzzy-input", FuzzyInput)
        self.results_list = self.query_one("#fuzzy-results", OptionList)
        self.input.focus()
        self._load_items()
        self._update_list()

    @work(exclusive=True, thread=True)
    def _load_items(self):
        items = []

        # 0. Sidebar Core Items
        items.append(
            {
                "id": "made_for_you_leaf",
                "uri": "spotify:made_for_you",
                "name": "Made For You",
                "type": "context",
                "owner": "Spotify",
                "source": "core",
            }
        )
        items.append(
            {
                "id": "liked_songs_leaf",
                "uri": "spotify:collection:tracks",
                "name": "Liked Songs",
                "type": "context",
                "owner": "You",
                "source": "core",
            }
        )
        items.append(
            {
                "id": "recently_played_leaf",
                "uri": "spotify:recently_played",
                "name": "Recently Played",
                "type": "context",
                "owner": "You",
                "source": "core",
            }
        )
        items.append(
            {
                "id": "featured_leaf",
                "uri": "spotify:featured",
                "name": "Featured",
                "type": "context",
                "owner": "Spotify",
                "source": "core",
            }
        )

        # 1. Personal Playlists
        user_playlists = self.store.get("playlists") or []
        for pl in user_playlists:
            if pl and isinstance(pl, dict):
                items.append(
                    {
                        "id": pl.get("id"),
                        "uri": pl.get("uri"),
                        "name": pl.get("name", "Unknown"),
                        "type": "playlist",
                        "owner": "You",
                        "source": "personal",
                    }
                )

        # 2. Spotify Playlists
        sp_playlists = []
        sp_cache_key = "all_user_playlists_spotify"
        sp_cached_obj = self.store.get(sp_cache_key)
        if sp_cached_obj and isinstance(sp_cached_obj, dict):
            sp_playlists = sp_cached_obj.get("data", [])
            for pl in sp_playlists:
                if pl and isinstance(pl, dict):
                    items.append(
                        {
                            "id": pl.get("id"),
                            "uri": pl.get("uri"),
                            "name": pl.get("name", "Unknown"),
                            "type": "playlist",
                            "owner": "Spotify",
                            "source": "spotify",
                        }
                    )

        # 3. All Prefetched Tracks (from inside the playlists)
        tracks_cache_key = "all_prefetched_tracks"
        tracks_obj = self.store.get(tracks_cache_key)
        if tracks_obj and isinstance(tracks_obj, dict):
            tracks = tracks_obj.get("data", [])
            items.extend(tracks)  # They already have the right dictionary structure

        # 4. Inject V2 Persistent Cache (Loaded Liked Songs / Visited Playlists)
        from src.core.cache import CacheStore

        cache = CacheStore(enable_disk=True)
        for key, entry in cache._store.items():
            if key.startswith("playlist_tracks_v2:") or key == "liked_songs_tracks_v2":
                cached_data = entry.get("value")
                if cached_data and isinstance(cached_data, dict):
                    cached_tracks = cached_data.get("tracks", [])

                    context_name = "Liked Songs"
                    context_uri = "spotify:collection:tracks"
                    if key.startswith("playlist_tracks_v2:"):
                        pid = key.split(":")[-1]
                        context_uri = f"spotify:playlist:{pid}"
                        context_name = "Playlist"
                        for pl in user_playlists + sp_playlists:
                            if pl and isinstance(pl, dict) and pl.get("id") == pid:
                                context_name = pl.get("name", "Playlist")
                                break

                    for t in cached_tracks:
                        if not t or not isinstance(t, dict):
                            continue
                        uri = t.get("uri")
                        if not uri:
                            continue

                        album_name = "Unknown Album"
                        if t.get("album"):
                            album_name = t["album"].get("name", "Unknown Album")

                        items.append(
                            {
                                "id": t.get("id"),
                                "uri": uri,
                                "name": t.get("name", "Unknown"),
                                "artists": [a.get("name") for a in t.get("artists", []) if a]
                                if "artists" in t
                                else [],
                                "album": album_name,
                                "type": "track",
                                "source": "cache_v2",
                                "context_name": context_name,
                                "context_uri": context_uri,
                            }
                        )

        # 5. Inject current tracks if not already present
        # This ensures the active playlist/liked songs is always 100% searchable
        current_tracks = self.store.get("current_tracks") or []
        existing_uris = {item.get("uri") for item in items if item.get("uri")}

        for t in current_tracks:
            if not t or not isinstance(t, dict):
                continue
            uri = t.get("uri")
            if not uri or uri in existing_uris:
                continue

            # Format the track properly for the fuzzy finder
            name = t.get("name", "Unknown")
            artists = [a.get("name") for a in t.get("artists", []) if a] if "artists" in t else []

            # Extract album name
            album_name = "Unknown Album"
            if t.get("album"):
                album_name = t["album"].get("name", "Unknown Album")

            # Extract context name if available
            context_name = "Current List"
            context_uri = uri
            last_context = self.store.get("last_active_context")
            if last_context:
                context_uri = last_context
                if last_context.startswith("spotify:playlist:"):
                    playlist_id = last_context.split(":")[-1]
                    # Try to get playlist name
                    for pl in user_playlists + sp_playlists:
                        if pl and isinstance(pl, dict) and pl.get("id") == playlist_id:
                            context_name = pl.get("name", "Playlist")
                            break
                elif last_context == "liked_songs":
                    context_name = "Liked Songs"
                elif last_context == "recently_played":
                    context_name = "Recently Played"

            items.append(
                {
                    "id": t.get("id"),
                    "uri": uri,
                    "name": name,
                    "artists": artists,
                    "album": album_name,
                    "type": "track",
                    "source": "current",
                    "context_name": context_name,
                    "context_uri": context_uri,
                }
            )

        self.all_items = items
        self.app.call_from_thread(self._filter_and_update, self.input.value)

    def _filter_and_update(self, query: str):
        query = query.lower().strip()
        if not query:
            self.filtered_items = self.all_items
        else:
            self.filtered_items = []
            terms = query.split()

            scored_items = []

            for item in self.all_items:
                name = item.get("name", "").lower()

                artists_list = item.get("artists", [])
                artists = (
                    " ".join([a.lower() for a in artists_list])
                    if isinstance(artists_list, list)
                    else ""
                )

                album = item.get("album", "").lower()
                context_name = item.get("context_name", "").lower()

                searchable = f"{name} {artists} {album} {context_name}".strip()

                # All terms must be present in the searchable string
                if all(term in searchable for term in terms):
                    # Calculate a basic score: exact name matches get highest priority
                    score = 0
                    if query == name:
                        score = 100
                    elif name.startswith(query):
                        score = 50
                    elif query in name:
                        score = 25
                    elif query in artists:
                        score = 20
                    elif query in album:
                        score = 15
                    elif query in context_name:
                        score = 10

                    # Prioritize playlists over tracks if scores are equal
                    if item.get("type") == "playlist":
                        score += 10

                    scored_items.append((score, item))

            # Sort by score descending
            scored_items.sort(key=lambda x: x[0], reverse=True)
            self.filtered_items = [item for score, item in scored_items]

        self._update_list()

    def _update_list(self):
        self.results_list.clear_options()
        if not self.filtered_items:
            self.results_list.add_option("No results found.")
            return

        # Cap results to avoid UI lag with thousands of tracks
        display_items = self.filtered_items[:100]

        for item in display_items:
            if item["type"] == "playlist":
                icon = Icons.PLAYLIST
                label = f"{icon} {strip_icons(item['name'])} [dim]({item['owner']})[/dim]"
            elif item["type"] == "track":
                icon = Icons.TRACK
                artists = ", ".join(item.get("artists", []))
                label = f"{icon} {strip_icons(item['name'])} [dim]by {artists} (in {item.get('context_name')})[/dim]"
            else:
                icon = Icons.ALBUM
                label = f"{icon} {strip_icons(item['name'])} [dim]({item['owner']})[/dim]"
            self.results_list.add_option(label)

    def on_input_changed(self, event: Input.Changed):
        self._filter_and_update(event.value)

    def on_input_submitted(self, event: Input.Submitted):
        if hasattr(self.results_list, "highlighted") and self.results_list.highlighted is not None:
            idx = self.results_list.highlighted
            if self.filtered_items and idx < len(self.filtered_items):
                item = self.filtered_items[idx]
                self.dismiss(item)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        idx = event.option_index
        if not self.filtered_items or idx >= len(self.filtered_items):
            return

        item = self.filtered_items[idx]
        self.dismiss(item)

    def handle_escape(self) -> None:
        if self.input_mode == "NORMAL":
            self.dismiss(None)
        else:
            self.input_mode = "NORMAL"

    def on_fuzzy_input_mode_changed(self, event: FuzzyInput.ModeChanged) -> None:
        self.input_mode = event.mode

    def on_fuzzy_input_navigate(self, event: FuzzyInput.Navigate) -> None:
        if event.direction == "down":
            self.results_list.action_cursor_down()
        elif event.direction == "up":
            self.results_list.action_cursor_up()
        elif event.direction == "select":
            # Simulate selection of the currently highlighted item
            if (
                hasattr(self.results_list, "highlighted")
                and self.results_list.highlighted is not None
            ):
                idx = self.results_list.highlighted
                if self.filtered_items and idx < len(self.filtered_items):
                    item = self.filtered_items[idx]
                    self.dismiss(item)

    def watch_input_mode(self, mode: str) -> None:
        header = self.query_one("#fuzzy-header")
        from textual.widgets import Label

        hints = self.query_one("#fuzzy-hints", Label)

        if mode == "INSERT":
            header.add_class("insert-mode")
            hints.update("[bold #a6e3a1]-- INSERT --[/] [dim] esc: Normal [/]")
        else:
            header.remove_class("insert-mode")
            hints.update("[dim] [i/a] Insert • [j/k] Move [/]")

        # We always keep focus on the input field so our Vim bindings work
        self.input.focus()

        if self.input.mode != mode:
            self.input.mode = mode

            self.results_list.action_cursor_down()

    def action_cursor_up(self):
        if self.input_mode == "INSERT":
            self.input_mode = "NORMAL"
            self.results_list.action_cursor_up()
