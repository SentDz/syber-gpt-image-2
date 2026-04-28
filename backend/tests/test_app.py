from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.inspirations import cache_inspiration_images, normalize_inspiration_source_url, parse_inspiration_markdown
from app.main import create_app, _auth_client, _db, _image_size_tier, _provider, _provider_image_size, _settings
from app.provider import ProviderError
from app.settings import Settings


PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class FakeProvider:
    def __init__(self) -> None:
        self.generated_configs: list[dict[str, Any]] = []
        self.generated_payloads: list[dict[str, Any]] = []
        self.edited_configs: list[dict[str, Any]] = []
        self.edited_fields: list[dict[str, Any]] = []
        self.edited_images: list[list[tuple[str, bytes, str]]] = []

    async def test_connection(self, config: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "models": ["gpt-image-2"], "raw": {"data": [{"id": "gpt-image-2"}]}}

    async def usage(self, config: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "remaining": 12.5, "raw": {"remaining": 12.5, "unit": "USD"}}

    async def generate_image(self, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0.02)
        assert payload["model"] == "gpt-image-2"
        self.generated_configs.append(dict(config))
        self.generated_payloads.append(payload)
        return {"created": 123, "data": [{"b64_json": PNG_B64, "revised_prompt": "revised"}], "usage": {"total_tokens": 1}}

    async def edit_image(
        self,
        config: dict[str, Any],
        fields: dict[str, Any],
        images: list[tuple[str, bytes, str]],
        mask: tuple[str, bytes, str] | None = None,
    ) -> dict[str, Any]:
        await asyncio.sleep(0.02)
        assert images
        self.edited_configs.append(dict(config))
        self.edited_fields.append(fields)
        self.edited_images.append(images)
        return {"created": 124, "data": [{"b64_json": PNG_B64}], "usage": {"total_tokens": 2}}


class FlakyProvider(FakeProvider):
    def __init__(self, generate_failures: int) -> None:
        super().__init__()
        self.generate_attempts = 0
        self.generate_failures = generate_failures

    async def generate_image(self, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        self.generate_attempts += 1
        if self.generate_attempts <= self.generate_failures:
            raise ProviderError(
                502,
                "Upstream request failed",
                {"error": {"message": "Upstream request failed", "type": "upstream_error"}},
            )
        return await super().generate_image(config, payload)


class FakeAuthClient:
    def __init__(self) -> None:
        self.public_settings_base_urls: list[str] = []
        self.register_base_urls: list[str] = []
        self.login_base_urls: list[str] = []
        self.login_2fa_base_urls: list[str] = []
        self.list_keys_base_urls: list[str] = []
        self.create_key_base_urls: list[str] = []
        self.list_usage_base_urls: list[str] = []
        self.created_keys: list[dict[str, Any]] = []
        self.usage_logs: list[dict[str, Any]] = [
            {
                "id": 501,
                "request_id": "client:test",
                "model": "gpt-image-2",
                "actual_cost": 0.456,
                "total_cost": 0.456,
                "image_count": 1,
                "image_size": "2K",
                "inbound_endpoint": "/v1/images/generations",
                "billing_mode": "image",
                "created_at": "2026-04-26T10:00:00Z",
            }
        ]

    async def public_settings(self, base_url: str) -> dict[str, Any]:
        self.public_settings_base_urls.append(base_url)
        return {"registration_enabled": True, "email_verify_enabled": False, "backend_mode_enabled": False, "site_name": "demo"}

    async def send_verify_code(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"message": "sent", "countdown": 60}

    async def register(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.register_base_urls.append(base_url)
        return {
            "access_token": "access-demo",
            "refresh_token": "refresh-demo",
            "token_type": "Bearer",
            "user": {"id": 7, "email": payload["email"], "username": "demo-user", "role": "admin"},
        }

    async def login(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.login_base_urls.append(base_url)
        return {
            "access_token": "access-demo",
            "refresh_token": "refresh-demo",
            "token_type": "Bearer",
            "user": {"id": 7, "email": payload["email"], "username": "demo-user", "role": "admin"},
        }

    async def login_2fa(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.login_2fa_base_urls.append(base_url)
        return {
            "access_token": "access-demo",
            "refresh_token": "refresh-demo",
            "token_type": "Bearer",
            "user": {"id": 7, "email": "demo@example.com", "username": "demo-user", "role": "admin"},
        }

    async def list_keys(self, base_url: str, access_token: str) -> list[dict[str, Any]]:
        self.list_keys_base_urls.append(base_url)
        return []

    async def list_available_groups(self, base_url: str, access_token: str) -> list[dict[str, Any]]:
        return [{"id": 42, "name": "image-openai", "platform": "openai"}]

    async def create_key(self, base_url: str, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.create_key_base_urls.append(base_url)
        key = {
            "id": 99,
            "key": "sk-user-managed-123456",
            "name": payload["name"],
            "group": {"id": payload.get("group_id"), "name": "general-openai", "platform": "openai"},
            "status": "active",
        }
        self.created_keys.append(key)
        return key

    async def list_usage(self, base_url: str, access_token: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.list_usage_base_urls.append(base_url)
        return list(self.usage_logs)


class ExistingKeysAuthClient(FakeAuthClient):
    def __init__(self, keys: list[dict[str, Any]], groups: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self.keys = keys
        self.groups = groups or [{"id": 42, "name": "image-openai", "platform": "openai"}]

    async def list_keys(self, base_url: str, access_token: str) -> list[dict[str, Any]]:
        self.list_keys_base_urls.append(base_url)
        return list(self.keys)

    async def list_available_groups(self, base_url: str, access_token: str) -> list[dict[str, Any]]:
        return list(self.groups)


def make_app(tmp_path: Path, auth_client: FakeAuthClient | None = None, provider: FakeProvider | None = None):
    settings = Settings(
        backend_dir=tmp_path,
        database_path=tmp_path / "data" / "app.sqlite3",
        storage_dir=tmp_path / "storage",
        provider_base_url="http://127.0.0.1:9878/v1",
        auth_base_url="http://127.0.0.1:9878",
        provider_usage_path="/v1/usage",
        image_model="gpt-image-2",
        default_size="2K",
        default_quality="auto",
        image_price_1k=0.134,
        image_price_2k=0.201,
        image_price_4k=0.268,
        user_name="tester",
        cors_origins=["http://127.0.0.1:3000"],
        request_timeout_seconds=10,
        session_cookie_name="cybergen_session",
        guest_cookie_name="cybergen_guest",
        session_ttl_seconds=3600,
        guest_ttl_seconds=86400,
        cookie_secure=False,
        image_retention_days=2,
        image_cleanup_interval_seconds=6 * 60 * 60,
    )
    app = create_app(settings=settings, provider=provider or FakeProvider(), auth_client=auth_client or FakeAuthClient())
    app.dependency_overrides[_db] = lambda: app.state.db
    app.dependency_overrides[_settings] = lambda: app.state.settings
    app.dependency_overrides[_provider] = lambda: app.state.provider
    app.dependency_overrides[_auth_client] = lambda: app.state.auth_client
    return app


def make_client(
    tmp_path: Path,
    auth_client: FakeAuthClient | None = None,
    provider: FakeProvider | None = None,
) -> TestClient:
    return TestClient(make_app(tmp_path, auth_client=auth_client, provider=provider))


def wait_for_task(client: TestClient, task_id: str, attempts: int = 60, delay: float = 0.02) -> dict[str, Any]:
    for _ in range(attempts):
        response = client.get(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        task = response.json()
        if task["status"] in {"succeeded", "failed"}:
            return task
        time.sleep(delay)
    raise AssertionError(f"Task {task_id} did not finish in time")


def test_guest_config_masks_api_key(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.put("/api/config", json={"api_key": "sk-test-123456", "user_name": "Neo"})
        assert response.status_code == 200
        data = response.json()
        assert data["api_key_set"] is True
        assert data["api_key_hint"] == "sk-tes...3456"
        assert data["user_name"] == "Neo"
        assert data["managed_by_auth"] is False


def test_guest_history_is_isolated_by_cookie(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    with TestClient(app) as client_a, TestClient(app) as client_b:
        client_a.put("/api/config", json={"api_key": "sk-test-123456"})
        generated = client_a.post("/api/images/generate", json={"prompt": "neon city"})
        assert generated.status_code == 200
        task = wait_for_task(client_a, generated.json()["id"])
        assert task["status"] == "succeeded"
        tasks = client_a.get("/api/tasks").json()["items"]

        history_a = client_a.get("/api/history").json()["items"]
        history_b = client_b.get("/api/history").json()["items"]
        config_b = client_b.get("/api/config").json()
        succeeded_tasks = client_a.get("/api/tasks?status=succeeded").json()["items"]
        queued_tasks = client_a.get("/api/tasks?status=queued").json()["items"]

        assert tasks[0]["id"] == generated.json()["id"]
        assert succeeded_tasks[0]["id"] == generated.json()["id"]
        assert queued_tasks == []
        assert len(history_a) == 1
        assert history_a[0]["prompt"] == "neon city"
        assert history_b == []
        assert config_b["api_key_set"] is False


def test_deleting_history_removes_finished_task_from_task_center(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    with TestClient(app) as client:
        client.put("/api/config", json={"api_key": "sk-test-123456"})
        generated = client.post("/api/images/generate", json={"prompt": "delete me"})
        assert generated.status_code == 200
        task_id = generated.json()["id"]
        task = wait_for_task(client, task_id)
        history_id = task["items"][0]["id"]
        image_path = Path(task["items"][0]["image_path"])
        assert image_path.exists()

        deleted = client.delete(f"/api/history/{history_id}")

        assert deleted.status_code == 200
        assert deleted.json()["candidate_files"] == 1
        assert deleted.json()["protected_files"] == 0
        assert deleted.json()["deleted_files"] == 1
        assert not image_path.exists()
        assert client.get("/api/history").json()["items"] == []
        assert client.get("/api/tasks").json()["items"] == []
        assert client.get(f"/api/tasks/{task_id}").status_code == 404


def test_deleting_history_keeps_file_referenced_by_admin_case(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.put("/api/config", json={"api_key": "sk-test-123456"})
        generated = client.post("/api/images/generate", json={"prompt": "shared public asset"})
        assert generated.status_code == 200
        task = wait_for_task(client, generated.json()["id"])
        history_item = task["items"][0]
        image_path = Path(history_item["image_path"])
        assert image_path.exists()

        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200
        admin_case = client.post(
            "/api/admin/cases",
            json={
                "title": "Shared Asset",
                "prompt": "keep this asset",
                "image_url": history_item["image_url"],
                "image_path": history_item["image_path"],
                "status": "visible",
            },
        )
        assert admin_case.status_code == 200

        deleted = client.delete(f"/api/history/{history_item['id']}")

        assert deleted.status_code == 200
        assert deleted.json()["candidate_files"] == 1
        assert deleted.json()["protected_files"] == 1
        assert deleted.json()["deleted_files"] == 0
        assert image_path.exists()


def test_admin_cleanup_expires_unpublished_history_but_keeps_public_cases(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.put("/api/config", json={"api_key": "sk-test-123456"})
        unpublished_task = client.post("/api/images/generate", json={"prompt": "temporary history"})
        public_task = client.post("/api/images/generate", json={"prompt": "public keeper"})
        assert unpublished_task.status_code == 200
        assert public_task.status_code == 200
        wait_for_task(client, unpublished_task.json()["id"])
        wait_for_task(client, public_task.json()["id"])

        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200
        history_items = client.get("/api/history").json()["items"]
        by_prompt = {item["prompt"]: item for item in history_items}
        unpublished = by_prompt["temporary history"]
        public = by_prompt["public keeper"]
        unpublished_path = Path(unpublished["image_path"])
        public_path = Path(public["image_path"])
        assert unpublished_path.exists()
        assert public_path.exists()

        old_timestamp = (datetime.now(timezone.utc) - timedelta(days=3)).replace(microsecond=0).isoformat()
        with client.app.state.db.connect() as conn:
            conn.execute(
                "UPDATE image_history SET created_at = ?, updated_at = ?",
                (old_timestamp, old_timestamp),
            )

        published = client.post(f"/api/history/{public['id']}/publish")
        assert published.status_code == 200

        cleanup = client.post("/api/admin/maintenance/cleanup-images")

        assert cleanup.status_code == 200
        data = cleanup.json()
        assert data["retention_days"] == 2
        assert data["deleted_history"] == 1
        assert data["protected_history"] == 1
        assert data["deleted_tasks"] == 1
        assert data["deleted_files"] == 1
        assert not unpublished_path.exists()
        assert public_path.exists()
        remaining_history = client.get("/api/history").json()["items"]
        assert [item["id"] for item in remaining_history] == [public["id"]]
        remaining_tasks = client.get("/api/tasks").json()["items"]
        assert all(unpublished["id"] not in [item["id"] for item in task["items"]] for task in remaining_tasks)
        public_cases = client.get("/api/cases?q=public%20keeper").json()["items"]
        assert len(public_cases) == 1
        assert public_cases[0]["history_id"] == public["id"]


def test_generation_passes_resolution_ratio_and_quality(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    with TestClient(app) as client:
        client.put("/api/config", json={"api_key": "sk-test-123456"})

        generated = client.post(
            "/api/images/generate",
            json={"prompt": "wide city", "size": "2K", "aspect_ratio": "16:9", "quality": "high"},
        )

        assert generated.status_code == 200
        task = wait_for_task(client, generated.json()["id"])
        item = task["items"][0]
        provider = client.app.state.provider
        assert task["size"] == "2560x1440"
        assert task["aspect_ratio"] == "16:9"
        assert item["aspect_ratio"] == "16:9"
        assert provider.generated_payloads[-1]["size"] == "2560x1440"
        assert "aspectRatio" not in provider.generated_payloads[-1]
        assert provider.generated_payloads[-1]["quality"] == "high"


def test_generation_retries_retryable_upstream_errors(tmp_path: Path) -> None:
    provider = FlakyProvider(generate_failures=2)
    with make_client(tmp_path, provider=provider) as client:
        client.put("/api/config", json={"api_key": "sk-test-123456"})

        generated = client.post("/api/images/generate", json={"prompt": "retryable cup"})

        assert generated.status_code == 200
        task = wait_for_task(client, generated.json()["id"], attempts=120)
        assert task["status"] == "succeeded"
        assert provider.generate_attempts == 3
        assert task["items"][0]["status"] == "succeeded"


def test_generation_records_nonzero_ledger_amount(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    with TestClient(app) as client:
        client.put("/api/config", json={"api_key": "sk-test-123456"})

        generated = client.post(
            "/api/images/generate",
            json={"prompt": "tall city", "size": "4K", "aspect_ratio": "9:16", "quality": "medium"},
        )

        assert generated.status_code == 200
        task = wait_for_task(client, generated.json()["id"])
        ledger = client.get("/api/ledger").json()["items"]
        assert task["size"] == "2160x3840"
        assert ledger[0]["history_id"] == task["items"][0]["id"]
        assert ledger[0]["amount"] == 0.268
        assert ledger[0]["metadata"]["size_tier"] == "4K"
        assert ledger[0]["metadata"]["usage"] == {"total_tokens": 1}


def test_managed_user_ledger_uses_sub2api_actual_cost(tmp_path: Path) -> None:
    auth = FakeAuthClient()
    auth.usage_logs[0]["actual_cost"] = 0.321
    with make_client(tmp_path, auth_client=auth) as client:
        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200

        generated = client.post(
            "/api/images/generate",
            json={"prompt": "managed billing", "size": "2K", "aspect_ratio": "1:1", "quality": "medium"},
        )

        assert generated.status_code == 200
        wait_for_task(client, generated.json()["id"])
        ledger = client.get("/api/ledger").json()["items"]
        assert ledger[0]["amount"] == 0.321
        assert ledger[0]["metadata"]["cost_source"] == "sub2api_actual_cost"
        assert ledger[0]["metadata"]["sub2api_usage_log"]["actual_cost"] == 0.321


def test_manual_override_ledger_keeps_estimated_cost(tmp_path: Path) -> None:
    auth = FakeAuthClient()
    with make_client(tmp_path, auth_client=auth) as client:
        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200
        overridden = client.put("/api/config", json={"api_key": "sk-shared-bonus-654321"})
        assert overridden.json()["api_key_source"] == "manual_override"

        generated = client.post(
            "/api/images/generate",
            json={"prompt": "shared key billing", "size": "2K", "aspect_ratio": "1:1", "quality": "medium"},
        )

        assert generated.status_code == 200
        wait_for_task(client, generated.json()["id"])
        ledger = client.get("/api/ledger").json()["items"]
        assert ledger[0]["amount"] == 0.201
        assert ledger[0]["metadata"]["cost_source"] == "local_image_price"


def test_image_size_presets_follow_provider_limits() -> None:
    assert _provider_image_size("1K", "1:1") == "1088x1088"
    assert _provider_image_size("1K", "16:9") == "2048x1152"
    assert _provider_image_size("1K", "9:16") == "1152x2048"
    assert _provider_image_size("1K", "3:2") == "1632x1088"
    assert _provider_image_size("2K", "1:1") == "1440x1440"
    assert _provider_image_size("2K", "16:9") == "2560x1440"
    assert _provider_image_size("2K", "3:2") == "2160x1440"
    assert _provider_image_size("4K", "16:9") == "3840x2160"
    with pytest.raises(HTTPException):
        _provider_image_size("576x1024", "9:16")
    with pytest.raises(HTTPException):
        _provider_image_size("1080x1920", "9:16")
    with pytest.raises(HTTPException):
        _provider_image_size("4K", "1:1")
    with pytest.raises(HTTPException):
        _provider_image_size("3840x3840", "1:1")
    with pytest.raises(HTTPException):
        _provider_image_size("4096x4096", "1:1")
    assert _image_size_tier("1088x1088") == "1K"
    assert _image_size_tier("2048x1152") == "1K"
    assert _image_size_tier("1440x1440") == "2K"
    assert _image_size_tier("2560x1440") == "2K"
    assert _image_size_tier("2160x3840") == "4K"


def test_edit_persists_upload_and_result(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.put("/api/config", json={"api_key": "sk-test-123456"})

        response = client.post(
            "/api/images/edit",
            data={"prompt": "make it cyberpunk"},
            files=[
                ("image", ("source.png", b"fake-image", "image/png")),
                ("image", ("style.png", b"fake-style", "image/png")),
            ],
        )

        assert response.status_code == 200
        task = wait_for_task(client, response.json()["id"])
        item = task["items"][0]
        provider = client.app.state.provider
        assert item["mode"] == "edit"
        assert item["input_image_url"].startswith("/storage/uploads/")
        assert Path(item["input_image_path"]).exists()
        assert len(provider.edited_images[-1]) == 2
        assert provider.edited_images[-1][0][0] == "source.png"
        assert provider.edited_images[-1][1][0] == "style.png"


def test_account_includes_balance_and_stats(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.put("/api/config", json={"api_key": "sk-test-123456"})
        generated = client.post("/api/images/generate", json={"prompt": "one"})
        wait_for_task(client, generated.json()["id"])

        response = client.get("/api/account")

        assert response.status_code == 200
        data = response.json()
        assert data["balance"]["remaining"] == 12.5
        assert data["stats"]["total"] == 1
        assert data["viewer"]["authenticated"] is False


def test_user_can_publish_and_unpublish_history_as_public_case(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.put("/api/config", json={"api_key": "sk-test-123456"})
        generated = client.post("/api/images/generate", json={"prompt": "public neon gallery"})
        task = wait_for_task(client, generated.json()["id"])
        history_id = task["items"][0]["id"]

        history_before = client.get("/api/history").json()["items"][0]
        assert history_before["published"] is False

        guest_publish = client.post(f"/api/history/{history_id}/publish")
        assert guest_publish.status_code == 401

        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200

        published = client.post(f"/api/history/{history_id}/publish")
        assert published.status_code == 200
        published_data = published.json()
        assert published_data["item"]["published"] is True
        assert published_data["case"]["source_type"] == "user_history"
        assert published_data["case"]["prompt"] == "public neon gallery"
        assert published_data["item"]["published_case_id"] == published_data["case"]["id"]

        public_cases = client.get("/api/cases?q=public%20neon").json()["items"]
        assert len(public_cases) == 1
        assert public_cases[0]["source_type"] == "user_history"

        unpublished = client.delete(f"/api/history/{history_id}/publish")
        assert unpublished.status_code == 200
        assert unpublished.json()["item"]["published"] is False
        public_cases_after = client.get("/api/cases?q=public%20neon").json()["items"]
        assert public_cases_after == []


def test_login_merges_guest_history_without_auto_selecting_key(tmp_path: Path) -> None:
    auth = FakeAuthClient()
    with make_client(tmp_path, auth_client=auth) as client:
        client.put("/api/config", json={"api_key": "sk-guest-123456"})
        generated = client.post("/api/images/generate", json={"prompt": "guest prompt"})
        task_id = generated.json()["id"]
        task = wait_for_task(client, task_id)
        assert task["status"] == "succeeded"

        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200
        assert login.json()["viewer"]["authenticated"] is True
        assert auth.created_keys == []

        config = client.get("/api/config").json()
        history = client.get("/api/history").json()["items"]
        account = client.get("/api/account").json()

        assert config["managed_by_auth"] is True
        assert config["api_key_set"] is False
        assert len(history) == 1
        assert history[0]["prompt"] == "guest prompt"
        assert account["viewer"]["user"]["email"] == "demo@example.com"
        assert account["user"]["api_key_source"] == "managed"
        assert account["viewer"]["user"]["role"] == "admin"


def test_user_can_select_group_and_reuse_existing_key(tmp_path: Path) -> None:
    auth = ExistingKeysAuthClient(
        [
            {
                "id": 1,
                "key": "sk-other-group-111111",
                "name": "other-group",
                "group": {"id": 10, "name": "text-only", "platform": "openai"},
                "status": "active",
            },
            {
                "id": 2,
                "key": "sk-image-group-222222",
                "name": "image-group",
                "group": {"id": 42, "name": "image-openai", "platform": "openai"},
                "status": "active",
            },
        ]
    )

    with make_client(tmp_path, auth_client=auth) as client:
        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200

        groups = client.get("/api/auth/key-groups")
        assert groups.status_code == 200
        assert groups.json()["items"] == [{"id": "42", "name": "image-openai", "platform": "openai"}]

        selected = client.post("/api/auth/key-groups/select", json={"group_id": "42"})
        assert selected.status_code == 200
        assert auth.created_keys == []
        assert selected.json()["group"]["name"] == "image-openai"
        config = client.get("/api/config").json()
        assert config["api_key_hint"] == "sk-ima...2222"


def test_user_group_selection_creates_key_for_selected_group(tmp_path: Path) -> None:
    auth = ExistingKeysAuthClient([])

    with make_client(tmp_path, auth_client=auth) as client:
        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200

        selected = client.post("/api/auth/key-groups/select", json={"group_id": "42"})
        assert selected.status_code == 200
        assert auth.created_keys and auth.created_keys[0]["name"] == "cybergen-image"
        assert auth.created_keys[0]["group"]["id"] == 42
        config = client.get("/api/config").json()
        assert config["api_key_hint"] == "sk-use...3456"


def test_signed_in_user_can_override_key_and_clear_back_to_managed(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200
        selected = client.post("/api/auth/key-groups/select", json={"group_id": "42"})
        assert selected.status_code == 200

        overridden = client.put("/api/config", json={"api_key": "sk-shared-bonus-654321"})
        assert overridden.status_code == 200
        overridden_data = overridden.json()
        assert overridden_data["api_key_hint"] == "sk-sha...4321"
        assert overridden_data["api_key_source"] == "manual_override"

        account = client.get("/api/account").json()
        assert account["user"]["api_key_source"] == "manual_override"

        restored = client.put("/api/config", json={"clear_api_key": True})
        assert restored.status_code == 200
        restored_data = restored.json()
        assert restored_data["api_key_hint"] == "sk-use...3456"
        assert restored_data["api_key_source"] == "managed"


def test_site_settings_default_to_chinese(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/api/site-settings")

        assert response.status_code == 200
        data = response.json()
        assert data["default_locale"] == "zh-CN"
        assert data["announcement"]["enabled"] is True
        assert "即刻" in data["announcement"]["title"]
        assert "https://ai.get-money.locker" in data["announcement"]["body"]
        assert "inspiration_sources" not in data


def test_site_settings_migrates_old_default_brand(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        db = client.app.state.db
        with db.connect() as conn:
            conn.execute(
                """
                UPDATE site_settings
                SET announcement_title = ?,
                    announcement_body = ?
                WHERE id = 1
                """,
                (
                    "欢迎来到 JokoAI 图像系统",
                    """欢迎使用 JokoAI 图像生态系统。

站主联系方式：
QQ：935764227
Telegram：https://t.me/jokoacoount

中转站 / 充值站点：
https://ai.get-money.locker

如需充值、额度支持或账号协助，请通过以上方式联系。""",
                ),
            )

        response = client.get("/api/site-settings")

        assert response.status_code == 200
        data = response.json()
        assert "即刻" in data["announcement"]["title"]
        assert "JokoAI" not in data["announcement"]["body"]
        assert "joko" not in data["announcement"]["body"].lower()


def test_site_settings_migrates_jike_default_contact(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        db = client.app.state.db
        with db.connect() as conn:
            conn.execute(
                """
                UPDATE site_settings
                SET announcement_body = ?
                WHERE id = 1
                """,
                (
                    """欢迎使用 即刻 图像生态系统。

站主联系方式：
QQ：935764227
Telegram：https://t.me/jokoacoount

中转站 / 充值站点：
https://ai.get-money.locker

如需充值、额度支持或账号协助，请通过以上方式联系。""",
                ),
            )

        response = client.get("/api/site-settings")

        assert response.status_code == 200
        data = response.json()
        assert "joko" not in data["announcement"]["body"].lower()


def test_admin_can_update_site_settings(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200

        response = client.put(
            "/api/site-settings",
            json={
                "default_locale": "en-US",
                "announcement_enabled": True,
                "announcement_title": "系统维护通知",
                "announcement_body": "今晚 23:00 会进行维护。",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["default_locale"] == "en-US"
        assert data["announcement"]["enabled"] is True
        assert data["announcement"]["title"] == "系统维护通知"
        assert "inspiration_sources" not in data


def test_admin_can_update_global_upstream_settings(tmp_path: Path) -> None:
    auth = FakeAuthClient()
    app = make_app(tmp_path, auth_client=auth)
    provider = app.state.provider
    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200

        response = client.put(
            "/api/site-settings",
            json={
                "provider_base_url": "https://image-upstream.example.com/v1/",
                "auth_base_url": "https://auth-upstream.example.com/",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["upstream"]["provider_base_url"] == "https://image-upstream.example.com/v1"
        assert data["upstream"]["auth_base_url"] == "https://auth-upstream.example.com"
        assert data["upstream"]["effective_provider_base_url"] == "https://image-upstream.example.com/v1"
        assert data["upstream"]["effective_auth_base_url"] == "https://auth-upstream.example.com"

        public_settings = client.get("/api/auth/public-settings")
        assert public_settings.status_code == 200
        assert auth.public_settings_base_urls[-1] == "https://auth-upstream.example.com"

        generated = client.post(
            "/api/images/generate",
            json={"prompt": "custom upstream", "size": "2K", "aspect_ratio": "1:1", "quality": "medium"},
        )
        assert generated.status_code == 200
        wait_for_task(client, generated.json()["id"])

        assert provider.generated_configs[-1]["base_url"] == "https://image-upstream.example.com/v1"
        assert auth.list_usage_base_urls[-1] == "https://auth-upstream.example.com"


def test_invalid_global_upstream_url_is_rejected(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200

        response = client.put("/api/site-settings", json={"provider_base_url": "not-a-url"})

        assert response.status_code == 400


def test_parse_inspiration_markdown() -> None:
    markdown = """
## Portrait & Photography Cases

### Case 1: [Convenience Store Neon Portrait](https://x.com/demo/status/1) (by [@demo](https://x.com/demo))

| Output |
| :----: |
| <img src="./images/portrait_case1/output.jpg" width="300" alt="Output image"> |

**Prompt:**

```
35mm film photography, neon signs, authentic grain
```
"""
    items = parse_inspiration_markdown(
        markdown,
        "https://raw.githubusercontent.com/EvoLinkAI/awesome-gpt-image-2-prompts/main/README.md",
    )

    assert len(items) == 1
    assert items[0]["section"] == "Portrait & Photography Cases"
    assert items[0]["title"] == "Convenience Store Neon Portrait"
    assert items[0]["author"] == "@demo"
    assert items[0]["source_link"] == "https://x.com/demo/status/1"
    assert items[0]["image_url"].endswith("/images/portrait_case1/output.jpg")
    assert "35mm film" in items[0]["prompt"]


def test_parse_youmind_inspiration_markdown() -> None:
    markdown = """
## 🔥 Featured Prompts

### No. 1: VR Headset Exploded View Poster

#### 📖 Description

Generates a high-tech exploded view diagram.

#### 📝 Prompt

```
{
  "type": "exploded view product diagram poster",
  "subject": "VR headset"
}
```

#### 🖼️ Generated Images

##### Image 1

<div align="center">
<img src="https://cms-assets.youmind.com/media/demo.jpg" width="700" alt="VR Headset Exploded View Poster - Image 1">
</div>

#### 📌 Details

- **Author:** [wory](https://x.com/wory37303852)
- **Source:** [Twitter Post](https://x.com/wory37303852/status/2045925660401795478)
"""
    items = parse_inspiration_markdown(
        markdown,
        "https://raw.githubusercontent.com/YouMind-OpenLab/awesome-gpt-image-2/main/README.md",
    )

    assert len(items) == 1
    assert items[0]["section"] == "🔥 Featured Prompts"
    assert items[0]["title"] == "VR Headset Exploded View Poster"
    assert items[0]["author"] == "wory"
    assert items[0]["source_link"] == "https://x.com/wory37303852/status/2045925660401795478"
    assert items[0]["image_url"] == "https://cms-assets.youmind.com/media/demo.jpg"
    assert "exploded view product" in items[0]["prompt"]


def test_normalize_github_inspiration_source_url() -> None:
    assert (
        normalize_inspiration_source_url("https://github.com/YouMind-OpenLab/awesome-gpt-image-2")
        == "https://raw.githubusercontent.com/YouMind-OpenLab/awesome-gpt-image-2/main/README.md"
    )
    assert (
        normalize_inspiration_source_url(
            "https://github.com/YouMind-OpenLab/awesome-gpt-image-2/blob/main/README_zh.md"
        )
        == "https://raw.githubusercontent.com/YouMind-OpenLab/awesome-gpt-image-2/main/README_zh.md"
    )


def test_cache_inspiration_images_to_local_storage(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    settings = app.state.settings
    items = [{"image_url": "https://cdn.example.com/case.png", "raw": {}}]

    async def run_cache() -> dict[str, Any]:
        def handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url) == "https://cdn.example.com/case.png"
            return httpx.Response(200, headers={"content-type": "image/png"}, content=b"png-data")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await cache_inspiration_images(settings, client, items)

    result = asyncio.run(run_cache())

    assert result["cached"] == 1
    assert items[0]["image_url"].startswith("/storage/inspirations/")
    assert items[0]["raw"]["original_image_url"] == "https://cdn.example.com/case.png"
    cached_path = settings.storage_dir / items[0]["image_url"].removeprefix("/storage/")
    assert cached_path.read_bytes() == b"png-data"


def test_admin_can_manage_cases_likes_and_comments(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        assert client.get("/api/inspirations").status_code == 404
        assert client.post("/api/inspirations/sync").status_code == 404

        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200

        created = client.post(
            "/api/admin/cases",
            json={
                "title": "Manual Mockup",
                "author": "@admin",
                "prompt": "make a UI case",
                "image_url": "https://example.com/image.jpg",
                "status": "visible",
            },
        )
        assert created.status_code == 200
        case = created.json()
        assert case["source_type"] == "admin_manual"
        assert case["created_by_admin"] is True

        public_cases = client.get("/api/cases?q=manual").json()["items"]
        assert len(public_cases) == 1
        assert public_cases[0]["id"] == case["id"]

        liked = client.post(f"/api/cases/{case['id']}/like")
        assert liked.status_code == 200
        assert liked.json()["liked"] is True
        assert liked.json()["like_count"] == 1
        liked_again = client.post(f"/api/cases/{case['id']}/like")
        assert liked_again.json()["like_count"] == 1

        comment = client.post(f"/api/cases/{case['id']}/comments", json={"body": "great public case"})
        assert comment.status_code == 200
        comment_id = comment.json()["id"]
        assert comment.json()["author"] == "de***er"
        assert comment.json()["can_delete"] is True
        detail = client.get(f"/api/cases/{case['id']}").json()
        assert detail["comment_count"] == 1

        admin_comment = client.post(
            "/api/admin/comments",
            json={"case_id": case["id"], "author": "moderator", "body": "admin note", "status": "hidden"},
        )
        assert admin_comment.status_code == 200
        assert admin_comment.json()["status"] == "hidden"
        assert admin_comment.json()["can_edit"] is True
        public_comments = client.get(f"/api/cases/{case['id']}/comments").json()["items"]
        assert [item["body"] for item in public_comments] == ["great public case"]
        assert public_comments[0]["author"] == "de***er"
        admin_comments = client.get("/api/admin/comments").json()["items"]
        assert {item["body"]: item["author"] for item in admin_comments}["great public case"] == "demo-user"

        updated_comment = client.put(f"/api/comments/{comment_id}", json={"body": "edited public case", "status": "hidden"})
        assert updated_comment.status_code == 200
        assert updated_comment.json()["body"] == "edited public case"
        assert client.get(f"/api/cases/{case['id']}/comments").json()["items"] == []

        updated_case = client.put(f"/api/admin/cases/{case['id']}", json={"title": "Hidden Mockup", "status": "hidden"})
        assert updated_case.status_code == 200
        assert updated_case.json()["status"] == "hidden"
        assert client.get("/api/cases?q=manual").json()["items"] == []

        admin_cases = client.get("/api/admin/cases?q=hidden").json()["items"]
        assert admin_cases[0]["id"] == case["id"]

        deleted = client.delete(f"/api/admin/cases/{case['id']}")
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "deleted"


def test_public_cases_support_sorting_and_pagination(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200

        created_cases = []
        for title in ("Old Case", "Liked Case", "Commented Case"):
            created = client.post(
                "/api/admin/cases",
                json={
                    "title": title,
                    "prompt": f"prompt for {title}",
                    "image_url": f"https://example.com/{title.lower().replace(' ', '-')}.jpg",
                    "status": "visible",
                },
            )
            assert created.status_code == 200
            created_cases.append(created.json())

        timestamps = {
            created_cases[0]["id"]: "2026-04-20T00:00:00+00:00",
            created_cases[1]["id"]: "2026-04-21T00:00:00+00:00",
            created_cases[2]["id"]: "2026-04-22T00:00:00+00:00",
        }
        with client.app.state.db.connect() as conn:
            for case_id, timestamp in timestamps.items():
                conn.execute(
                    "UPDATE public_cases SET created_at = ?, updated_at = ? WHERE id = ?",
                    (timestamp, timestamp, case_id),
                )

        liked = client.post(f"/api/cases/{created_cases[1]['id']}/like")
        assert liked.status_code == 200
        commented = client.post(
            "/api/admin/comments",
            json={"case_id": created_cases[0]["id"], "author": "mod", "body": "visible comment", "status": "visible"},
        )
        assert commented.status_code == 200

        latest = client.get("/api/cases?sort=latest&limit=2&offset=0")
        likes = client.get("/api/cases?sort=likes&limit=3")
        comments = client.get("/api/cases?sort=comments&limit=3")
        page_two = client.get("/api/cases?sort=latest&limit=2&offset=1")

        assert latest.status_code == 200
        assert latest.json()["total"] == 3
        assert [item["title"] for item in latest.json()["items"]] == ["Commented Case", "Liked Case"]
        assert likes.status_code == 200
        assert likes.json()["items"][0]["title"] == "Liked Case"
        assert comments.status_code == 200
        assert comments.json()["items"][0]["title"] == "Old Case"
        assert page_two.status_code == 200
        assert page_two.json()["offset"] == 1
        assert [item["title"] for item in page_two.json()["items"]] == ["Liked Case", "Old Case"]


def test_public_comment_authors_are_masked(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200

        created = client.post(
            "/api/admin/cases",
            json={
                "title": "Privacy Case",
                "prompt": "show a privacy case",
                "image_url": "https://example.com/privacy.jpg",
                "status": "visible",
            },
        )
        case_id = created.json()["id"]

        admin_comment = client.post(
            "/api/admin/comments",
            json={"case_id": case_id, "author": "privacy@example.com", "body": "email author", "status": "visible"},
        )
        assert admin_comment.status_code == 200
        assert admin_comment.json()["author"] == "privacy@example.com"

        public_comments = client.get(f"/api/cases/{case_id}/comments").json()["items"]
        assert public_comments[0]["author"] == "pr***cy@e***e.com"
