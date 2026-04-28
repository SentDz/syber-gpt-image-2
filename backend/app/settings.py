from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser().resolve() if value else default.resolve()


def _derive_auth_base_url(provider_base_url: str) -> str:
    base_url = provider_base_url.rstrip("/")
    if base_url.endswith("/v1"):
        return base_url[:-3]
    return base_url


@dataclass(frozen=True)
class Settings:
    backend_dir: Path
    database_path: Path
    storage_dir: Path
    provider_base_url: str
    auth_base_url: str
    provider_usage_path: str
    image_model: str
    default_size: str
    default_quality: str
    image_price_1k: float
    image_price_2k: float
    image_price_4k: float
    user_name: str
    cors_origins: list[str]
    request_timeout_seconds: float
    session_cookie_name: str
    guest_cookie_name: str
    session_ttl_seconds: int
    guest_ttl_seconds: int
    cookie_secure: bool
    image_retention_days: int
    image_cleanup_interval_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        backend_dir = Path(__file__).resolve().parents[1]
        provider_base_url = os.getenv("SUB2API_BASE_URL", "http://127.0.0.1:9878/v1").rstrip("/")
        cors_origins = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:5173,http://localhost:5173",
            ).split(",")
            if origin.strip()
        ]
        return cls(
            backend_dir=backend_dir,
            database_path=_env_path("DATABASE_PATH", backend_dir / "data" / "app.sqlite3"),
            storage_dir=_env_path("STORAGE_DIR", backend_dir / "storage"),
            provider_base_url=provider_base_url,
            auth_base_url=os.getenv("SUB2API_AUTH_BASE_URL", _derive_auth_base_url(provider_base_url)).rstrip("/"),
            provider_usage_path=os.getenv("SUB2API_USAGE_PATH", "/v1/usage"),
            image_model=os.getenv("IMAGE_MODEL", "gpt-image-2"),
            default_size=os.getenv("IMAGE_SIZE", "2K"),
            default_quality=os.getenv("IMAGE_QUALITY", "auto"),
            image_price_1k=float(os.getenv("IMAGE_PRICE_1K_USD", "0.134")),
            image_price_2k=float(os.getenv("IMAGE_PRICE_2K_USD", "0.201")),
            image_price_4k=float(os.getenv("IMAGE_PRICE_4K_USD", "0.268")),
            user_name=os.getenv("APP_USER_NAME", "NEON_USER_404"),
            cors_origins=cors_origins,
            request_timeout_seconds=float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "300")),
            session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "cybergen_session"),
            guest_cookie_name=os.getenv("GUEST_COOKIE_NAME", "cybergen_guest"),
            session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", str(30 * 24 * 60 * 60))),
            guest_ttl_seconds=int(os.getenv("GUEST_TTL_SECONDS", str(365 * 24 * 60 * 60))),
            cookie_secure=os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"},
            image_retention_days=int(os.getenv("IMAGE_RETENTION_DAYS", "2")),
            image_cleanup_interval_seconds=int(os.getenv("IMAGE_CLEANUP_INTERVAL_SECONDS", str(6 * 60 * 60))),
        )

    @property
    def images_dir(self) -> Path:
        return self.storage_dir / "images"

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def inspirations_dir(self) -> Path:
        return self.storage_dir / "inspirations"

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.inspirations_dir.mkdir(parents=True, exist_ok=True)
