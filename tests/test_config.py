"""
测试配置管理器 - 使用全局隔离的 HOME 目录
"""

import pytest
import os
from pathlib import Path
from src.config_manager import ConfigManager


class TestConfigManager:

    def test_init_creates_config_file(self, isolate_home_for_all_tests):
        """测试 ConfigManager 在第一次写入时创建配置文件"""
        config_dir = Path(isolate_home_for_all_tests) / ".coverpicker"
        if config_dir.exists():
            import shutil
            shutil.rmtree(config_dir)
        
        config = ConfigManager()
        config.set("test", "value")
        
        config_path = config_dir / "config.json"
        assert config_path.exists(), f"配置文件未创建: {config_path}"

    def test_set_and_get(self, isolate_home_for_all_tests):
        """测试基本的键值存储"""
        config = ConfigManager()
        config.set("test_key", "test_value")
        assert config.get("test_key") == "test_value"
        
        config2 = ConfigManager()
        assert config2.get("test_key") == "test_value"

    def test_get_default(self, isolate_home_for_all_tests):
        """测试获取不存在的键时返回默认值"""
        config = ConfigManager()
        assert config.get("nonexistent", "default") == "default"

    def test_watch_dirs_persistence(self, isolate_home_for_all_tests):
        """测试监控目录的增删改"""
        config = ConfigManager()
        dirs = ["C:/test1", "D:/test2"]
        config.set_watch_dirs(dirs)
        assert config.get_watch_dirs() == dirs
        
        config2 = ConfigManager()
        assert config2.get_watch_dirs() == dirs

    def test_backup_dir_persistence(self, isolate_home_for_all_tests):
        """测试备份目录的存储"""
        config = ConfigManager()
        backup_dir = "E:/backup"
        config.set_backup_dir(backup_dir)
        assert config.get_backup_dir() == backup_dir
        
        config2 = ConfigManager()
        assert config2.get_backup_dir() == backup_dir

    def test_last_export_dir(self, isolate_home_for_all_tests):
        """测试上次导出目录的记忆"""
        config = ConfigManager()
        config.set("last_export_dir", "F:/exports")
        assert config.get("last_export_dir") == "F:/exports"
        
        if hasattr(config, "get_last_export_dir"):
            assert config.get_last_export_dir() == "F:/exports"