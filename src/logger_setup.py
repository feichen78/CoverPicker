# src/logger_setup.py
# 日志配置模块 —— 同时输出到控制台和文件，支持日志轮转

import os
import logging
import logging.handlers
from pathlib import Path


def get_app_dir() -> Path:
    """获取应用所在目录"""
    return Path(__file__).parent.parent.absolute()


def setup_logger(app_name: str = "CoverPicker", log_dir: str = None) -> logging.Logger:
    """
    配置日志系统
    返回 root logger
    """
    if log_dir is None:
        app_dir = get_app_dir()
        log_dir = app_dir / "log"
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{app_name}.log"

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.getLogger('qasync').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    logger.info(f"日志系统初始化完成，日志文件: {log_file}")
    return logger


def get_log_file_path(app_name: str = "CoverPicker", log_dir: str = None) -> str:
    if log_dir is None:
        app_dir = get_app_dir()
        log_dir = app_dir / "log"
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    return str(log_dir / f"{app_name}.log")