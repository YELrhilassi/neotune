-- lua/audio.lua
-- Audio Configuration

spotify_tui.set_audio(
    "pulseaudio", -- backend: pulseaudio, alsa, rodio, pipe
    "default",    -- device
    "320"         -- bitrate: 96, 160, 320
)
