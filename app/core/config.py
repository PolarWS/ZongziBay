import logging
import os

import yaml
from typing import Any, Dict

logger = logging.getLogger(__name__)


class Config:
    """
    配置管理类（单例模式）
    从项目根目录 config.yml 加载并提供全局配置。
    """
    _instance = None
    _config: Dict[str, Any] = {}

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

    def _load_config(self):
        """
        加载配置文件
        1. 加载 config.yml 作为基础配置
        2. 若存在 APP_ENV，加载 config-{env}.yml 覆盖
        3. 从环境变量覆盖（支持 Docker 注入）
        """
        current_file = os.path.abspath(__file__)
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))

        base_config = {}
        docker_config_path = os.path.join(root_dir, "config", "config.yml")
        root_config_path = os.path.join(root_dir, "config.yml")
        target_config_path = root_config_path
        if os.path.exists(docker_config_path):
            target_config_path = docker_config_path

        if os.path.exists(target_config_path):
            try:
                with open(target_config_path, "r", encoding="utf-8") as f:
                    base_config = yaml.safe_load(f) or {}
                    logger.info(f"已加载基础配置: {target_config_path}")
            except Exception as e:
                logger.error(f"加载基础配置失败: {e}")
        else:
            logger.warning(f"警告: 基础配置文件未找到: {target_config_path}")

        env = os.getenv("APP_ENV")
        if env:
            env_config_filename = f"config-{env}.yml"
            env_config_path = os.path.join(root_dir, env_config_filename)
            if os.path.exists(env_config_path):
                try:
                    with open(env_config_path, "r", encoding="utf-8") as f:
                        env_config = yaml.safe_load(f) or {}
                        logger.info(f"已加载环境配置: {env_config_path} (环境: {env})")
                        self._deep_update(base_config, env_config)
                except Exception as e:
                    logger.error(f"加载环境配置失败: {e}")
            else:
                logger.warning(f"警告: 环境配置文件未找到: {env_config_path}")

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


config = Config()
