import click
from src.state.app_state import ApplicationState

@click.group()
def cli():
    """Spotify CLI Tool"""
    pass

@cli.command()
def status():
    """Show current playback status"""
    state = ApplicationState()
    if not state.is_authenticated:
        click.echo(f"Authentication error: {state.auth_error}")
        return
        
    state.refresh_playback()
    playback = state.current_playback
    
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
    pass

@playback.command(name="play-pause")
def play_pause():
    """Toggle play/pause"""
    state = ApplicationState()
    if state.network:
        is_playing = state.network.toggle_play_pause()
        click.echo("Playing" if is_playing else "Paused")

@playback.command()
def next():
    """Skip to next track"""
    state = ApplicationState()
    if state.network:
        state.network.next_track()
        click.echo("Skipped to next track.")

@playback.command()
def prev():
    """Go to previous track"""
    state = ApplicationState()
    if state.network:
        state.network.prev_track()
        click.echo("Went to previous track.")

@cli.command()
def playlists():
    """List your playlists"""
    state = ApplicationState()
    if state.network:
        state.refresh_playlists()
        for idx, pl in enumerate(state.playlists):
            click.echo(f"{idx+1}. {pl['name']} ({pl['id']})")
