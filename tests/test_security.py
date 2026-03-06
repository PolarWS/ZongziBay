"""
安全与 JWT 单元测试：Token 生成与解析
"""
import pytest
from datetime import timedelta
from unittest.mock import patch

from app.core.security import create_access_token
from jose import jwt

SECRET = "test-secret-key"
ALGORITHM = "HS256"


@patch("app.core.security.SECRET_KEY", SECRET)
@patch("app.core.security.ALGORITHM", ALGORITHM)
def test_create_access_token_decodable():
    """生成 token 后可用相同密钥解析出 sub"""
    token = create_access_token(data={"sub": "admin"})
    assert isinstance(token, str)
    payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    assert payload["sub"] == "admin"
    assert "exp" in payload


@patch("app.core.security.SECRET_KEY", SECRET)
@patch("app.core.security.ALGORITHM", ALGORITHM)
def test_create_access_token_with_expires_delta():
    """指定 expires_delta 时过期时间正确"""
    token = create_access_token(data={"sub": "user"}, expires_delta=timedelta(minutes=5))
    payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    assert payload["sub"] == "user"
    # exp 应在约 5 分钟后（允许 1 分钟误差）
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).timestamp()
    assert payload["exp"] >= now
    assert payload["exp"] <= now + 360  # 6 分钟内
