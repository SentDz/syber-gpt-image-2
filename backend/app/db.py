from __future__ import annotations

import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .settings import Settings


LEGACY_OWNER_ID = "legacy:default"
DEFAULT_SITE_LOCALE = "zh-CN"
USER_GALLERY_SOURCE_URL = "joko-image://user-gallery"
USER_GALLERY_SECTION = "用户作品"
DEFAULT_ANNOUNCEMENT_TITLE = "欢迎来到 即刻 图像系统"
DEFAULT_ANNOUNCEMENT_BODY = """欢迎使用 即刻 图像生态系统。

站主联系方式：
QQ：935764227
Telegram：请在后台配置

中转站 / 充值站点：
https://ai.get-money.locker

如需充值、额度支持或账号协助，请通过以上方式联系。"""
OLD_JIKE_ANNOUNCEMENT_BODY_WITH_JOKO_CONTACT = """欢迎使用 即刻 图像生态系统。

站主联系方式：
QQ：935764227
Telegram：https://t.me/jokoacoount

中转站 / 充值站点：
https://ai.get-money.locker

如需充值、额度支持或账号协助，请通过以上方式联系。"""
OLD_DEFAULT_ANNOUNCEMENT_TITLE = "欢迎来到 JokoAI 图像系统"
OLD_DEFAULT_ANNOUNCEMENT_BODY = """欢迎使用 JokoAI 图像生态系统。

站主联系方式：
QQ：935764227
Telegram：https://t.me/jokoacoount

中转站 / 充值站点：
https://ai.get-money.locker

如需充值、额度支持或账号协助，请通过以上方式联系。"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def utc_after(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self, settings: Settings) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS owner_config (
                    owner_id TEXT PRIMARY KEY,
                    api_key TEXT NOT NULL DEFAULT '',
                    managed_api_key TEXT NOT NULL DEFAULT '',
                    base_url TEXT NOT NULL,
                    usage_path TEXT NOT NULL,
                    model TEXT NOT NULL,
                    default_size TEXT NOT NULL,
                    default_quality TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    managed_by_auth INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS image_history (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL DEFAULT 'legacy:default',
                    mode TEXT NOT NULL CHECK (mode IN ('generate', 'edit')),
                    prompt TEXT NOT NULL,
                    model TEXT NOT NULL,
                    size TEXT NOT NULL,
                    aspect_ratio TEXT NOT NULL DEFAULT '',
                    quality TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed')),
                    image_url TEXT,
                    image_path TEXT,
                    input_image_url TEXT,
                    input_image_path TEXT,
                    revised_prompt TEXT,
                    usage_json TEXT,
                    provider_response_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS image_tasks (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    mode TEXT NOT NULL CHECK (mode IN ('generate', 'edit')),
                    prompt TEXT NOT NULL,
                    model TEXT NOT NULL,
                    size TEXT NOT NULL,
                    aspect_ratio TEXT NOT NULL DEFAULT '',
                    quality TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
                    request_json TEXT,
                    input_image_url TEXT,
                    input_image_path TEXT,
                    result_history_ids_json TEXT,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS ledger_entries (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL DEFAULT 'legacy:default',
                    event_type TEXT NOT NULL,
                    amount REAL NOT NULL DEFAULT 0,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    description TEXT NOT NULL,
                    history_id TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(history_id) REFERENCES image_history(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS user_sessions (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    sub2api_user_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    username TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT 'user',
                    access_token TEXT NOT NULL DEFAULT '',
                    refresh_token TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    user_agent TEXT,
                    ip_address TEXT
                );

                CREATE TABLE IF NOT EXISTS site_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    default_locale TEXT NOT NULL DEFAULT 'zh-CN',
                    announcement_enabled INTEGER NOT NULL DEFAULT 1,
                    announcement_title TEXT NOT NULL DEFAULT '',
                    announcement_body TEXT NOT NULL DEFAULT '',
                    announcement_updated_at TEXT,
                    inspiration_sources_json TEXT NOT NULL DEFAULT '[]',
                    provider_base_url TEXT NOT NULL DEFAULT '',
                    auth_base_url TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS inspiration_prompts (
                    id TEXT PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    source_item_id TEXT NOT NULL,
                    section TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    prompt TEXT NOT NULL,
                    image_url TEXT,
                    source_link TEXT,
                    raw_json TEXT,
                    synced_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(source_url, source_item_id)
                );

                CREATE TABLE IF NOT EXISTS public_cases (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    history_id TEXT UNIQUE,
                    title TEXT NOT NULL,
                    author TEXT,
                    prompt TEXT NOT NULL,
                    image_url TEXT,
                    image_path TEXT,
                    model TEXT NOT NULL DEFAULT '',
                    size TEXT NOT NULL DEFAULT '',
                    aspect_ratio TEXT NOT NULL DEFAULT '',
                    quality TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL CHECK (status IN ('visible', 'hidden', 'deleted')),
                    source_type TEXT NOT NULL CHECK (source_type IN ('user_history', 'admin_manual')),
                    created_by_admin INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS case_likes (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(case_id, owner_id),
                    FOREIGN KEY(case_id) REFERENCES public_cases(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS case_comments (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    author TEXT,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('visible', 'hidden', 'deleted')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(case_id) REFERENCES public_cases(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_owner_config_managed ON owner_config(managed_by_auth);
                CREATE INDEX IF NOT EXISTS idx_user_sessions_owner_id ON user_sessions(owner_id);
                CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);
                CREATE INDEX IF NOT EXISTS idx_image_tasks_owner_created_at ON image_tasks(owner_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_image_tasks_status_updated_at ON image_tasks(status, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_inspiration_prompts_synced_at ON inspiration_prompts(synced_at DESC);
                CREATE INDEX IF NOT EXISTS idx_inspiration_prompts_section ON inspiration_prompts(section);
                CREATE INDEX IF NOT EXISTS idx_public_cases_status_created_at ON public_cases(status, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_public_cases_owner_created_at ON public_cases(owner_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_case_likes_case_id ON case_likes(case_id);
                CREATE INDEX IF NOT EXISTS idx_case_comments_case_status_created_at ON case_comments(case_id, status, created_at DESC);
                """
            )
            self._migrate_legacy_schema(conn, settings)
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_image_history_owner_created_at ON image_history(owner_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_ledger_entries_owner_created_at ON ledger_entries(owner_id, created_at DESC);
                """
            )
            self._migrate_public_cases_from_user_gallery(conn)

    def _migrate_legacy_schema(self, conn: sqlite3.Connection, settings: Settings) -> None:
        owner_config_columns = _table_columns(conn, "owner_config")
        if "managed_api_key" not in owner_config_columns:
            conn.execute("ALTER TABLE owner_config ADD COLUMN managed_api_key TEXT NOT NULL DEFAULT ''")

        session_columns = _table_columns(conn, "user_sessions")
        if session_columns and "role" not in session_columns:
            conn.execute("ALTER TABLE user_sessions ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        if session_columns and "access_token" not in session_columns:
            conn.execute("ALTER TABLE user_sessions ADD COLUMN access_token TEXT NOT NULL DEFAULT ''")
        if session_columns and "refresh_token" not in session_columns:
            conn.execute("ALTER TABLE user_sessions ADD COLUMN refresh_token TEXT NOT NULL DEFAULT ''")

        image_columns = _table_columns(conn, "image_history")
        if "owner_id" not in image_columns:
            conn.execute(
                f"ALTER TABLE image_history ADD COLUMN owner_id TEXT NOT NULL DEFAULT '{LEGACY_OWNER_ID}'"
            )
        if image_columns and "aspect_ratio" not in image_columns:
            conn.execute("ALTER TABLE image_history ADD COLUMN aspect_ratio TEXT NOT NULL DEFAULT ''")

        task_columns = _table_columns(conn, "image_tasks")
        if task_columns and "aspect_ratio" not in task_columns:
            conn.execute("ALTER TABLE image_tasks ADD COLUMN aspect_ratio TEXT NOT NULL DEFAULT ''")

        ledger_columns = _table_columns(conn, "ledger_entries")
        if "owner_id" not in ledger_columns:
            conn.execute(
                f"ALTER TABLE ledger_entries ADD COLUMN owner_id TEXT NOT NULL DEFAULT '{LEGACY_OWNER_ID}'"
            )

        site_settings_columns = _table_columns(conn, "site_settings")
        if "inspiration_sources_json" not in site_settings_columns:
            conn.execute("ALTER TABLE site_settings ADD COLUMN inspiration_sources_json TEXT NOT NULL DEFAULT '[]'")
        if "provider_base_url" not in site_settings_columns:
            conn.execute("ALTER TABLE site_settings ADD COLUMN provider_base_url TEXT NOT NULL DEFAULT ''")
        if "auth_base_url" not in site_settings_columns:
            conn.execute("ALTER TABLE site_settings ADD COLUMN auth_base_url TEXT NOT NULL DEFAULT ''")

        self._ensure_site_settings(conn, settings)

        if self._owner_config_exists(conn, LEGACY_OWNER_ID):
            return

        if not _table_exists(conn, "app_config"):
            return

        row = conn.execute("SELECT * FROM app_config WHERE id = 1").fetchone()
        if row is None:
            return

        self._insert_owner_config(
            conn,
            LEGACY_OWNER_ID,
            settings,
            {
                "api_key": row["api_key"],
                "managed_api_key": "",
                "base_url": row["base_url"],
                "usage_path": row["usage_path"],
                "model": row["model"],
                "default_size": row["default_size"],
                "default_quality": row["default_quality"],
                "user_name": row["user_name"],
                "managed_by_auth": 0,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )

    def _migrate_public_cases_from_user_gallery(self, conn: sqlite3.Connection) -> None:
        if not _table_exists(conn, "inspiration_prompts") or not _table_exists(conn, "public_cases"):
            return
        rows = conn.execute(
            """
            SELECT p.*, h.owner_id AS history_owner_id, h.image_path AS history_image_path,
                   h.model AS history_model, h.size AS history_size, h.aspect_ratio AS history_aspect_ratio,
                   h.quality AS history_quality, h.created_at AS history_created_at
            FROM inspiration_prompts p
            LEFT JOIN image_history h ON h.id = p.source_item_id
            WHERE p.source_url = ?
            """,
            (USER_GALLERY_SOURCE_URL,),
        ).fetchall()
        for row in rows:
            raw = _json_load(row["raw_json"]) or {}
            history_id = str(raw.get("history_id") or row["source_item_id"])
            owner_id = str(raw.get("owner_id") or row["history_owner_id"] or LEGACY_OWNER_ID)
            created_at = row["created_at"] or row["history_created_at"] or utc_now()
            record = {
                "id": row["id"] or f"user-{history_id}",
                "owner_id": owner_id,
                "history_id": history_id,
                "title": row["title"] or _inspiration_title_from_prompt(row["prompt"]),
                "author": row["author"],
                "prompt": row["prompt"],
                "image_url": row["image_url"],
                "image_path": row["history_image_path"],
                "model": raw.get("model") or row["history_model"] or "",
                "size": raw.get("size") or row["history_size"] or "",
                "aspect_ratio": raw.get("aspect_ratio") or row["history_aspect_ratio"] or "",
                "quality": raw.get("quality") or row["history_quality"] or "",
                "status": "visible",
                "source_type": "user_history",
                "created_by_admin": 0,
                "created_at": created_at,
                "updated_at": row["updated_at"] or created_at,
            }
            conn.execute(
                """
                INSERT INTO public_cases (
                    id, owner_id, history_id, title, author, prompt, image_url, image_path,
                    model, size, aspect_ratio, quality, status, source_type, created_by_admin,
                    created_at, updated_at
                )
                VALUES (
                    :id, :owner_id, :history_id, :title, :author, :prompt, :image_url, :image_path,
                    :model, :size, :aspect_ratio, :quality, :status, :source_type, :created_by_admin,
                    :created_at, :updated_at
                )
                ON CONFLICT(history_id) DO NOTHING
                """,
                record,
            )

    def _ensure_site_settings(self, conn: sqlite3.Connection, settings: Settings | None = None) -> None:
        row = conn.execute("SELECT * FROM site_settings WHERE id = 1").fetchone()
        now = utc_now()
        sources_json = _json_or_none([])
        if row is None:
            conn.execute(
                """
                INSERT INTO site_settings (
                    id, default_locale, announcement_enabled, announcement_title,
                    announcement_body, announcement_updated_at, inspiration_sources_json,
                    created_at, updated_at
                )
                VALUES (1, ?, 1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    DEFAULT_SITE_LOCALE,
                    DEFAULT_ANNOUNCEMENT_TITLE,
                    DEFAULT_ANNOUNCEMENT_BODY,
                    now,
                    sources_json,
                    now,
                    now,
                ),
            )
            return

        needs_default_announcement = (
            not str(row["announcement_title"] or "").strip()
            and not str(row["announcement_body"] or "").strip()
            and int(row["announcement_enabled"] or 0) == 0
            and row["announcement_updated_at"] == row["created_at"]
        )
        needs_brand_announcement_migration = (
            str(row["announcement_title"] or "") == OLD_DEFAULT_ANNOUNCEMENT_TITLE
            and str(row["announcement_body"] or "") == OLD_DEFAULT_ANNOUNCEMENT_BODY
        ) or (
            str(row["announcement_title"] or "") == DEFAULT_ANNOUNCEMENT_TITLE
            and str(row["announcement_body"] or "") == OLD_JIKE_ANNOUNCEMENT_BODY_WITH_JOKO_CONTACT
        )
        updates: dict[str, Any] = {}
        if not str(row["default_locale"] or "").strip():
            updates["default_locale"] = DEFAULT_SITE_LOCALE
        if needs_default_announcement or needs_brand_announcement_migration:
            updates["announcement_enabled"] = 1
            updates["announcement_title"] = DEFAULT_ANNOUNCEMENT_TITLE
            updates["announcement_body"] = DEFAULT_ANNOUNCEMENT_BODY
            updates["announcement_updated_at"] = now
        if updates:
            updates["updated_at"] = now
            assignments = ", ".join(f"{key} = ?" for key in updates)
            values = list(updates.values())
            values.append(1)
            conn.execute(f"UPDATE site_settings SET {assignments} WHERE id = ?", values)

    def _insert_owner_config(
        self,
        conn: sqlite3.Connection,
        owner_id: str,
        settings: Settings,
        overrides: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now()
        values = {
            "owner_id": owner_id,
            "api_key": "",
            "managed_api_key": "",
            "base_url": settings.provider_base_url,
            "usage_path": settings.provider_usage_path,
            "model": settings.image_model,
            "default_size": settings.default_size,
            "default_quality": settings.default_quality,
            "user_name": settings.user_name,
            "managed_by_auth": 0,
            "created_at": now,
            "updated_at": now,
        }
        if overrides:
            values.update({key: value for key, value in overrides.items() if value is not None})
        conn.execute(
            """
            INSERT INTO owner_config (
                owner_id, api_key, managed_api_key, base_url, usage_path, model, default_size,
                default_quality, user_name, managed_by_auth, created_at, updated_at
            )
            VALUES (
                :owner_id, :api_key, :managed_api_key, :base_url, :usage_path, :model, :default_size,
                :default_quality, :user_name, :managed_by_auth, :created_at, :updated_at
            )
            """,
            values,
        )

    def _owner_config_exists(self, conn: sqlite3.Connection, owner_id: str) -> bool:
        row = conn.execute("SELECT owner_id FROM owner_config WHERE owner_id = ?", (owner_id,)).fetchone()
        return row is not None

    def get_config(self, owner_id: str, settings: Settings, user_name: str | None = None) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM owner_config WHERE owner_id = ?", (owner_id,)).fetchone()
            if row is None:
                self._insert_owner_config(
                    conn,
                    owner_id,
                    settings,
                    {"user_name": user_name or settings.user_name},
                )
                row = conn.execute("SELECT * FROM owner_config WHERE owner_id = ?", (owner_id,)).fetchone()
            elif user_name and row["managed_by_auth"] and row["user_name"] != user_name:
                conn.execute(
                    "UPDATE owner_config SET user_name = ?, updated_at = ? WHERE owner_id = ?",
                    (user_name, utc_now(), owner_id),
                )
                row = conn.execute("SELECT * FROM owner_config WHERE owner_id = ?", (owner_id,)).fetchone()
            if row is None:
                raise RuntimeError("owner_config was not initialized")
            config = _config_row(row)
            site_row = conn.execute("SELECT provider_base_url FROM site_settings WHERE id = 1").fetchone()
            provider_base_url = str(site_row["provider_base_url"] or "").strip() if site_row else ""
            config["base_url"] = (provider_base_url or settings.provider_base_url).rstrip("/")
            return config

    def update_config(self, owner_id: str, settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "api_key",
            "managed_api_key",
            "base_url",
            "usage_path",
            "model",
            "default_size",
            "default_quality",
            "user_name",
            "managed_by_auth",
        }
        updates = {key: value for key, value in payload.items() if key in allowed and value is not None}
        if not updates:
            return self.get_config(owner_id, settings)

        with self.connect() as conn:
            if not self._owner_config_exists(conn, owner_id):
                self._insert_owner_config(conn, owner_id, settings)
            updates["updated_at"] = utc_now()
            assignments = ", ".join(f"{key} = ?" for key in updates)
            values = list(updates.values())
            values.append(owner_id)
            conn.execute(f"UPDATE owner_config SET {assignments} WHERE owner_id = ?", values)
        return self.get_config(owner_id, settings)

    def get_site_settings(self) -> dict[str, Any]:
        with self.connect() as conn:
            self._ensure_site_settings(conn)
            row = conn.execute("SELECT * FROM site_settings WHERE id = 1").fetchone()
            if row is None:
                raise RuntimeError("site_settings was not initialized")
            return _site_settings_row(row)

    def update_site_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "default_locale",
            "announcement_enabled",
            "announcement_title",
            "announcement_body",
            "announcement_updated_at",
            "provider_base_url",
            "auth_base_url",
        }
        updates = {key: value for key, value in payload.items() if key in allowed and value is not None}
        if not updates:
            return self.get_site_settings()

        with self.connect() as conn:
            self._ensure_site_settings(conn)
            if any(key in updates for key in {"announcement_enabled", "announcement_title", "announcement_body"}):
                updates["announcement_updated_at"] = utc_now()
            updates["updated_at"] = utc_now()
            assignments = ", ".join(f"{key} = ?" for key in updates)
            values = list(updates.values())
            values.append(1)
            conn.execute(f"UPDATE site_settings SET {assignments} WHERE id = ?", values)
        return self.get_site_settings()

    def apply_managed_config(
        self,
        owner_id: str,
        settings: Settings,
        *,
        api_key: str,
        user_name: str,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        current = self.get_config(owner_id, settings, user_name=user_name)
        manual_api_key = str(current.get("manual_api_key") or "")
        previous_managed_api_key = str(current.get("managed_api_key") or "")
        payload = {
            "managed_api_key": api_key,
            "base_url": (base_url or settings.provider_base_url).rstrip("/"),
            "usage_path": settings.provider_usage_path,
            "model": current.get("model") or settings.image_model,
            "user_name": user_name,
            "managed_by_auth": 1,
        }
        preserve_manual_override = bool(current.get("managed_by_auth")) and bool(
            manual_api_key and manual_api_key != previous_managed_api_key
        )
        if not preserve_manual_override:
            payload["api_key"] = ""
        return self.update_config(owner_id, settings, payload)

    def apply_authenticated_config(
        self,
        owner_id: str,
        settings: Settings,
        *,
        user_name: str,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        current = self.get_config(owner_id, settings, user_name=user_name)
        payload: dict[str, Any] = {
            "base_url": (base_url or settings.provider_base_url).rstrip("/"),
            "usage_path": settings.provider_usage_path,
            "model": current.get("model") or settings.image_model,
            "user_name": user_name,
            "managed_by_auth": 1,
        }
        if not current.get("managed_by_auth"):
            payload["api_key"] = ""
        return self.update_config(owner_id, settings, payload)

    def merge_owner_data(
        self,
        from_owner_id: str,
        to_owner_id: str,
        settings: Settings,
        user_name: str | None = None,
    ) -> None:
        if from_owner_id == to_owner_id:
            return

        with self.connect() as conn:
            source_config = conn.execute(
                "SELECT * FROM owner_config WHERE owner_id = ?",
                (from_owner_id,),
            ).fetchone()
            target_config = conn.execute(
                "SELECT * FROM owner_config WHERE owner_id = ?",
                (to_owner_id,),
            ).fetchone()

            if source_config is not None and target_config is None:
                self._insert_owner_config(
                    conn,
                    to_owner_id,
                    settings,
                    {
                        "base_url": source_config["base_url"],
                        "usage_path": source_config["usage_path"],
                        "model": source_config["model"],
                        "default_size": source_config["default_size"],
                        "default_quality": source_config["default_quality"],
                        "user_name": user_name or source_config["user_name"],
                        "managed_by_auth": 0,
                    },
                )
            elif source_config is not None and target_config is not None:
                conn.execute(
                    """
                    UPDATE owner_config
                    SET default_size = COALESCE(NULLIF(default_size, ''), ?),
                        default_quality = COALESCE(NULLIF(default_quality, ''), ?),
                        updated_at = ?
                    WHERE owner_id = ?
                    """,
                    (
                        source_config["default_size"],
                        source_config["default_quality"],
                        utc_now(),
                        to_owner_id,
                    ),
                )

            conn.execute("UPDATE image_history SET owner_id = ? WHERE owner_id = ?", (to_owner_id, from_owner_id))
            conn.execute("UPDATE image_tasks SET owner_id = ? WHERE owner_id = ?", (to_owner_id, from_owner_id))
            conn.execute("UPDATE ledger_entries SET owner_id = ? WHERE owner_id = ?", (to_owner_id, from_owner_id))
            conn.execute("UPDATE public_cases SET owner_id = ? WHERE owner_id = ?", (to_owner_id, from_owner_id))
            conn.execute("UPDATE case_likes SET owner_id = ? WHERE owner_id = ?", (to_owner_id, from_owner_id))
            conn.execute("UPDATE case_comments SET owner_id = ? WHERE owner_id = ?", (to_owner_id, from_owner_id))
            conn.execute("DELETE FROM owner_config WHERE owner_id = ?", (from_owner_id,))

    def create_history(self, owner_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": payload.get("id") or uuid4().hex,
            "owner_id": owner_id,
            "mode": payload["mode"],
            "prompt": payload["prompt"],
            "model": payload["model"],
            "size": payload["size"],
            "aspect_ratio": payload.get("aspect_ratio") or "",
            "quality": payload["quality"],
            "status": payload["status"],
            "image_url": payload.get("image_url"),
            "image_path": payload.get("image_path"),
            "input_image_url": payload.get("input_image_url"),
            "input_image_path": payload.get("input_image_path"),
            "revised_prompt": payload.get("revised_prompt"),
            "usage_json": _json_or_none(payload.get("usage")),
            "provider_response_json": _json_or_none(payload.get("provider_response")),
            "error": payload.get("error"),
            "created_at": now,
            "updated_at": now,
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO image_history (
                    id, owner_id, mode, prompt, model, size, aspect_ratio, quality, status, image_url, image_path,
                    input_image_url, input_image_path, revised_prompt, usage_json,
                    provider_response_json, error, created_at, updated_at
                )
                VALUES (
                    :id, :owner_id, :mode, :prompt, :model, :size, :aspect_ratio, :quality, :status, :image_url,
                    :image_path, :input_image_url, :input_image_path, :revised_prompt,
                    :usage_json, :provider_response_json, :error, :created_at, :updated_at
                )
                """,
                record,
            )
        return self.get_history(owner_id, record["id"])

    def get_history(self, owner_id: str, history_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT h.*, c.id AS published_case_id, c.created_at AS published_at
                FROM image_history h
                LEFT JOIN public_cases c
                    ON c.history_id = h.id AND c.status != 'deleted'
                WHERE h.owner_id = ? AND h.id = ?
                """,
                (owner_id, history_id),
            ).fetchone()
        return _history_row(row) if row else None

    def list_history(self, owner_id: str, limit: int = 30, offset: int = 0, q: str = "") -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        search = f"%{q.strip().lower()}%"
        with self.connect() as conn:
            if q.strip():
                rows = conn.execute(
                    """
                    SELECT h.*, c.id AS published_case_id, c.created_at AS published_at
                    FROM image_history h
                    LEFT JOIN public_cases c
                        ON c.history_id = h.id AND c.status != 'deleted'
                    WHERE h.owner_id = ? AND lower(h.prompt) LIKE ?
                    ORDER BY h.created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (owner_id, search, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT h.*, c.id AS published_case_id, c.created_at AS published_at
                    FROM image_history h
                    LEFT JOIN public_cases c
                        ON c.history_id = h.id AND c.status != 'deleted'
                    WHERE h.owner_id = ?
                    ORDER BY h.created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (owner_id, limit, offset),
                ).fetchall()
        return [_history_row(row) for row in rows]

    def delete_history(self, owner_id: str, history_id: str) -> bool:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE public_cases
                SET status = 'deleted',
                    updated_at = ?
                WHERE history_id = ?
                  AND owner_id = ?
                """,
                (now, history_id, owner_id),
            )
            result = conn.execute(
                "DELETE FROM image_history WHERE owner_id = ? AND id = ?",
                (owner_id, history_id),
            )
            if result.rowcount <= 0:
                return False
            self._cleanup_task_history_refs(conn, owner_id, [history_id], now)
            return True

    def cleanup_expired_history(self, cutoff: str) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as conn:
            protected_history = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM image_history h
                WHERE h.created_at < ?
                  AND EXISTS (
                    SELECT 1
                    FROM public_cases c
                    WHERE c.history_id = h.id
                      AND c.status != 'deleted'
                  )
                """,
                (cutoff,),
            ).fetchone()
            rows = conn.execute(
                """
                SELECT h.id, h.owner_id, h.image_path, h.input_image_path
                FROM image_history h
                WHERE h.created_at < ?
                  AND NOT EXISTS (
                    SELECT 1
                    FROM public_cases c
                    WHERE c.history_id = h.id
                      AND c.status != 'deleted'
                  )
                """,
                (cutoff,),
            ).fetchall()
            owner_history_ids: dict[str, list[str]] = {}
            file_paths: set[str] = set()
            deleted_history = 0
            for row in rows:
                owner_id = str(row["owner_id"])
                history_id = str(row["id"])
                for key in ("image_path", "input_image_path"):
                    path = str(row[key] or "").strip()
                    if path:
                        file_paths.add(path)
                result = conn.execute(
                    "DELETE FROM image_history WHERE owner_id = ? AND id = ?",
                    (owner_id, history_id),
                )
                if result.rowcount <= 0:
                    continue
                deleted_history += result.rowcount
                owner_history_ids.setdefault(owner_id, []).append(history_id)

            task_stats = {"deleted_tasks": 0, "updated_tasks": 0}
            for owner_id, history_ids in owner_history_ids.items():
                owner_stats = self._cleanup_task_history_refs(conn, owner_id, history_ids, now)
                task_stats["deleted_tasks"] += owner_stats["deleted_tasks"]
                task_stats["updated_tasks"] += owner_stats["updated_tasks"]

        return {
            "cutoff": cutoff,
            "deleted_history": deleted_history,
            "protected_history": int(protected_history["count"] if protected_history else 0),
            "deleted_tasks": task_stats["deleted_tasks"],
            "updated_tasks": task_stats["updated_tasks"],
            "file_paths": sorted(file_paths),
        }

    def referenced_storage_paths(self, paths: list[str]) -> set[str]:
        candidates = sorted({str(path).strip() for path in paths if str(path).strip()})
        if not candidates:
            return set()
        placeholders = ", ".join("?" for _ in candidates)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT image_path AS path
                FROM image_history
                WHERE image_path IN ({placeholders})
                UNION
                SELECT input_image_path AS path
                FROM image_history
                WHERE input_image_path IN ({placeholders})
                UNION
                SELECT image_path AS path
                FROM public_cases
                WHERE status != 'deleted'
                  AND image_path IN ({placeholders})
                UNION
                SELECT input_image_path AS path
                FROM image_tasks
                WHERE status IN ('queued', 'running')
                  AND input_image_path IN ({placeholders})
                """,
                (*candidates, *candidates, *candidates, *candidates),
            ).fetchall()
        return {str(row["path"]) for row in rows if row["path"]}

    def _cleanup_task_history_refs(
        self,
        conn: sqlite3.Connection,
        owner_id: str,
        history_ids: list[str],
        now: str,
    ) -> dict[str, int]:
        deleted = {str(item) for item in history_ids}
        if not deleted:
            return {"deleted_tasks": 0, "updated_tasks": 0}
        deleted_tasks = 0
        updated_tasks = 0
        task_rows = conn.execute(
            """
            SELECT id, status, result_history_ids_json
            FROM image_tasks
            WHERE owner_id = ?
              AND result_history_ids_json IS NOT NULL
            """,
            (owner_id,),
        ).fetchall()
        for row in task_rows:
            current_ids = _json_load(row["result_history_ids_json"]) or []
            if not isinstance(current_ids, list):
                continue
            next_ids = [item_id for item_id in current_ids if str(item_id) not in deleted]
            if len(next_ids) == len(current_ids):
                continue
            if not next_ids and row["status"] in {"succeeded", "failed"}:
                result = conn.execute("DELETE FROM image_tasks WHERE owner_id = ? AND id = ?", (owner_id, row["id"]))
                deleted_tasks += max(result.rowcount, 0)
                continue
            result = conn.execute(
                """
                UPDATE image_tasks
                SET result_history_ids_json = ?,
                    updated_at = ?
                WHERE owner_id = ?
                  AND id = ?
                """,
                (_json_or_none(next_ids), now, owner_id, row["id"]),
            )
            updated_tasks += max(result.rowcount, 0)
        return {"deleted_tasks": deleted_tasks, "updated_tasks": updated_tasks}

    def create_image_task(self, owner_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": payload.get("id") or uuid4().hex,
            "owner_id": owner_id,
            "mode": payload["mode"],
            "prompt": payload["prompt"],
            "model": payload["model"],
            "size": payload["size"],
            "aspect_ratio": payload.get("aspect_ratio") or "",
            "quality": payload["quality"],
            "status": payload.get("status", "queued"),
            "request_json": _json_or_none(payload.get("request")),
            "input_image_url": payload.get("input_image_url"),
            "input_image_path": payload.get("input_image_path"),
            "result_history_ids_json": _json_or_none(payload.get("result_history_ids") or []),
            "result_json": _json_or_none(payload.get("result")),
            "error": payload.get("error"),
            "created_at": now,
            "updated_at": now,
            "started_at": payload.get("started_at"),
            "completed_at": payload.get("completed_at"),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO image_tasks (
                    id, owner_id, mode, prompt, model, size, aspect_ratio, quality, status, request_json,
                    input_image_url, input_image_path, result_history_ids_json, result_json, error,
                    created_at, updated_at, started_at, completed_at
                )
                VALUES (
                    :id, :owner_id, :mode, :prompt, :model, :size, :aspect_ratio, :quality, :status, :request_json,
                    :input_image_url, :input_image_path, :result_history_ids_json, :result_json, :error,
                    :created_at, :updated_at, :started_at, :completed_at
                )
                """,
                record,
            )
        return self.get_image_task(owner_id, record["id"])

    def get_image_task(self, owner_id: str, task_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM image_tasks WHERE owner_id = ? AND id = ?",
                (owner_id, task_id),
            ).fetchone()
        if row is None:
            return None
        return _image_task_row(row)

    def list_image_tasks(
        self,
        owner_id: str,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        clauses = ["owner_id = ?"]
        params: list[Any] = [owner_id]
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(statuses)
        where = " AND ".join(clauses)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM image_tasks
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [_image_task_row(row) for row in rows]

    def update_image_task(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        updates: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {"status", "input_image_url", "input_image_path", "error", "started_at", "completed_at"}:
                updates[key] = value
            elif key == "request":
                updates["request_json"] = _json_or_none(value)
            elif key == "request_json":
                updates["request_json"] = value
            elif key == "result_history_ids":
                updates["result_history_ids_json"] = _json_or_none(value or [])
            elif key == "result_history_ids_json":
                updates["result_history_ids_json"] = value
            elif key == "result":
                updates["result_json"] = _json_or_none(value)
            elif key == "result_json":
                updates["result_json"] = value
        if not updates:
            return self.get_image_task_by_id(task_id)
        with self.connect() as conn:
            row = conn.execute("SELECT owner_id FROM image_tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            updates["updated_at"] = utc_now()
            assignments = ", ".join(f"{key} = ?" for key in updates)
            values = list(updates.values())
            values.append(task_id)
            conn.execute(f"UPDATE image_tasks SET {assignments} WHERE id = ?", values)
        return self.get_image_task(str(row["owner_id"]), task_id)

    def get_image_task_by_id(self, task_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM image_tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return _image_task_row(row)

    def get_history_items(self, owner_id: str, history_ids: list[str]) -> list[dict[str, Any]]:
        if not history_ids:
            return []
        placeholders = ", ".join("?" for _ in history_ids)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT h.*, c.id AS published_case_id, c.created_at AS published_at
                FROM image_history h
                LEFT JOIN public_cases c
                    ON c.history_id = h.id AND c.status != 'deleted'
                WHERE h.owner_id = ? AND h.id IN ({placeholders})
                """,
                (owner_id, *history_ids),
            ).fetchall()
        items: dict[str, dict[str, Any]] = {}
        for row in rows:
            record = _history_row(row)
            items[record["id"]] = record
        return [items[item_id] for item_id in history_ids if item_id in items]

    def publish_history_as_case(self, owner_id: str, history_id: str, author: str) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as conn:
            history = conn.execute(
                "SELECT * FROM image_history WHERE owner_id = ? AND id = ?",
                (owner_id, history_id),
            ).fetchone()
            if history is None:
                return None
            if history["status"] != "succeeded" or not history["image_url"]:
                raise ValueError("Only successful history items with an image can be published")

            record = {
                "id": f"user-{history_id}",
                "title": _inspiration_title_from_prompt(history["prompt"]),
                "history_id": history_id,
                "owner_id": owner_id,
                "author": author,
                "prompt": history["prompt"],
                "image_url": history["image_url"],
                "image_path": history["image_path"],
                "model": history["model"],
                "size": history["size"],
                "aspect_ratio": history["aspect_ratio"],
                "quality": history["quality"],
                "status": "visible",
                "source_type": "user_history",
                "created_by_admin": 0,
                "created_at": now,
                "updated_at": now,
            }
            conn.execute(
                """
                INSERT INTO public_cases (
                    id, owner_id, history_id, title, author, prompt, image_url, image_path,
                    model, size, aspect_ratio, quality, status, source_type, created_by_admin,
                    created_at, updated_at
                )
                VALUES (
                    :id, :owner_id, :history_id, :title, :author, :prompt, :image_url, :image_path,
                    :model, :size, :aspect_ratio, :quality, :status, :source_type, :created_by_admin,
                    :created_at, :updated_at
                )
                ON CONFLICT(history_id) DO UPDATE SET
                    title = excluded.title,
                    owner_id = excluded.owner_id,
                    author = excluded.author,
                    prompt = excluded.prompt,
                    image_url = excluded.image_url,
                    image_path = excluded.image_path,
                    model = excluded.model,
                    size = excluded.size,
                    aspect_ratio = excluded.aspect_ratio,
                    quality = excluded.quality,
                    status = 'visible',
                    source_type = 'user_history',
                    created_by_admin = 0,
                    updated_at = excluded.updated_at
                """,
                record,
            )
            row = conn.execute(
                "SELECT * FROM public_cases WHERE history_id = ? AND owner_id = ? AND status != 'deleted'",
                (history_id, owner_id),
            ).fetchone()
            return _case_row(conn, row, owner_id) if row else None

    def unpublish_history_case(self, owner_id: str, history_id: str) -> bool:
        with self.connect() as conn:
            result = conn.execute(
                """
                UPDATE public_cases
                SET status = 'deleted',
                    updated_at = ?
                WHERE history_id = ?
                  AND owner_id = ?
                  AND status != 'deleted'
                """,
                (utc_now(), history_id, owner_id),
            )
            return result.rowcount > 0

    def fail_incomplete_tasks(self, message: str) -> int:
        now = utc_now()
        with self.connect() as conn:
            result = conn.execute(
                """
                UPDATE image_tasks
                SET status = 'failed',
                    error = ?,
                    completed_at = COALESCE(completed_at, ?),
                    updated_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (message, now, now),
            )
            return int(result.rowcount or 0)

    def add_ledger_entry(self, owner_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = {
            "id": payload.get("id") or uuid4().hex,
            "owner_id": owner_id,
            "event_type": payload["event_type"],
            "amount": payload.get("amount", 0),
            "currency": payload.get("currency", "USD"),
            "description": payload["description"],
            "history_id": payload.get("history_id"),
            "metadata_json": _json_or_none(payload.get("metadata")),
            "created_at": utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO ledger_entries (
                    id, owner_id, event_type, amount, currency, description, history_id,
                    metadata_json, created_at
                )
                VALUES (
                    :id, :owner_id, :event_type, :amount, :currency, :description, :history_id,
                    :metadata_json, :created_at
                )
                """,
                record,
            )
        return record

    def list_ledger(self, owner_id: str, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ledger_entries WHERE owner_id = ? ORDER BY created_at DESC LIMIT ?",
                (owner_id, limit),
            ).fetchall()
        return [_ledger_row(row) for row in rows]

    def create_session(
        self,
        *,
        owner_id: str,
        sub2api_user_id: int,
        email: str,
        username: str,
        role: str,
        ttl_seconds: int,
        access_token: str = "",
        refresh_token: str = "",
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": secrets.token_urlsafe(32),
            "owner_id": owner_id,
            "sub2api_user_id": sub2api_user_id,
            "email": email,
            "username": username or "",
            "role": role or "user",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "created_at": now,
            "updated_at": now,
            "expires_at": utc_after(ttl_seconds),
            "user_agent": user_agent,
            "ip_address": ip_address,
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO user_sessions (
                    id, owner_id, sub2api_user_id, email, username, role, access_token, refresh_token,
                    created_at, updated_at, expires_at, user_agent, ip_address
                )
                VALUES (
                    :id, :owner_id, :sub2api_user_id, :email, :username, :role, :access_token, :refresh_token,
                    :created_at, :updated_at, :expires_at, :user_agent, :ip_address
                )
                """,
                record,
            )
        return record

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        if not session_id:
            return None
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM user_sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                return None
            data = dict(row)
            if _is_expired(data["expires_at"]):
                conn.execute("DELETE FROM user_sessions WHERE id = ?", (session_id,))
                return None
            return data

    def latest_session_for_owner(self, owner_id: str) -> dict[str, Any] | None:
        if not owner_id:
            return None
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM user_sessions
                WHERE owner_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (owner_id,),
            ).fetchone()
            if row is None:
                return None
            data = dict(row)
            if _is_expired(data["expires_at"]):
                conn.execute("DELETE FROM user_sessions WHERE id = ?", (data["id"],))
                return None
            return data

    def touch_session(self, session_id: str, ttl_seconds: int) -> None:
        if not session_id:
            return
        with self.connect() as conn:
            conn.execute(
                "UPDATE user_sessions SET updated_at = ?, expires_at = ? WHERE id = ?",
                (utc_now(), utc_after(ttl_seconds), session_id),
            )

    def delete_session(self, session_id: str) -> None:
        if not session_id:
            return
        with self.connect() as conn:
            conn.execute("DELETE FROM user_sessions WHERE id = ?", (session_id,))

    def stats(self, owner_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS succeeded,
                    SUM(CASE WHEN mode = 'edit' THEN 1 ELSE 0 END) AS edits,
                    MAX(created_at) AS last_generation_at
                FROM image_history
                WHERE owner_id = ?
                """,
                (owner_id,),
            ).fetchone()
        return {
            "total": int(row["total"] or 0),
            "succeeded": int(row["succeeded"] or 0),
            "edits": int(row["edits"] or 0),
            "last_generation_at": row["last_generation_at"],
        }

    def list_public_cases(
        self,
        viewer_owner_id: str | None = None,
        limit: int = 48,
        offset: int = 0,
        q: str = "",
        sort: str = "latest",
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        clauses = ["p.status = 'visible'", "p.image_url IS NOT NULL", "p.image_url != ''"]
        params: list[Any] = []
        if q.strip():
            search = f"%{q.strip().lower()}%"
            clauses.append("(lower(p.title) LIKE ? OR lower(p.prompt) LIKE ? OR lower(COALESCE(p.author, '')) LIKE ?)")
            params.extend([search, search, search])
        where = " AND ".join(clauses)
        order_by = _public_case_order_by(sort)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT p.*
                FROM public_cases p
                WHERE {where}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
            return [_case_row(conn, row, viewer_owner_id) for row in rows]

    def count_public_cases(self, q: str = "") -> int:
        clauses = ["p.status = 'visible'", "p.image_url IS NOT NULL", "p.image_url != ''"]
        params: list[Any] = []
        if q.strip():
            search = f"%{q.strip().lower()}%"
            clauses.append("(lower(p.title) LIKE ? OR lower(p.prompt) LIKE ? OR lower(COALESCE(p.author, '')) LIKE ?)")
            params.extend([search, search, search])
        where = " AND ".join(clauses)
        with self.connect() as conn:
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM public_cases p
                WHERE {where}
                """,
                params,
            ).fetchone()
        return int(row["count"] or 0) if row else 0

    def list_admin_cases(self, limit: int = 80, offset: int = 0, q: str = "") -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if q.strip():
            search = f"%{q.strip().lower()}%"
            clauses.append("(lower(title) LIKE ? OR lower(prompt) LIKE ? OR lower(COALESCE(author, '')) LIKE ?)")
            params.extend([search, search, search])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM public_cases
                {where}
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
            return [_case_row(conn, row, None) for row in rows]

    def get_public_case(
        self,
        case_id: str,
        viewer_owner_id: str | None = None,
        *,
        include_hidden: bool = False,
    ) -> dict[str, Any] | None:
        with self.connect() as conn:
            if include_hidden:
                row = conn.execute("SELECT * FROM public_cases WHERE id = ?", (case_id,)).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM public_cases WHERE id = ? AND status = 'visible'",
                    (case_id,),
                ).fetchone()
            return _case_row(conn, row, viewer_owner_id) if row else None

    def public_case_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN source_type = 'user_history' THEN 1 ELSE 0 END) AS user_cases,
                    SUM(CASE WHEN source_type = 'admin_manual' THEN 1 ELSE 0 END) AS admin_cases,
                    MAX(created_at) AS last_case_at
                FROM public_cases
                WHERE status = 'visible'
                """
            ).fetchone()
            likes = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM case_likes cl
                JOIN public_cases pc ON pc.id = cl.case_id
                WHERE pc.status = 'visible'
                """
            ).fetchone()
            comments = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM case_comments cc
                JOIN public_cases pc ON pc.id = cc.case_id
                WHERE cc.status = 'visible' AND pc.status = 'visible'
                """
            ).fetchone()
        return {
            "total": int(row["total"] or 0),
            "user_cases": int(row["user_cases"] or 0),
            "admin_cases": int(row["admin_cases"] or 0),
            "likes": int(likes["total"] or 0),
            "comments": int(comments["total"] or 0),
            "last_case_at": row["last_case_at"],
        }

    def create_admin_case(self, owner_id: str, author: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        record = {
            "id": payload.get("id") or uuid4().hex,
            "owner_id": owner_id,
            "history_id": None,
            "title": str(payload.get("title") or _inspiration_title_from_prompt(str(payload.get("prompt") or ""))).strip(),
            "author": str(payload.get("author") or author).strip(),
            "prompt": str(payload.get("prompt") or "").strip(),
            "image_url": str(payload.get("image_url") or "").strip() or None,
            "image_path": str(payload.get("image_path") or "").strip() or None,
            "model": str(payload.get("model") or "").strip(),
            "size": str(payload.get("size") or "").strip(),
            "aspect_ratio": str(payload.get("aspect_ratio") or "").strip(),
            "quality": str(payload.get("quality") or "").strip(),
            "status": str(payload.get("status") or "visible").strip(),
            "source_type": "admin_manual",
            "created_by_admin": 1,
            "created_at": now,
            "updated_at": now,
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO public_cases (
                    id, owner_id, history_id, title, author, prompt, image_url, image_path,
                    model, size, aspect_ratio, quality, status, source_type, created_by_admin,
                    created_at, updated_at
                )
                VALUES (
                    :id, :owner_id, :history_id, :title, :author, :prompt, :image_url, :image_path,
                    :model, :size, :aspect_ratio, :quality, :status, :source_type, :created_by_admin,
                    :created_at, :updated_at
                )
                """,
                record,
            )
            row = conn.execute("SELECT * FROM public_cases WHERE id = ?", (record["id"],)).fetchone()
            return _case_row(conn, row, owner_id)

    def update_case(self, case_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {
            "title",
            "author",
            "prompt",
            "image_url",
            "image_path",
            "model",
            "size",
            "aspect_ratio",
            "quality",
            "status",
        }
        updates = {key: value for key, value in payload.items() if key in allowed and value is not None}
        if not updates:
            return self.get_public_case(case_id, include_hidden=True)
        updates["updated_at"] = utc_now()
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM public_cases WHERE id = ?", (case_id,)).fetchone()
            if row is None:
                return None
            assignments = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(f"UPDATE public_cases SET {assignments} WHERE id = ?", (*updates.values(), case_id))
            updated = conn.execute("SELECT * FROM public_cases WHERE id = ?", (case_id,)).fetchone()
            return _case_row(conn, updated, None)

    def like_case(self, case_id: str, owner_id: str) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as conn:
            case = conn.execute("SELECT * FROM public_cases WHERE id = ? AND status = 'visible'", (case_id,)).fetchone()
            if case is None:
                return None
            conn.execute(
                """
                INSERT OR IGNORE INTO case_likes (id, case_id, owner_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (uuid4().hex, case_id, owner_id, now),
            )
            return _case_row(conn, case, owner_id)

    def unlike_case(self, case_id: str, owner_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            case = conn.execute("SELECT * FROM public_cases WHERE id = ? AND status = 'visible'", (case_id,)).fetchone()
            if case is None:
                return None
            conn.execute("DELETE FROM case_likes WHERE case_id = ? AND owner_id = ?", (case_id, owner_id))
            return _case_row(conn, case, owner_id)

    def list_case_comments(
        self,
        case_id: str,
        viewer_owner_id: str | None = None,
        *,
        is_admin: bool = False,
    ) -> list[dict[str, Any]]:
        with self.connect() as conn:
            case = conn.execute(
                "SELECT id FROM public_cases WHERE id = ? AND (? OR status = 'visible')",
                (case_id, 1 if is_admin else 0),
            ).fetchone()
            if case is None:
                return []
            where = "case_id = ?" if is_admin else "case_id = ? AND status = 'visible'"
            rows = conn.execute(
                f"""
                SELECT *
                FROM case_comments
                WHERE {where}
                ORDER BY created_at ASC
                """,
                (case_id,),
            ).fetchall()
            return [_comment_row(row, viewer_owner_id, is_admin) for row in rows]

    def list_admin_comments(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT cc.*, pc.title AS case_title
                FROM case_comments cc
                JOIN public_cases pc ON pc.id = cc.case_id
                ORDER BY cc.updated_at DESC, cc.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
            return [_comment_row(row, None, True) for row in rows]

    def create_case_comment(self, case_id: str, owner_id: str, author: str, body: str) -> dict[str, Any] | None:
        now = utc_now()
        clean_body = body.strip()
        with self.connect() as conn:
            case = conn.execute("SELECT id FROM public_cases WHERE id = ? AND status = 'visible'", (case_id,)).fetchone()
            if case is None:
                return None
            record = {
                "id": uuid4().hex,
                "case_id": case_id,
                "owner_id": owner_id,
                "author": author,
                "body": clean_body,
                "status": "visible",
                "created_at": now,
                "updated_at": now,
            }
            conn.execute(
                """
                INSERT INTO case_comments (id, case_id, owner_id, author, body, status, created_at, updated_at)
                VALUES (:id, :case_id, :owner_id, :author, :body, :status, :created_at, :updated_at)
                """,
                record,
            )
            row = conn.execute("SELECT * FROM case_comments WHERE id = ?", (record["id"],)).fetchone()
            return _comment_row(row, owner_id, False)

    def create_admin_case_comment(
        self,
        case_id: str,
        owner_id: str,
        author: str,
        body: str,
        *,
        status: str = "visible",
    ) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as conn:
            case = conn.execute("SELECT id FROM public_cases WHERE id = ? AND status != 'deleted'", (case_id,)).fetchone()
            if case is None:
                return None
            record = {
                "id": uuid4().hex,
                "case_id": case_id,
                "owner_id": owner_id,
                "author": author.strip(),
                "body": body.strip(),
                "status": status,
                "created_at": now,
                "updated_at": now,
            }
            conn.execute(
                """
                INSERT INTO case_comments (id, case_id, owner_id, author, body, status, created_at, updated_at)
                VALUES (:id, :case_id, :owner_id, :author, :body, :status, :created_at, :updated_at)
                """,
                record,
            )
            row = conn.execute("SELECT * FROM case_comments WHERE id = ?", (record["id"],)).fetchone()
            return _comment_row(row, owner_id, True)

    def update_case_comment(
        self,
        comment_id: str,
        *,
        owner_id: str | None = None,
        is_admin: bool = False,
        body: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any] | None:
        updates: dict[str, Any] = {}
        if body is not None:
            updates["body"] = body.strip()
        if status is not None:
            updates["status"] = status
        if not updates:
            with self.connect() as conn:
                row = conn.execute("SELECT * FROM case_comments WHERE id = ?", (comment_id,)).fetchone()
                return _comment_row(row, owner_id, is_admin) if row else None
        updates["updated_at"] = utc_now()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM case_comments WHERE id = ?", (comment_id,)).fetchone()
            if row is None:
                return None
            if not is_admin and row["owner_id"] != owner_id:
                raise PermissionError("Comment owner mismatch")
            assignments = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(f"UPDATE case_comments SET {assignments} WHERE id = ?", (*updates.values(), comment_id))
            updated = conn.execute("SELECT * FROM case_comments WHERE id = ?", (comment_id,)).fetchone()
            return _comment_row(updated, owner_id, is_admin)

    def upsert_inspirations(self, source_url: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        now = utc_now()
        changed = 0
        with self.connect() as conn:
            for item in items:
                record = {
                    "id": item["id"],
                    "source_url": source_url,
                    "source_item_id": item["source_item_id"],
                    "section": item["section"],
                    "title": item["title"],
                    "author": item.get("author"),
                    "prompt": item["prompt"],
                    "image_url": item.get("image_url"),
                    "source_link": item.get("source_link"),
                    "raw_json": _json_or_none(item.get("raw")),
                    "synced_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
                conn.execute(
                    """
                    INSERT INTO inspiration_prompts (
                        id, source_url, source_item_id, section, title, author, prompt,
                        image_url, source_link, raw_json, synced_at, created_at, updated_at
                    )
                    VALUES (
                        :id, :source_url, :source_item_id, :section, :title, :author,
                        :prompt, :image_url, :source_link, :raw_json, :synced_at,
                        :created_at, :updated_at
                    )
                    ON CONFLICT(source_url, source_item_id) DO UPDATE SET
                        section = excluded.section,
                        title = excluded.title,
                        author = excluded.author,
                        prompt = excluded.prompt,
                        image_url = excluded.image_url,
                        source_link = excluded.source_link,
                        raw_json = excluded.raw_json,
                        synced_at = excluded.synced_at,
                        updated_at = excluded.updated_at
                    """,
                    record,
                )
                changed += 1
        return {"count": changed, "synced_at": now}

    def list_inspirations(
        self,
        limit: int = 48,
        offset: int = 0,
        q: str = "",
        section: str = "",
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        clauses = []
        params: list[Any] = []
        if q.strip():
            clauses.append("(lower(title) LIKE ? OR lower(prompt) LIKE ? OR lower(author) LIKE ?)")
            search = f"%{q.strip().lower()}%"
            params.extend([search, search, search])
        if section.strip():
            clauses.append("section = ?")
            params.append(section.strip())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM inspiration_prompts
                {where}
                ORDER BY created_at DESC, synced_at DESC, section ASC, title ASC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
        return [_inspiration_row(row) for row in rows]

    def inspiration_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    MAX(synced_at) AS last_synced_at,
                    COUNT(DISTINCT section) AS sections
                FROM inspiration_prompts
                """
            ).fetchone()
            section_rows = conn.execute(
                """
                SELECT section, COUNT(*) AS count
                FROM inspiration_prompts
                GROUP BY section
                ORDER BY section ASC
                """
            ).fetchall()
            source_rows = conn.execute(
                """
                SELECT source_url, COUNT(*) AS count, MAX(synced_at) AS last_synced_at
                FROM inspiration_prompts
                GROUP BY source_url
                ORDER BY last_synced_at DESC, source_url ASC
                """
            ).fetchall()
        return {
            "total": int(row["total"] or 0),
            "last_synced_at": row["last_synced_at"],
            "sections": int(row["sections"] or 0),
            "section_counts": [{"section": item["section"], "count": int(item["count"])} for item in section_rows],
            "source_counts": [
                {
                    "source_url": item["source_url"],
                    "count": int(item["count"] or 0),
                    "last_synced_at": item["last_synced_at"],
                }
                for item in source_rows
            ],
        }


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}


def _is_expired(value: str | None) -> bool:
    if not value:
        return True
    return datetime.fromisoformat(value) <= datetime.now(timezone.utc)


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _json_load(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _history_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["usage"] = _json_load(data.pop("usage_json"))
    data["provider_response"] = _json_load(data.pop("provider_response_json"))
    data["published_case_id"] = data.get("published_case_id")
    data["published_inspiration_id"] = data["published_case_id"]
    data["published_at"] = data.get("published_at")
    data["published"] = bool(data["published_case_id"])
    return data


def _ledger_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["metadata"] = _json_load(data.pop("metadata_json"))
    return data


def _image_task_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["request"] = _json_load(data.pop("request_json"))
    data["result_history_ids"] = _json_load(data.pop("result_history_ids_json")) or []
    data["result"] = _json_load(data.pop("result_json"))
    return data


def _case_row(conn: sqlite3.Connection, row: sqlite3.Row, viewer_owner_id: str | None = None) -> dict[str, Any]:
    data = dict(row)
    data["created_by_admin"] = bool(data.get("created_by_admin"))
    like_row = conn.execute("SELECT COUNT(*) AS count FROM case_likes WHERE case_id = ?", (data["id"],)).fetchone()
    comment_row = conn.execute(
        "SELECT COUNT(*) AS count FROM case_comments WHERE case_id = ? AND status = 'visible'",
        (data["id"],),
    ).fetchone()
    data["like_count"] = int(like_row["count"] or 0)
    data["comment_count"] = int(comment_row["count"] or 0)
    data["liked"] = False
    if viewer_owner_id:
        liked = conn.execute(
            "SELECT 1 FROM case_likes WHERE case_id = ? AND owner_id = ?",
            (data["id"], viewer_owner_id),
        ).fetchone()
        data["liked"] = liked is not None
    return data


def _public_case_order_by(sort: str) -> str:
    if sort == "likes":
        return "(SELECT COUNT(*) FROM case_likes cl WHERE cl.case_id = p.id) DESC, p.created_at DESC, p.updated_at DESC"
    if sort == "comments":
        return (
            "(SELECT COUNT(*) FROM case_comments cc WHERE cc.case_id = p.id AND cc.status = 'visible') DESC, "
            "p.created_at DESC, p.updated_at DESC"
        )
    return "p.created_at DESC, p.updated_at DESC"


def _comment_row(row: sqlite3.Row, viewer_owner_id: str | None = None, is_admin: bool = False) -> dict[str, Any]:
    data = dict(row)
    if not is_admin:
        data["author"] = _mask_public_author(data.get("author"))
    data["can_edit"] = bool(is_admin or (viewer_owner_id and data["owner_id"] == viewer_owner_id))
    data["can_delete"] = data["can_edit"]
    return data


def _mask_public_author(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "@" in text and not text.startswith("@"):
        local, domain = text.split("@", 1)
        if local and "." in domain:
            return f"{_mask_token(local)}@{_mask_domain(domain)}"
    prefix = "@" if text.startswith("@") else ""
    body = text[1:] if prefix else text
    return f"{prefix}{_mask_token(body)}"


def _mask_domain(domain: str) -> str:
    parts = [part for part in domain.split(".") if part]
    if not parts:
        return "***"
    if len(parts) == 1:
        return _mask_short_token(parts[0])
    return ".".join([_mask_short_token(parts[0]), *parts[1:]])


def _mask_token(value: str) -> str:
    text = value.strip()
    if not text:
        return "***"
    if len(text) == 1:
        return "*"
    if len(text) == 2:
        return f"{text[0]}*"
    if len(text) <= 4:
        return f"{text[0]}***{text[-1]}"
    return f"{text[:2]}***{text[-2:]}"


def _mask_short_token(value: str) -> str:
    text = value.strip()
    if not text:
        return "***"
    if len(text) == 1:
        return "*"
    if len(text) == 2:
        return f"{text[0]}*"
    return f"{text[0]}***{text[-1]}"


def _inspiration_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["raw"] = _json_load(data.pop("raw_json"))
    return data


def _inspiration_title_from_prompt(prompt: str) -> str:
    compact = " ".join(prompt.split())
    if len(compact) <= 48:
        return compact or "用户作品"
    return f"{compact[:48].rstrip()}..."


def _site_settings_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data.pop("inspiration_sources_json", None)
    return data


def _config_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    manual_api_key = str(data.get("api_key") or "")
    managed_api_key = str(data.get("managed_api_key") or "")
    effective_api_key = manual_api_key or managed_api_key
    data["manual_api_key"] = manual_api_key
    data["managed_api_key"] = managed_api_key
    data["api_key_source"] = _config_api_key_source(data)
    data["api_key"] = effective_api_key
    return data


def _config_api_key_source(config: dict[str, Any]) -> str:
    if config.get("managed_by_auth"):
        manual_api_key = str(config.get("api_key") or "")
        managed_api_key = str(config.get("managed_api_key") or "")
        if manual_api_key and manual_api_key != managed_api_key:
            return "manual_override"
        return "managed"
    return "manual"
