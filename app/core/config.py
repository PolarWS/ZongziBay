import copy
import logging
import os

import yaml
from typing import Any, Dict

from app.core.password_hash import hash_password, is_password_hash

logger = logging.getLogger(__name__)


# SQLite 文件名固定，与 config.yml 同目录；不写进 YAML
DATABASE_SQLITE_FILENAME = "ZongziBay.db"


def _deep_merge_default(default: Dict, user: Dict) -> Dict:
    """
    以默认配置为基底，用用户配置覆盖；用户没有的键从默认补全。
    用于启动时检测完整性（每次更新可能新增或删除配置项）。
    """
    result = copy.deepcopy(default)
    for key, user_value in user.items():
        if key not in result:
            result[key] = copy.deepcopy(user_value)
        elif isinstance(result[key], dict) and isinstance(user_value, dict):
            result[key] = _deep_merge_default(result[key], user_value)
        else:
            result[key] = copy.deepcopy(user_value)
    return result


class Config:
    """
    配置管理类（单例模式）
    从项目根目录 config.yml 加载并提供全局配置。
    启动时与默认配置合并，缺项补全；支持在设置页通过 API 读写配置文件。
    """
    _instance = None
    _config: Dict[str, Any] = {}
    _file_config: Dict[str, Any] = {}
    _config_path: str = ""

    def __new__(cls):
        """实现单例，确保全局只有一个配置实例"""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _deep_update(self, base_dict: Dict, update_dict: Dict) -> Dict:
        """递归合并两个字典，用于配置覆盖"""
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
        return base_dict

    def _upgrade_security_password_if_needed(self, cfg: Dict[str, Any]) -> bool:
        """
        若 security.password 为明文，则自动升级为 PBKDF2 哈希。
        返回是否发生了升级。
        """
        if not isinstance(cfg, dict):
            return False
        security = cfg.get("security")
        if not isinstance(security, dict):
            return False
        password = security.get("password")
        if not isinstance(password, str) or not password.strip():
            return False
        if is_password_hash(password):
            return False

        security["password"] = hash_password(password)
        logger.info("检测到明文 security.password，已自动升级为 PBKDF2 哈希")
        return True

    def _load_default_config(self) -> Dict[str, Any]:
        """
        加载内置默认模板 app/resources/config_default.yml（用于完整性检测与补全），避免用户修改污染默认值。
        """
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_path = os.path.join(app_dir, "resources", "config_default.yml")
        if not os.path.exists(default_path):
            logger.warning(f"默认配置文件未找到: {default_path}")
            return {}
        try:
            with open(default_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"加载默认配置失败: {e}")
            return {}

    def _override_from_env(self, config: Dict, prefix: str = "ZONGZI", parent_key: str = ""):
        """
        递归检查环境变量并覆盖配置
        命名规则: ZONGZI_SECTION_KEY，如 security.password -> ZONGZI_SECURITY_PASSWORD
        """
        for key, value in config.items():
            current_key = f"{parent_key}_{key}" if parent_key else key
            current_key_upper = current_key.upper()

            if isinstance(value, dict):
                self._override_from_env(value, prefix, current_key_upper)
            else:
                env_var_name = f"{prefix}_{current_key_upper}"
                env_value = os.getenv(env_var_name)

                if env_value is not None:
                    if isinstance(value, bool):
                        if env_value.lower() in ('true', '1', 'yes', 'on'):
                            config[key] = True
                        elif env_value.lower() in ('false', '0', 'no', 'off'):
                            config[key] = False
                    elif isinstance(value, int):
                        try:
                            config[key] = int(env_value)
                        except ValueError:
                            config[key] = env_value
                    else:
                        config[key] = env_value
                    logger.info(f"配置项 {key} 已被环境变量 {env_var_name} 覆盖")

    def _all_keys_set(self, d: Dict, prefix: str = "") -> set:
        """递归收集所有叶子键路径（点号分隔），用于检测缺项"""
        out = set()
        for k, v in d.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(self._all_keys_set(v, path))
            else:
                out.add(path)
        return out

    def _load_config(self):
        """
        加载配置文件
        1. 加载默认 app/resources/config_default.yml，与用户 config 做完整性合并（缺项补全）
        2. 若有缺项或文件不存在，写回合并后的 config，保证结构完整
        3. 若存在 APP_ENV，则优先使用 config/config-{env}.yml 或 config-{env}.yml 作为主配置文件
        4. 从环境变量覆盖（支持 Docker 注入）
        """
        current_file = os.path.abspath(__file__)
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))

        default_config = self._load_default_config()

        # 基础配置文件（无环境变量时）
        docker_config_path = os.path.join(root_dir, "config", "config.yml")
        root_config_path = os.path.join(root_dir, "config.yml")
        target_config_path = root_config_path
        if os.path.exists(docker_config_path):
            target_config_path = docker_config_path

        # 根据 APP_ENV 选择环境专用配置文件作为最终读写对象
        env = os.getenv("APP_ENV")
        if env:
            env_filename = f"config-{env}.yml"
            docker_env_path = os.path.join(root_dir, "config", env_filename)
            root_env_path = os.path.join(root_dir, env_filename)
            if os.path.exists(docker_env_path):
                target_config_path = docker_env_path
            elif os.path.exists(root_env_path):
                target_config_path = root_env_path

        self._config_path = target_config_path
        user_config: Dict[str, Any] = {}
        if os.path.exists(target_config_path):
            try:
                with open(target_config_path, "r", encoding="utf-8") as f:
                    user_config = yaml.safe_load(f) or {}
                    logger.info(f"已加载基础配置: {target_config_path}")
            except Exception as e:
                logger.error(f"加载基础配置失败: {e}")
        else:
            logger.warning(f"基础配置文件未找到: {target_config_path}，将使用默认配置并创建文件")

        # 以默认配置为基底合并用户配置，缺项补全（每次更新可能新增或删除项）
        base_config = _deep_merge_default(default_config, user_config)
        default_keys = self._all_keys_set(default_config)
        user_keys = self._all_keys_set(user_config)
        missing = default_keys - user_keys
        password_upgraded = self._upgrade_security_password_if_needed(base_config)
        if missing or not os.path.exists(target_config_path) or password_upgraded:
            try:
                os.makedirs(os.path.dirname(target_config_path) or ".", exist_ok=True)
                with open(target_config_path, "w", encoding="utf-8") as f:
                    yaml.dump(base_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                if missing:
                    logger.info(f"配置完整性已修复，补全缺失项: {missing}")
                elif password_upgraded:
                    logger.info("已将明文登录密码自动升级并写回配置文件")
                else:
                    logger.info(f"已创建配置文件: {target_config_path}")
            except Exception as e:
                logger.error(f"写入配置文件失败: {e}")

        base_config.pop("database", None)
        self._file_config = copy.deepcopy(base_config)
        self._override_from_env(base_config)
        self._config = base_config

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项，支持点号嵌套键，如 "security.username"
        """
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def get_database_file_path(self) -> str:
        """
        SQLite 绝对路径：与当前加载的 config.yml 同目录 + DATABASE_SQLITE_FILENAME。
        Docker 常见为 config/config.yml → config/ZongziBay.db。
        """
        name = DATABASE_SQLITE_FILENAME
        cfg_path = os.path.abspath(self._config_path)
        cfg_dir = os.path.dirname(cfg_path)
        if not cfg_dir:
            cfg_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if os.path.isabs(name):
            return name
        return os.path.join(cfg_dir, name)

    def get_file_config(self) -> Dict[str, Any]:
        """返回当前文件中的配置（未叠加环境变量），供设置页展示与编辑"""
        out = copy.deepcopy(self._file_config)
        out.pop("database", None)
        return out

    def save_file_config(self, new_config: Dict[str, Any]) -> None:
        """将配置写入文件并重新加载（设置页保存时调用）；new_config 为完整配置对象"""
        new_config = copy.deepcopy(new_config)
        new_config.pop("database", None)
        self._upgrade_security_password_if_needed(new_config)
        self._file_config = new_config
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                yaml.dump(self._file_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            runtime = copy.deepcopy(self._file_config)
            self._override_from_env(runtime)
            self._config = runtime
            logger.info(f"配置已保存: {self._config_path}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            raise

    def reload(self) -> None:
        """重新从磁盘加载配置并应用环境变量（保存后由 save_file_config 内部更新，也可单独调用）"""
        self._file_config = {}
        self._config = {}
        self._load_config()


config = Config()
