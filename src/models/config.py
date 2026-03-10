"""Pydantic models for configuration validation."""

from typing import Dict, Optional
from pydantic import BaseModel, Field, field_validator

from src.core.constants import (
    AudioBackend,
    AudioBitrate,
    ThemeNames,
    NavigationKeys,
    PlayerSettings,
)


class AudioConfig(BaseModel):
    """Audio configuration model."""

    backend: str = Field(default=PlayerSettings.DEFAULT_BACKEND.value)
    device: str = Field(default=PlayerSettings.DEFAULT_DEVICE)
    bitrate: str = Field(default=PlayerSettings.DEFAULT_BITRATE.value)

    @field_validator("backend")
    @classmethod
    def validate_backend(cls, v: str) -> str:
        """Validate audio backend."""
        valid_backends = [b.value for b in AudioBackend]
        if v not in valid_backends:
            raise ValueError(f"Invalid backend: {v}. Must be one of: {valid_backends}")
        return v

    @field_validator("bitrate")
    @classmethod
    def validate_bitrate(cls, v: str) -> str:
        """Validate bitrate."""
        valid_bitrates = [b.value for b in AudioBitrate]
        if v not in valid_bitrates:
            raise ValueError(f"Invalid bitrate: {v}. Must be one of: {valid_bitrates}")
        return v


class KeybindingConfig(BaseModel):
    """Keybinding configuration model."""

    key: str
    action: str
    description: str


class NavigationConfig(BaseModel):
    """Navigation key bindings configuration."""

    up: str = Field(default=NavigationKeys.UP)
    down: str = Field(default=NavigationKeys.DOWN)
    left: str = Field(default=NavigationKeys.LEFT)
    right: str = Field(default=NavigationKeys.RIGHT)
    page_up: str = Field(default=NavigationKeys.PAGE_UP)
    page_down: str = Field(default=NavigationKeys.PAGE_DOWN)


class ThemeConfig(BaseModel):
    """Theme configuration model."""

    name: str = Field(default=ThemeNames.CATPPUCCIN.value)
    primary: Optional[str] = None
    accent: Optional[str] = None
    background: Optional[str] = None
    surface: Optional[str] = None
    panel: Optional[str] = None
    success: Optional[str] = None
    warning: Optional[str] = None
    error: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_theme_name(cls, v: str) -> str:
        """Validate theme name."""
        valid_themes = [t.value for t in ThemeNames]
        if v not in valid_themes and v != "default":
            raise ValueError(f"Invalid theme: {v}. Must be one of: {valid_themes}")
        return v


class UserPreferencesModel(BaseModel):
    """Complete user preferences model."""

    theme: str = Field(default=ThemeNames.CATPPUCCIN.value)
    theme_vars: Optional[Dict[str, str]] = Field(default=None)
    leader: str = Field(default="space")
    show_which_key: bool = Field(default=True)
    auto_play: bool = Field(default=False)
    auto_select_device: bool = Field(default=True)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    navigation: NavigationConfig = Field(default_factory=NavigationConfig)

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        """Validate theme name."""
        valid_themes = [t.value for t in ThemeNames] + ["default"]
        if v not in valid_themes:
            raise ValueError(f"Invalid theme: {v}")
        return v

    def to_user_prefs_dict(self) -> Dict:
        """Convert to dictionary format expected by UserPreferences class.

        Returns:
            Dictionary with user preference settings
        """
        return {
            "theme": self.theme,
            "theme_vars": self.theme_vars,
            "leader": self.leader,
            "show_which_key": self.show_which_key,
            "auto_play": self.auto_play,
            "auto_select_device": self.auto_select_device,
            "audio_config": {
                "backend": self.audio.backend,
                "device": self.audio.device,
                "bitrate": self.audio.bitrate,
            },
            "nav_bindings": {
                "up": self.navigation.up,
                "down": self.navigation.down,
                "left": self.navigation.left,
                "right": self.navigation.right,
                "page_up": self.navigation.page_up,
                "page_down": self.navigation.page_down,
            },
        }
