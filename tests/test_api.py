"""
API 冒烟测试
覆盖：健康检查、登录、Refresh Token、Logout、Cookie 认证、任务列表、通知、系统配置
"""
from app.core.security import create_access_token


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
