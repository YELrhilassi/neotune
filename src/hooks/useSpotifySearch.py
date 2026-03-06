from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork

def useSpotifySearch(query: str, qtypes: str = "track,album,playlist"):
    """
    Performs a Spotify search and returns a structured dictionary of results.
    """
    network = Container.resolve(SpotifyNetwork)
    try:
        results = network.search(query, qtypes)
        if results is None:
            return {"tracks": [], "albums": [], "playlists": []}
            
        data = {"tracks": [], "albums": [], "playlists": []}
        for item in results:
            item_type = item.get("_qtype")
            item_data = item.get("data")
            if not item_data: continue
            
            if item_type == "track":
                data["tracks"].append(item_data)
            elif item_type == "album":
                data["albums"].append(item_data)
            elif item_type == "playlist":
                data["playlists"].append(item_data)
        return data
    except Exception:
        return {"tracks": [], "albums": [], "playlists": []}
