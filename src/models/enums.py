from enum import Enum, auto

class PlaybackState(Enum):
    PLAYING = auto()
    PAUSED = auto()
    UNKNOWN = auto()

class RepeatState(Enum):
    OFF = "off"
    CONTEXT = "context"
    TRACK = "track"

class ListType(Enum):
    USER_PLAYLISTS = auto()
    FEATURED_PLAYLISTS = auto()
    RECENTLY_PLAYED = auto()
