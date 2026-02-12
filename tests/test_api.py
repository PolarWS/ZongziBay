"""
API 最小冒烟测试
覆盖：健康检查、登录、认证、任务列表、通知
"""


def test_health(client):
    """健康检查"""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert data["message"] == "ok"


def test_login_success(client):
    """登录成功"""
    resp = client.post(
        "/api/v1/users/login",
        data={"username": "admin", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "access_token" in data["data"]
    assert data["data"]["token_type"] == "bearer"


def test_login_fail(client):
    """登录失败：密码错误"""
    resp = client.post(
        "/api/v1/users/login",
        data={"username": "admin", "password": "wrong"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 40000
    assert "密码" in data["message"] or "错误" in data["message"]


def test_me_unauthorized(client):
    """未登录访问 /me"""
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 40100


def test_me_authorized(client, token):
    """登录后访问 /me"""
    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert data["data"]["username"] == "admin"


def test_tasks_list(client, token):
    """任务列表（需认证）"""
    resp = client.get("/api/v1/tasks/list", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "items" in data["data"]
    assert "total" in data["data"]


def test_notifications_list(client, token):
    """通知列表（需认证）"""
    resp = client.get("/api/v1/notifications/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "items" in data["data"]
    assert "total" in data["data"]


def test_system_paths(client, token):
    """系统路径配置（需认证）"""
    resp = client.get("/api/v1/system/paths", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "data" in data
