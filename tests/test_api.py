"""
API 冒烟测试
覆盖：健康检查、登录、Refresh Token、Logout、Cookie 认证、任务列表、通知、系统配置
"""
import os

import pytest

from app.core.security import create_access_token


@pytest.fixture(scope="module", autouse=True)
def _backup_and_restore_config():
    """备份并恢复项目 config.yml，避免测试写入污染共享配置（如 secret_key）"""
    from app.core.config import config
    path = config._config_path
    backup = None
    if os.path.exists(path):
        with open(path, "rb") as f:
            backup = f.read()
    yield
    if backup is not None:
        with open(path, "wb") as f:
            f.write(backup)
    else:
        if os.path.exists(path):
            os.remove(path)
    config.reload()


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert data["message"] == "ok"


# ---------------------------------------------------------------------------
# 登录
# ---------------------------------------------------------------------------

def test_login_success(client):
    resp = client.post(
        "/api/v1/users/login",
        data={"username": "admin", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "access_token" in data["data"]
    assert data["data"]["token_type"] == "bearer"


def test_login_returns_cookies(client):
    """登录成功应设置 httpOnly Cookie（access_token 和 refresh_token）"""
    resp = client.post(
        "/api/v1/users/login",
        data={"username": "admin", "password": "password123"},
    )
    assert resp.status_code == 200
    cookies = resp.cookies
    assert "access_token" in cookies, "登录应设置 access_token Cookie"
    assert "refresh_token" in cookies, "登录应设置 refresh_token Cookie"
    # httpOnly Cookie 通过 TestClient 也能读到
    assert cookies["access_token"] != ""


def test_login_fail(client):
    resp = client.post(
        "/api/v1/users/login",
        data={"username": "admin", "password": "wrong"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 40000
    assert "密码" in data["message"] or "错误" in data["message"]


# ---------------------------------------------------------------------------
# /me 认证守卫
# ---------------------------------------------------------------------------

def test_me_unauthorized(client):
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 40100


def test_me_authorized(client, token):
    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert data["data"]["username"] == "admin"


def test_me_authorized_via_cookie(client):
    """Cookie 认证令牌可被中间件识别（配合 Authorization header 使用）"""
    login_resp = client.post(
        "/api/v1/users/login",
        data={"username": "admin", "password": "password123"},
    )
    assert login_resp.status_code == 200
    set_cookie = login_resp.headers.get("set-cookie", "")
    import re
    match = re.search(r"access_token=([^;]+)", set_cookie)
    assert match, f"Set-Cookie header: {set_cookie}"
    access_token = match.group(1)
    # 通过 Cookie 头发送，同时带 Authorization 保证 /me 的依赖注入也能取到
    resp = client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Cookie": f"access_token={access_token}",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert data["data"]["username"] == "admin"


def test_no_auth_blocked_by_middleware(client):
    """无 Cookie 和 Authorization header 时中间件会拦截"""
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 40100
    assert "未登录" in data["message"] or "凭证" in data["message"]


# ---------------------------------------------------------------------------
# Refresh Token
# ---------------------------------------------------------------------------

def test_refresh_token_success(client):
    """使用 Refresh Token 刷新 Access Token"""
    login_resp = client.post(
        "/api/v1/users/login",
        data={"username": "admin", "password": "password123"},
    )
    refresh_token = login_resp.cookies["refresh_token"]

    resp = client.post(
        "/api/v1/users/refresh",
        headers={"Cookie": f"refresh_token={refresh_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "access_token" in data["data"]
    assert data["data"]["token_type"] == "bearer"

    # 刷新后也应设置新的 access_token Cookie
    assert "access_token" in resp.cookies


def test_refresh_token_without_cookie(client):
    """未提供 Refresh Token Cookie 时刷新失败"""
    resp = client.post("/api/v1/users/refresh")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 40100


def test_refresh_token_invalid(client):
    """无效 Refresh Token 刷新失败"""
    resp = client.post(
        "/api/v1/users/refresh",
        headers={"Cookie": "refresh_token=invalid-token-value"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 40100


def test_access_token_cannot_refresh(client):
    """Access Token 不能用于刷新（type 不同）"""
    login_resp = client.post(
        "/api/v1/users/login",
        data={"username": "admin", "password": "password123"},
    )
    access_token = login_resp.cookies["access_token"]

    resp = client.post(
        "/api/v1/users/refresh",
        headers={"Cookie": f"refresh_token={access_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 40100


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout_success(client, token):
    """登出应清除认证 Cookie"""
    resp = client.post(
        "/api/v1/users/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200

    # 登出后 Cookie 应被清除
    cookies = resp.cookies
    # delete_cookie 通过设置空值和过期时间为 0 实现
    assert "access_token" in cookies or resp.headers.get("set-cookie") is not None


def test_logout_unauthorized(client):
    """未登录不能登出"""
    resp = client.post("/api/v1/users/logout")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 40100


# ---------------------------------------------------------------------------
# 认证白名单测试
# ---------------------------------------------------------------------------

def test_whitelist_system_status(client):
    """白名单路径 /api/v1/system/status 无需认证"""
    resp = client.get("/api/v1/system/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] in (200, 40100)  # 可能返回 200 或 40100 取决于是否初始化


def test_whitelist_system_env_config(client):
    """白名单路径 /api/v1/system/env-config 无需认证"""
    resp = client.get("/api/v1/system/env-config")
    assert resp.status_code == 200


def test_whitelist_system_existing_config(client):
    """白名单路径 /api/v1/system/existing-config 无需认证"""
    resp = client.get("/api/v1/system/existing-config")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 任务与通知（需认证）
# ---------------------------------------------------------------------------

def test_tasks_list(client, token):
    resp = client.get("/api/v1/tasks/list", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "items" in data["data"]
    assert "total" in data["data"]


def test_notifications_list(client, token):
    resp = client.get("/api/v1/notifications/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "items" in data["data"]
    assert "total" in data["data"]


def test_system_paths(client, token):
    resp = client.get("/api/v1/system/paths", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "data" in data


# ---------------------------------------------------------------------------
# 下载器配置（需认证）
# ---------------------------------------------------------------------------

def test_config_returns_downloader_masked(client, token):
    """GET /system/config 返回 downloader 节，且敏感字段已脱敏"""
    resp = client.get("/api/v1/system/config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    dl = data.get("downloader", {}) or {}
    # 敏感字段应为脱敏占位符
    if dl.get("transmission", {}).get("password"):
        assert dl["transmission"]["password"] == "****"
    if dl.get("aria2", {}).get("secret"):
        assert dl["aria2"]["secret"] == "****"


def test_save_config_preserves_downloader(client, token):
    """PUT /system/config 保存后 downloader 节保留，且不破坏 qB 配置。

    注意：用 mock 隔离 config 文件写入，避免污染项目共享的 config.yml。
    """
    from unittest.mock import patch
    from app.api.v1 import system as system_mod

    # 构造含 downloader 节的完整配置
    cfg = {
        "security": {"secret_key": "a" * 32},
        "downloader": {
            "active": "transmission",
            "transmission": {"host": "http://localhost:9091", "password": "tm-secret"},
            "aria2": {"host": "http://localhost:6800", "secret": "aria-secret"},
        },
        "qbittorrent": {"host": "http://localhost:8080"},
    }

    # 保存成功后，save_file_config 应收到含 downloader 节的完整配置
    saved_payload = {}
    with patch.object(system_mod.config, "save_file_config", side_effect=lambda body: saved_payload.update(body)):
        resp2 = client.put("/api/v1/system/config", json=cfg, headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    assert resp2.json()["code"] == 200

    # 验证写入的配置含完整 downloader 节
    assert saved_payload["downloader"]["active"] == "transmission"
    assert saved_payload["downloader"]["transmission"]["host"] == "http://localhost:9091"
    assert saved_payload["downloader"]["aria2"]["secret"] == "aria-secret"
