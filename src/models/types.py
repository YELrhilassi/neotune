from typing import TypedDict, List, Optional, Any

class ArtistDict(TypedDict):
    id: str
    name: str
    uri: str

class AlbumDict(TypedDict):
    id: str
    name: str
    uri: str

class TrackDict(TypedDict):
    id: str
    name: str
    uri: str
    duration_ms: int
    artists: List[ArtistDict]
    album: AlbumDict

class PlaylistDict(TypedDict):
    id: str
    name: str
    uri: str

class DeviceDict(TypedDict):
    id: str
    name: str
    is_active: bool
    volume_percent: int

class PlaybackDict(TypedDict):
    is_playing: bool
    item: Optional[TrackDict]
    device: Optional[DeviceDict]
    shuffle_state: bool
    repeat_state: str
