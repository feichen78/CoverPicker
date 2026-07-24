# src/logger_setup.py
# 日志配置：按日期轮转，保留7天

import os
import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path


def setup_logger(name: str = "CoverPicker", log_dir: str = "log", level=logging.DEBUG):
    """配置日志：按日期命名，保留7天，控制台同时输出"""
    
    # 确保日志目录存在
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # 清理7天前的日志文件
    _clean_old_logs(log_path, days=7)

    # 创建 Logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加 Handler
    if logger.handlers:
        return logger

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # ===== 文件 Handler（按日期命名）=====
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_path / f"CoverPicker_{today}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # ===== 控制台 Handler =====
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    # 添加 Handler
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def _clean_old_logs(log_dir: Path, days: int = 7):
    """删除超过指定天数的日志文件"""
    try:
        cutoff = datetime.now() - timedelta(days=days)
        for file_path in log_dir.glob("CoverPicker_*.log"):
            # 从文件名提取日期
            try:
                date_str = file_path.stem.replace("CoverPicker_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    os.remove(file_path)
                    print(f"[LOG] 已删除旧日志: {file_path.name}")
            except ValueError:
                # 文件名格式不匹配，跳过
                continue
    except Exception as e:
        print(f"[LOG] 清理旧日志失败: {e}")