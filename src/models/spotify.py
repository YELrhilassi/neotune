"""Pydantic models for Spotify API data structures."""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class Device(BaseModel):
    """Spotify device model."""

    id: str
    name: str
    type: str
    is_active: bool = Field(default=False)
    is_private_session: bool = Field(default=False)
    is_restricted: bool = Field(default=False)
    volume_percent: Optional[int] = Field(default=None)


class Artist(BaseModel):
    """Spotify artist model."""

    id: str
    name: str
    uri: str


class Album(BaseModel):
    """Spotify album model."""

    id: str
    name: str
    uri: str
    artists: List[Artist] = Field(default_factory=list)
    images: List[Dict[str, Any]] = Field(default_factory=list)
    release_date: Optional[str] = Field(default=None)
    total_tracks: int = Field(default=0)


class Track(BaseModel):
    """Spotify track model."""

    id: str
    name: str
    uri: str
    artists: List[Artist] = Field(default_factory=list)
    album: Optional[Album] = Field(default=None)
    duration_ms: int = Field(default=0)
    explicit: bool = Field(default=False)
    popularity: Optional[int] = Field(default=None)
    preview_url: Optional[str] = Field(default=None)

    @property
    def duration_str(self) -> str:
        """Get duration as human-readable string (MM:SS)."""
        seconds = self.duration_ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

    @property
    def artist_names(self) -> str:
        """Get comma-separated artist names."""
        return ", ".join(a.name for a in self.artists)


class Playlist(BaseModel):
    """Spotify playlist model."""

    id: str
    name: str
    uri: str
    description: Optional[str] = Field(default=None)
    owner: Dict[str, Any] = Field(default_factory=dict)
    images: List[Dict[str, Any]] = Field(default_factory=list)
    tracks: Dict[str, Any] = Field(default_factory=dict)
    public: Optional[bool] = Field(default=None)
    collaborative: bool = Field(default=False)

    @property
    def track_count(self) -> int:
        """Get total track count."""
        return self.tracks.get("total", 0)


class PlaybackState(BaseModel):
    """Spotify playback state model."""

    device: Optional[Device] = Field(default=None)
    shuffle_state: bool = Field(default=False)
    repeat_state: str = Field(default="off")
    timestamp: int = Field(default=0)
    progress_ms: Optional[int] = Field(default=None)
    is_playing: bool = Field(default=False)
    item: Optional[Track] = Field(default=None)
    currently_playing_type: str = Field(default="track")

    @property
    def progress_str(self) -> str:
        """Get progress as human-readable string (MM:SS)."""
        if self.progress_ms is None:
            return "0:00"
        seconds = self.progress_ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"


class UserProfile(BaseModel):
    """Spotify user profile model."""

    id: str
    display_name: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)
    product: Optional[str] = Field(default=None)
    images: List[Dict[str, Any]] = Field(default_factory=list)
    explicit_content: Dict[str, bool] = Field(default_factory=dict)


class Category(BaseModel):
    """Spotify browse category model."""

    id: str
    name: str
    icons: List[Dict[str, Any]] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Spotify search result wrapper."""

    type: str  # track, album, playlist, etc.
    data: Dict[str, Any]

    def to_track(self) -> Optional[Track]:
        """Convert to Track if type matches."""
        if self.type == "track":
            return Track(**self.data)
        return None

    def to_album(self) -> Optional[Album]:
        """Convert to Album if type matches."""
        if self.type == "album":
            return Album(**self.data)
        return None

    def to_playlist(self) -> Optional[Playlist]:
        """Convert to Playlist if type matches."""
        if self.type == "playlist":
            return Playlist(**self.data)
        return None
