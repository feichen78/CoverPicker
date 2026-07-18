# src/config_manager.py
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class ConfigManager:
    CONFIG_DIR_NAME = ".coverpicker"
    CONFIG_FILE_NAME = "config.json"

    def __init__(self):
        self._config_path = self._get_config_path()
        self._config: Dict[str, Any] = {}
        self._load()

    def _get_config_path(self) -> Path:
        home = Path.home()
        config_dir = home / self.CONFIG_DIR_NAME
        config_dir.mkdir(exist_ok=True)
        return config_dir / self.CONFIG_FILE_NAME

    def _load(self):
        if self._config_path.exists():
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logger.info(f"配置文件已加载: {self._config_path}")
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}")
                self._config = {}
        else:
            logger.info(f"配置文件不存在，将使用默认配置: {self._config_path}")
            self._config = {}

    def _save(self):
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"配置文件已保存: {self._config_path}")
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value
        self._save()

    # ---- 备份目录 ----
    def get_backup_dir(self) -> Optional[str]:
        return self.get('backup_dir')

    def set_backup_dir(self, dir_path: str):
        self.set('backup_dir', dir_path)

    # ---- 主题 (dark/light/system) ----
    def get_theme(self) -> str:
        return self.get('theme', 'system')

    def set_theme(self, theme: str):
        if theme in ('dark', 'light', 'system'):
            self.set('theme', theme)

    # ---- 截图质量 (1~10) ----
    def get_quality(self) -> int:
        return self.get('quality', 5)

    def set_quality(self, quality: int):
        if 1 <= quality <= 10:
            self.set('quality', quality)

    # ---- 截图尺寸 ----
    def get_scale(self) -> str:
        return self.get('scale', 'original')

    def set_scale(self, scale: str):
        if scale in ('original', '640x360', '1280x720', '1920x1080'):
            self.set('scale', scale)

    # ---- 监控目录列表 ----
    def get_watch_dirs(self) -> List[str]:
        return self.get('watch_dirs', [])

    def set_watch_dirs(self, dirs: List[str]):
        self.set('watch_dirs', dirs)

    def add_watch_dir(self, dir_path: str):
        dirs = self.get_watch_dirs()
        if dir_path not in dirs:
            dirs.append(dir_path)
            self.set_watch_dirs(dirs)

    def remove_watch_dir(self, dir_path: str):
        dirs = self.get_watch_dirs()
        if dir_path in dirs:
            dirs.remove(dir_path)
            self.set_watch_dirs(dirs)