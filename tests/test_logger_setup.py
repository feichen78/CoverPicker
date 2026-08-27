"""
测试日志配置模块
"""

import os
import shutil
import pytest
import logging
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.logger_setup import setup_logger, _clean_old_logs


class TestLoggerSetup:

    @pytest.fixture(autouse=True)
    def cleanup_loggers(self):
        """在每个测试后强制关闭所有 logger handlers"""
        yield
        # 关闭所有已存在的 logger 的 handlers
        for logger_name in logging.root.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
        # 关闭 root logger handlers
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)

    @pytest.fixture
    def temp_log_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        # 强制删除临时目录（忽略权限错误）
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    def test_setup_logger_creates_log_dir(self, temp_log_dir):
        """测试 setup_logger 创建日志目录"""
        assert temp_log_dir.exists()
        logger = setup_logger(name="Test", log_dir=str(temp_log_dir))
        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_setup_logger_returns_logger(self, temp_log_dir):
        logger = setup_logger(name="Test", log_dir=str(temp_log_dir))
        assert isinstance(logger, logging.Logger)
        assert logger.name == "Test"
        assert logger.level == logging.DEBUG

    def test_setup_logger_adds_file_handler(self, temp_log_dir):
        logger = setup_logger(name="Test", log_dir=str(temp_log_dir))
        handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(handlers) >= 1

        # 写入一条日志，确保文件被创建
        logger.info("test message")
        today = datetime.now().strftime("%Y-%m-%d")
        expected_file = temp_log_dir / f"CoverPicker_{today}.log"
        import time
        time.sleep(0.1)
        assert expected_file.exists()

    def test_setup_logger_adds_console_handler(self, temp_log_dir):
        logger = setup_logger(name="Test", log_dir=str(temp_log_dir))
        handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(handlers) >= 1

    def test_setup_logger_prevents_duplicate_handlers(self, temp_log_dir):
        logger1 = setup_logger(name="TestDup", log_dir=str(temp_log_dir))
        handler_count = len(logger1.handlers)

        logger2 = setup_logger(name="TestDup", log_dir=str(temp_log_dir))
        assert len(logger2.handlers) == handler_count

    def test_clean_old_logs_removes_old_files(self, temp_log_dir):
        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        old_file = temp_log_dir / f"CoverPicker_{old_date}.log"
        old_file.write_text("old log")

        recent_date = datetime.now().strftime("%Y-%m-%d")
        recent_file = temp_log_dir / f"CoverPicker_{recent_date}.log"
        recent_file.write_text("recent log")

        _clean_old_logs(temp_log_dir, days=7)

        assert not old_file.exists()
        assert recent_file.exists()

    def test_clean_old_logs_ignores_malformed_filenames(self, temp_log_dir):
        weird_file = temp_log_dir / "CoverPicker_weird.log"
        weird_file.write_text("weird")

        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        old_file = temp_log_dir / f"CoverPicker_{old_date}.log"
        old_file.write_text("old log")

        _clean_old_logs(temp_log_dir, days=7)

        assert weird_file.exists()
        assert not old_file.exists()

    def test_clean_old_logs_handles_exception_gracefully(self, temp_log_dir, monkeypatch):
        def mock_remove(path):
            raise PermissionError("模拟权限错误")

        monkeypatch.setattr(os, 'remove', mock_remove)

        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        old_file = temp_log_dir / f"CoverPicker_{old_date}.log"
        old_file.write_text("old log")

        # 不应抛出异常
        _clean_old_logs(temp_log_dir, days=7)

    def test_setup_logger_calls_clean_old_logs(self, temp_log_dir):
        with patch('src.logger_setup._clean_old_logs') as mock_clean:
            logger = setup_logger(name="Test", log_dir=str(temp_log_dir))
            mock_clean.assert_called_once_with(temp_log_dir, days=7)

    def test_setup_logger_with_custom_level(self, temp_log_dir):
        logger = setup_logger(name="TestInfo", log_dir=str(temp_log_dir), level=logging.INFO)
        assert logger.level == logging.INFO