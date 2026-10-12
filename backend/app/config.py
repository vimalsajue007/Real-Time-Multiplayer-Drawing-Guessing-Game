"""Application settings, loaded from environment variables / .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "mysql+pymysql://drawguess:drawguess@localhost:3306/drawguess"
    secret_key: str = "change-me-in-production"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # Lobby / room limits
    min_players: int = 2
    max_players: int = 8
    default_rounds: int = 3
    max_rounds: int = 10

    # Timings (seconds)
    round_seconds: float = 80
    result_seconds: float = 8
    drawer_grace_seconds: float = 10      # drawer may reconnect within this window
    reconnect_grace_seconds: float = 60   # any player may reconnect within this window mid-game
    lobby_grace_seconds: float = 30       # lobby seat is kept this long after a disconnect
    finished_room_ttl_seconds: float = 300

    # Safety limits
    ws_max_message_bytes: int = 16384
    ws_rate_limit_messages: int = 400     # per 10 s window per connection
    max_stroke_points_stored: int = 50000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
