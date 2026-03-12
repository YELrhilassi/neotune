-- lua/audio.lua
-- Audio Configuration

neotune.set_audio(
    "pulseaudio", -- backend: pulseaudio, alsa, rodio, pipe
    "default",    -- device
    "320"         -- bitrate: 96, 160, 320
)
