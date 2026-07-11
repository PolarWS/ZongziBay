"""
pytest 公共配置
测试环境使用临时数据库文件，避免污染本地数据
"""
import os
import tempfile

# 必须在导入 app 之前设置，否则 config 会加载默认数据库路径
# 使用临时文件而非 :memory:，避免 Windows 下多线程/多连接问题
_test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db.close()
os.environ["ZONGZI_DATABASE_PATH"] = os.path.abspath(_test_db.name)

# CI 环境没有 config.yml，通过环境变量注入测试用的用户名和密码
# 密码直接用 bcrypt 哈希值，避免被 _hash_env_password_if_needed 做 SHA-256 二次哈希
# （生产环境前端会做 SHA-256 预处理，但测试直接用明文密码）
os.environ["ZONGZI_SECURITY_USERNAME"] = "admin"
import bcrypt as _conftest_bcrypt
os.environ["ZONGZI_SECURITY_PASSWORD"] = _conftest_bcrypt.hashpw(
    "password123".encode("utf-8"), _conftest_bcrypt.gensalt(rounds=12)
).decode("utf-8")

import pytest
from fastapi.testclient import TestClient

from app.core import db
from app.main import app


@pytest.fixture(scope="session")
def _cleanup_test_db():
    """会话结束删除临时数据库"""
    yield
    try:
        os.unlink(_test_db.name)
    except OSError:
        pass


@pytest.fixture
def client(_cleanup_test_db):
    """FastAPI 测试客户端。显式初始化临时库表结构，避免依赖 lifespan 执行顺序。"""
    db.init_db()
    return TestClient(app)


@pytest.fixture
def token(client):
    """登录获取 token，供需要认证的接口使用"""
    resp = client.post(
        "/api/v1/users/login",
        data={"username": "admin", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    return data["data"]["access_token"]
