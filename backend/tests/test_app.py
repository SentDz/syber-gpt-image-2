from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.inspirations import cache_inspiration_images, normalize_inspiration_source_url, parse_inspiration_markdown
from app.main import create_app, _auth_client, _db, _provider, _provider_image_size, _settings
from app.settings import Settings


PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class FakeProvider:
    def __init__(self) -> None:
        self.generated_payloads: list[dict[str, Any]] = []
        self.edited_fields: list[dict[str, Any]] = []

    async def test_connection(self, config: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "models": ["gpt-image-2"], "raw": {"data": [{"id": "gpt-image-2"}]}}

    async def usage(self, config: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "remaining": 12.5, "raw": {"remaining": 12.5, "unit": "USD"}}

    async def generate_image(self, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0.02)
        assert payload["model"] == "gpt-image-2"
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
        self.edited_fields.append(fields)
        return {"created": 124, "data": [{"b64_json": PNG_B64}], "usage": {"total_tokens": 2}}


class FakeAuthClient:
    def __init__(self) -> None:
        self.created_keys: list[dict[str, Any]] = []

    async def public_settings(self, base_url: str) -> dict[str, Any]:
        return {"registration_enabled": True, "email_verify_enabled": False, "backend_mode_enabled": False, "site_name": "demo"}

    async def send_verify_code(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"message": "sent", "countdown": 60}

    async def register(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "access_token": "access-demo",
            "refresh_token": "refresh-demo",
            "token_type": "Bearer",
            "user": {"id": 7, "email": payload["email"], "username": "demo-user", "role": "admin"},
        }

    async def login(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "access_token": "access-demo",
            "refresh_token": "refresh-demo",
            "token_type": "Bearer",
            "user": {"id": 7, "email": payload["email"], "username": "demo-user", "role": "admin"},
        }

    async def login_2fa(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "access_token": "access-demo",
            "refresh_token": "refresh-demo",
            "token_type": "Bearer",
            "user": {"id": 7, "email": "demo@example.com", "username": "demo-user", "role": "admin"},
        }

    async def list_keys(self, base_url: str, access_token: str) -> list[dict[str, Any]]:
        return []

    async def list_available_groups(self, base_url: str, access_token: str) -> list[dict[str, Any]]:
        raise AssertionError("Direct Sub2API mode should not require a dedicated image group")

    async def create_key(self, base_url: str, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        key = {
            "id": 99,
            "key": "sk-user-managed-123456",
            "name": payload["name"],
            "group": {"id": payload.get("group_id"), "name": "general-openai", "platform": "openai"},
            "status": "active",
        }
        self.created_keys.append(key)
        return key


def make_app(tmp_path: Path, auth_client: FakeAuthClient | None = None):
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
        user_name="tester",
        cors_origins=["http://127.0.0.1:3000"],
        request_timeout_seconds=10,
        inspiration_source_url="https://example.com/README.md",
        inspiration_sync_interval_seconds=0,
        inspiration_sync_on_startup=False,
        session_cookie_name="cybergen_session",
        guest_cookie_name="cybergen_guest",
        session_ttl_seconds=3600,
        guest_ttl_seconds=86400,
        cookie_secure=False,
    )
    app = create_app(settings=settings, provider=FakeProvider(), auth_client=auth_client or FakeAuthClient())
    app.dependency_overrides[_db] = lambda: app.state.db
    app.dependency_overrides[_settings] = lambda: app.state.settings
    app.dependency_overrides[_provider] = lambda: app.state.provider
    app.dependency_overrides[_auth_client] = lambda: app.state.auth_client
    return app


def make_client(tmp_path: Path, auth_client: FakeAuthClient | None = None) -> TestClient:
    return TestClient(make_app(tmp_path, auth_client=auth_client))


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
        assert task["size"] == "2048x1152"
        assert task["aspect_ratio"] == "16:9"
        assert item["aspect_ratio"] == "16:9"
        assert provider.generated_payloads[-1]["size"] == "2048x1152"
        assert "aspectRatio" not in provider.generated_payloads[-1]
        assert provider.generated_payloads[-1]["quality"] == "high"


def test_image_size_presets_follow_provider_limits() -> None:
    assert _provider_image_size("1K", "16:9") == "1024x576"
    assert _provider_image_size("2K", "16:9") == "2048x1152"
    assert _provider_image_size("4K", "16:9") == "3840x2160"
    with pytest.raises(HTTPException):
        _provider_image_size("4K", "1:1")
    with pytest.raises(HTTPException):
        _provider_image_size("3840x3840", "1:1")
    with pytest.raises(HTTPException):
        _provider_image_size("4096x4096", "1:1")


def test_edit_persists_upload_and_result(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.put("/api/config", json={"api_key": "sk-test-123456"})

        response = client.post(
            "/api/images/edit",
            data={"prompt": "make it cyberpunk"},
            files={"image": ("source.png", b"fake-image", "image/png")},
        )

        assert response.status_code == 200
        task = wait_for_task(client, response.json()["id"])
        item = task["items"][0]
        assert item["mode"] == "edit"
        assert item["input_image_url"].startswith("/storage/uploads/")
        assert Path(item["input_image_path"]).exists()


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

        published = client.post(f"/api/history/{history_id}/publish")
        assert published.status_code == 200
        published_data = published.json()
        assert published_data["item"]["published"] is True
        assert published_data["inspiration"]["section"] == "用户作品"
        assert published_data["inspiration"]["prompt"] == "public neon gallery"

        public_cases = client.get("/api/inspirations?q=public%20neon").json()["items"]
        assert len(public_cases) == 1
        assert public_cases[0]["source_url"] == "joko-image://user-gallery"

        unpublished = client.delete(f"/api/history/{history_id}/publish")
        assert unpublished.status_code == 200
        assert unpublished.json()["item"]["published"] is False
        public_cases_after = client.get("/api/inspirations?q=public%20neon").json()["items"]
        assert public_cases_after == []


def test_login_binds_managed_key_and_merges_guest_history(tmp_path: Path) -> None:
    auth = FakeAuthClient()
    with make_client(tmp_path, auth_client=auth) as client:
        client.put("/api/config", json={"api_key": "sk-guest-123456"})
        generated = client.post("/api/images/generate", json={"prompt": "guest prompt"})
        task_id = generated.json()["id"]

        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200
        assert login.json()["viewer"]["authenticated"] is True
        assert auth.created_keys and auth.created_keys[0]["name"] == "cybergen-image"
        assert auth.created_keys[0]["group"]["id"] is None

        task = wait_for_task(client, task_id)
        assert task["status"] == "succeeded"

        config = client.get("/api/config").json()
        history = client.get("/api/history").json()["items"]
        account = client.get("/api/account").json()

        assert config["managed_by_auth"] is True
        assert config["api_key_hint"] == "sk-use...3456"
        assert len(history) == 1
        assert history[0]["prompt"] == "guest prompt"
        assert account["viewer"]["user"]["email"] == "demo@example.com"
        assert account["user"]["api_key_source"] == "managed"
        assert account["viewer"]["user"]["role"] == "admin"


def test_signed_in_user_can_override_key_and_clear_back_to_managed(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        login = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "secret123"})
        assert login.status_code == 200

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
        assert "JokoAI" in data["announcement"]["title"]
        assert "https://ai.get-money.locker" in data["announcement"]["body"]
        assert data["inspiration_sources"] == ["https://example.com/README.md"]


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
                "inspiration_sources": [
                    "https://github.com/YouMind-OpenLab/awesome-gpt-image-2",
                    "https://raw.githubusercontent.com/EvoLinkAI/awesome-gpt-image-2-prompts/main/README.md",
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["default_locale"] == "en-US"
        assert data["announcement"]["enabled"] is True
        assert data["announcement"]["title"] == "系统维护通知"
        assert data["inspiration_sources"][0] == "https://raw.githubusercontent.com/YouMind-OpenLab/awesome-gpt-image-2/main/README.md"


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


def test_manual_inspiration_sync_endpoint(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        db = client.app.state.db
        db.upsert_inspirations(
            "https://example.com/README.md",
            [
                {
                    "id": "abc",
                    "source_item_id": "abc",
                    "section": "UI",
                    "title": "Mockup",
                    "author": "@demo",
                    "prompt": "make a UI",
                    "image_url": "https://example.com/image.jpg",
                    "source_link": "https://example.com/post",
                    "raw": {},
                }
            ],
        )

        response = client.get("/api/inspirations")

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["title"] == "Mockup"
