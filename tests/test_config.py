"""
配置模块测试：默认合并、点号获取、环境变量覆盖、叶子键收集
不写真实配置文件，通过 mock 或注入 _config 测试逻辑
"""
import os
from unittest.mock import patch

from app.core.config import _deep_merge_default, config


class TestDeepMergeDefault:
    """_deep_merge_default：以默认为基底，用户配置覆盖，缺项从默认补全"""

    def test_empty_user_returns_default_copy(self):
        default = {"a": 1, "b": 2}
        got = _deep_merge_default(default, {})
        assert got == default
        assert got is not default

    def test_user_overrides_value(self):
        default = {"a": 1, "b": 2}
        user = {"a": 10}
        got = _deep_merge_default(default, user)
        assert got["a"] == 10
        assert got["b"] == 2

    def test_user_adds_new_key(self):
        default = {"a": 1}
        user = {"b": 2}
        got = _deep_merge_default(default, user)
        assert got["a"] == 1
        assert got["b"] == 2

    def test_nested_merge(self):
        default = {"paths": {"download": "/dl", "target": "/nas"}}
        user = {"paths": {"download": "/custom"}}
        got = _deep_merge_default(default, user)
        assert got["paths"]["download"] == "/custom"
        assert got["paths"]["target"] == "/nas"

    def test_nested_user_adds_key(self):
        default = {"paths": {"download": "/dl"}}
        user = {"paths": {"target": "/nas"}}
        got = _deep_merge_default(default, user)
        assert got["paths"]["download"] == "/dl"
        assert got["paths"]["target"] == "/nas"

    def test_leaf_replaces_nested(self):
        default = {"a": {"b": 1}}
        user = {"a": 100}
        got = _deep_merge_default(default, user)
        assert got["a"] == 100


class TestConfigGet:
    """Config.get(key, default)：支持点号嵌套键"""

    def test_flat_key(self):
        cfg = config
        original = cfg._config
        try:
            cfg._config = {"host": "http://qb:8080"}
            assert cfg.get("host") == "http://qb:8080"
        finally:
            cfg._config = original

    def test_dotted_key(self):
        cfg = config
        original = cfg._config
        try:
            cfg._config = {"qbittorrent": {"host": "http://localhost:8080", "username": "admin"}}
            assert cfg.get("qbittorrent.host") == "http://localhost:8080"
            assert cfg.get("qbittorrent.username") == "admin"
        finally:
            cfg._config = original

    def test_missing_key_returns_default(self):
        cfg = config
        original = cfg._config
        try:
            cfg._config = {"a": 1}
            assert cfg.get("b") is None
            assert cfg.get("b", 99) == 99
            assert cfg.get("a.b.c", "x") == "x"
        finally:
            cfg._config = original

    def test_deep_nested(self):
        cfg = config
        original = cfg._config
        try:
            cfg._config = {"a": {"b": {"c": 42}}}
            assert cfg.get("a.b.c") == 42
        finally:
            cfg._config = original


class TestConfigAllKeysSet:
    """_all_keys_set：递归收集所有叶子键路径（点号分隔）"""

    def test_flat(self):
        cfg = config
        d = {"a": 1, "b": 2}
        assert cfg._all_keys_set(d) == {"a", "b"}

    def test_nested(self):
        cfg = config
        d = {"paths": {"download": "/dl", "target": "/nas"}}
        assert cfg._all_keys_set(d) == {"paths.download", "paths.target"}

    def test_empty(self):
        cfg = config
        assert cfg._all_keys_set({}) == set()


class TestConfigOverrideFromEnv:
    """_override_from_env：环境变量 ZONGZI_SECTION_KEY 覆盖配置"""

    def test_string_override(self):
        cfg = config
        data = {"security": {"username": "admin"}}
        with patch.dict(os.environ, {"ZONGZI_SECURITY_USERNAME": "root"}, clear=False):
            cfg._override_from_env(data, "ZONGZI", "")
        assert data["security"]["username"] == "root"

    def test_bool_override_true(self):
        cfg = config
        data = {"qbittorrent": {"file_handling": {"use_copy": False}}}
        with patch.dict(os.environ, {"ZONGZI_QBITTORRENT_FILE_HANDLING_USE_COPY": "true"}, clear=False):
            cfg._override_from_env(data, "ZONGZI", "")
        assert data["qbittorrent"]["file_handling"]["use_copy"] is True

    def test_bool_override_false(self):
        cfg = config
        data = {"flag": True}
        with patch.dict(os.environ, {"ZONGZI_FLAG": "false"}, clear=False):
            cfg._override_from_env(data, "ZONGZI", "")
        assert data["flag"] is False

    def test_int_override(self):
        cfg = config
        data = {"security": {"access_token_expire_minutes": 60}}
        with patch.dict(os.environ, {"ZONGZI_SECURITY_ACCESS_TOKEN_EXPIRE_MINUTES": "120"}, clear=False):
            cfg._override_from_env(data, "ZONGZI", "")
        assert data["security"]["access_token_expire_minutes"] == 120

    def test_unset_env_no_change(self):
        cfg = config
        data = {"security": {"username": "admin"}}
        env_key = "ZONGZI_SECURITY_USERNAME"
        with patch.dict(os.environ, {}, clear=False):
            if env_key in os.environ:
                del os.environ[env_key]
            cfg._override_from_env(data, "ZONGZI", "")
        assert data["security"]["username"] == "admin"
