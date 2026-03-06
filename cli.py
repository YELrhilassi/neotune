import click
from src.core.di import Container
from src.state.store import Store
from src.config.client_config import ClientConfiguration
from src.config.user_prefs import UserPreferences
from src.network.spotify_network import SpotifyNetwork
from src.network.local_player import LocalPlayer

def setup_di():
    Container.register(ClientConfiguration, ClientConfiguration, singleton=True)
    Container.register(UserPreferences, UserPreferences, singleton=True)
    Container.register(Store, Store, singleton=True)
    
    client_config = Container.resolve(ClientConfiguration)
    store = Container.resolve(Store)
    
    try:
        network = SpotifyNetwork(client_config)
        store.set("is_authenticated", True)
    except Exception as e:
        network = None
        store.set("is_authenticated", False)
        store.set("auth_error", str(e))
        
    Container.register(SpotifyNetwork, lambda: network, singleton=True)
    
    player = LocalPlayer()
    prefs = Container.resolve(UserPreferences)
    player.start(prefs.audio_config)
    Container.register(LocalPlayer, lambda: player, singleton=True)

@click.group()
def cli():
    """Spotify CLI Tool"""
    setup_di()

@cli.command()
def status():
    """Show current playback status"""
    store = Container.resolve(Store)
    if not store.get("is_authenticated"):
        click.echo(f"Authentication error: {store.get('auth_error')}")
        return
        
    network = Container.resolve(SpotifyNetwork)
    playback = network.get_current_playback()
    
    if playback and playback.get('is_playing') and playback.get('item'):
        item = playback['item']
        artists = ", ".join([a['name'] for a in item['artists']])
        track_name = item['name']
        device_name = playback.get('device', {}).get('name', 'Unknown')
        click.echo(f"🎵 Now Playing: {track_name} by {artists} | 🎧 {device_name}")
    else:
        click.echo("⏸ Paused or Nothing Playing")

@cli.group()
def playback():
    """Control Spotify playback"""
    setup_di()

@playback.command(name="play-pause")
def play_pause():
    """Toggle play/pause"""
    network = Container.resolve(SpotifyNetwork)
    if network:
        is_playing = network.toggle_play_pause()
        click.echo("Playing" if is_playing else "Paused")

@playback.command()
def next():
    """Skip to next track"""
    network = Container.resolve(SpotifyNetwork)
    if network:
        network.next_track()
        click.echo("Skipped to next track.")

@playback.command()
def prev():
    """Go to previous track"""
    network = Container.resolve(SpotifyNetwork)
    if network:
        network.prev_track()
        click.echo("Went to previous track.")

@cli.command()
def playlists():
    """List your playlists"""
    network = Container.resolve(SpotifyNetwork)
    if network:
        playlists = network.get_playlists()
        for idx, pl in enumerate(playlists):
            click.echo(f"{idx+1}. {pl['name']} ({pl['id']})")

if __name__ == "__main__":
    cli()
