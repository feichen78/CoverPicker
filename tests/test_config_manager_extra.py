"""
补充测试 config_manager 未覆盖分支
"""

import os
import tempfile
import pytest
from pathlib import Path

from src.config_manager import ConfigManager


class TestConfigManagerExtra:

    @pytest.fixture
    def isolated_config(self, isolate_home_for_all_tests):
        """使用隔离的 HOME 目录"""
        return ConfigManager()

    def test_set_backup_dir_valid(self, isolated_config):
        """测试设置有效的备份目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            isolated_config.set_backup_dir(tmpdir)
            assert isolated_config.get_backup_dir() == tmpdir

    def test_set_backup_dir_invalid_path(self, isolated_config):
        """测试设置无效路径（不检查存在性，直接存储）"""
        invalid_path = "/nonexistent/path"
        isolated_config.set_backup_dir(invalid_path)
        assert isolated_config.get_backup_dir() == invalid_path

    def test_set_last_export_dir_valid(self, isolated_config):
        """测试设置有效的导出目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            isolated_config.set_last_export_dir(tmpdir)
            assert isolated_config.get_last_export_dir() == tmpdir

    def test_set_last_export_dir_nonexistent(self, isolated_config):
        """测试设置不存在的目录（应被拒绝）"""
        nonexistent = "/nonexistent/dir"
        isolated_config.set_last_export_dir(nonexistent)
        # 应保持不变（或 None）
        assert isolated_config.get_last_export_dir() is None

    def test_set_last_gif_export_dir_valid(self, isolated_config):
        """测试设置有效的 GIF 导出目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            isolated_config.set_last_gif_export_dir(tmpdir)
            assert isolated_config.get_last_gif_export_dir() == tmpdir

    def test_set_last_gif_export_dir_nonexistent(self, isolated_config):
        """测试设置不存在的 GIF 导出目录（应被拒绝）"""
        nonexistent = "/nonexistent/gif_dir"
        isolated_config.set_last_gif_export_dir(nonexistent)
        assert isolated_config.get_last_gif_export_dir() is None

    def test_set_theme_valid(self, isolated_config):
        """测试设置主题"""
        isolated_config.set_theme("dark")
        assert isolated_config.get_theme() == "dark"
        isolated_config.set_theme("light")
        assert isolated_config.get_theme() == "light"
        isolated_config.set_theme("system")
        assert isolated_config.get_theme() == "system"

    def test_set_theme_invalid(self, isolated_config):
        """测试设置无效主题（应被忽略）"""
        isolated_config.set_theme("invalid")
        # 应保持默认 'system'
        assert isolated_config.get_theme() == "system"

    def test_set_quality_valid(self, isolated_config):
        """测试设置截图质量"""
        isolated_config.set_quality(8)
        assert isolated_config.get_quality() == 8

    def test_set_quality_out_of_range(self, isolated_config):
        """测试设置超出范围的质量（应被忽略）"""
        isolated_config.set_quality(0)
        assert isolated_config.get_quality() == 5  # 默认值
        isolated_config.set_quality(11)
        assert isolated_config.get_quality() == 5

    def test_set_scale_valid(self, isolated_config):
        """测试设置截图尺寸"""
        isolated_config.set_scale("1280x720")
        assert isolated_config.get_scale() == "1280x720"
        isolated_config.set_scale("original")
        assert isolated_config.get_scale() == "original"

    def test_set_scale_invalid(self, isolated_config):
        """测试设置无效尺寸（应被忽略）"""
        isolated_config.set_scale("invalid")
        assert isolated_config.get_scale() == "original"  # 默认值