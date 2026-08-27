"""
测试崩溃报告生成模块
"""

import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.crash_handler import CrashHandler, get_app_dir


class TestCrashHandler:

    @pytest.fixture
    def temp_report_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, temp_report_dir):
        return CrashHandler(app_name="TestApp", report_dir=str(temp_report_dir))

    def test_init_creates_report_dir(self, temp_report_dir):
        """测试初始化时创建报告目录（目录已由 fixture 创建）"""
        # 临时目录已存在，CrashHandler 应能正常使用
        handler = CrashHandler(report_dir=str(temp_report_dir))
        assert temp_report_dir.exists()
        assert handler.report_dir == temp_report_dir

    def test_init_default_dir(self):
        """测试默认报告目录为项目 log/crashes 目录"""
        with patch('src.crash_handler.get_app_dir', return_value=Path("C:/test")):
            handler = CrashHandler()
            assert handler.report_dir == Path("C:/test/log/crashes")

    def test_install_replaces_excepthook(self, handler):
        original_hook = sys.excepthook
        handler.install()
        assert sys.excepthook == handler._excepthook
        sys.excepthook = original_hook

    def test_uninstall_restores_excepthook(self, handler):
        original_hook = sys.excepthook
        handler.install()
        handler.uninstall()
        assert sys.excepthook == original_hook

    def test_generate_report_creates_file(self, handler):
        try:
            raise ValueError("测试异常")
        except ValueError as e:
            exc_type, exc_value, exc_tb = type(e), e, e.__traceback__

        report_path = handler._generate_report(exc_type, exc_value, exc_tb)
        assert os.path.exists(report_path)
        assert report_path.endswith(".txt")

        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "崩溃报告 - TestApp" in content
            assert "ValueError" in content
            assert "测试异常" in content
            assert "堆栈跟踪" in content
            assert "请将此报告提交给开发者" in content

    def test_excepthook_generates_report(self, handler):
        original_hook = sys.excepthook
        try:
            raise ValueError("测试异常")
        except ValueError as e:
            exc_type, exc_value, exc_tb = type(e), e, e.__traceback__

        with patch.object(handler, '_generate_report', return_value="/fake/path.txt") as mock_generate:
            with patch.object(handler, '_orig_excepthook'):
                handler._excepthook(exc_type, exc_value, exc_tb)
                mock_generate.assert_called_once_with(exc_type, exc_value, exc_tb)

        sys.excepthook = original_hook

    def test_get_crash_reports_empty(self, handler):
        reports = handler.get_crash_reports()
        assert reports == []

    def test_get_crash_reports_returns_reports(self, handler, temp_report_dir):
        for i in range(3):
            path = temp_report_dir / f"crash_report_2025010{i}.txt"
            path.write_text("dummy content")

        reports = handler.get_crash_reports(limit=2)
        assert len(reports) == 2
        assert reports[0]['name'].startswith("crash_report_")
        assert 'size' in reports[0]
        assert 'mtime' in reports[0]

    def test_get_crash_reports_sorted_by_mtime(self, handler, temp_report_dir):
        import time
        for i in range(3):
            path = temp_report_dir / f"crash_report_2025010{i}.txt"
            path.write_text("dummy")
            time.sleep(0.01)

        reports = handler.get_crash_reports(limit=3)
        # 按 mtime 降序，最新的在前
        assert reports[0]['mtime'] >= reports[1]['mtime'] if len(reports) >= 2 else True

    def test_check_crashes_on_startup_no_report(self, handler):
        result = handler.check_crashes_on_startup()
        assert result is None

    def test_check_crashes_on_startup_with_report(self, handler, temp_report_dir):
        path = temp_report_dir / "crash_report_20250101.txt"
        path.write_text("dummy")

        result = handler.check_crashes_on_startup()
        assert result == str(path)

    def test_get_app_dir_returns_parent_of_src(self):
        app_dir = get_app_dir()
        assert app_dir is not None
        assert app_dir.is_absolute()