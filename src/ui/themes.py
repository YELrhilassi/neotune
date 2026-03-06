from textual.theme import Theme

CATPPUCCIN = Theme(
    name="catppuccin",
    primary="#89b4fa",
    accent="#cba6f7",
    background="#1e1e2e",
    surface="#181825",
    panel="#313244",
    success="#a6e3a1",
    warning="#fab387",
    error="#f38ba8",
)

NORD = Theme(
    name="nord",
    primary="#81a1c1",
    accent="#88c0d0",
    background="#2e3440",
    surface="#3b4252",
    panel="#434c5e",
    success="#a3be8c",
    warning="#ebcb8b",
    error="#bf616a",
)

DRACULA = Theme(
    name="dracula",
    primary="#8be9fd",
    accent="#bd93f9",
    background="#282a36",
    surface="#44475a",
    panel="#6272a4",
    success="#50fa7b",
    warning="#ffb86c",
    error="#ff5555",
)

TOKYO_NIGHT = Theme(
    name="tokyo-night",
    primary="#7aa2f7",
    accent="#bb9af7",
    background="#1a1b26",
    surface="#16161e",
    panel="#24283b",
    success="#9ece6a",
    warning="#e0af68",
    error="#f7768e",
)

THEMES = {
    "catppuccin": CATPPUCCIN,
    "nord": NORD,
    "dracula": DRACULA,
    "tokyo-night": TOKYO_NIGHT
}
