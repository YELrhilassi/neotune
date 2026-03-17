from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork

nw = Container.resolve(SpotifyNetwork)
nw.authenticate()
try:
    nw.playback.sp.start_playback(device_id=None, context_uri="spotify:playlist:3hqXUcu06ajELPBS3uhCD1", uris=["spotify:track:3hqXUcu06ajELPBS3uhCD1"])
except Exception as e:
    print(e)
