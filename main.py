# main.py
# CoverPicker 主入口
# v3.0.1: 修复退出时 qasync 事件循环关闭导致的报错

import sys
import os
import asyncio
import logging
import shutil
from pathlib import Path

# 在导入 PySide6 之前设置环境变量
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

import qasync

from src.logger_setup import setup_logger
from src.crash_handler import CrashHandler
from src.config_manager import ConfigManager
from src.version import VERSION
from ui.views.segment_view import SegmentView


def auto_restore_backup(logger):
    """自动恢复最新的备份文件（如果比当前数据库新）"""
    config = ConfigManager()
    backup_dir = config.get_backup_dir()
    if not backup_dir or not os.path.exists(backup_dir):
        logger.debug("备份目录不存在，跳过自动恢复")
        return

    backup_files = []
    for f in os.listdir(backup_dir):
        if f.startswith("coverpicker_backup_") and f.endswith(".db"):
            file_path = os.path.join(backup_dir, f)
            mtime = os.path.getmtime(file_path)
            backup_files.append((file_path, mtime))

    if not backup_files:
        logger.debug("没有找到备份文件，跳过自动恢复")
        return

    backup_files.sort(key=lambda x: x[1], reverse=True)
    latest_backup_path = backup_files[0][0]
    latest_mtime = backup_files[0][1]

    home = Path.home()
    data_dir = home / ".coverpicker"
    db_path = data_dir / "coverpicker.db"

    if not db_path.exists():
        logger.info(f"当前数据库不存在，从备份恢复: {latest_backup_path}")
        try:
            shutil.copy2(latest_backup_path, db_path)
            logger.info("自动恢复成功")
        except Exception as e:
            logger.error(f"自动恢复失败: {e}")
        return

    current_mtime = os.path.getmtime(db_path)
    if latest_mtime > current_mtime:
        logger.info(f"发现更新的备份文件: {latest_backup_path}")
        try:
            shutil.copy2(latest_backup_path, db_path)
            logger.info("自动恢复成功")
        except Exception as e:
            logger.error(f"自动恢复失败: {e}")
    else:
        logger.debug("备份文件不比当前数据库新，跳过恢复")


def main():
    logger = setup_logger("CoverPicker")
    logger.info("=" * 60)
    logger.info(f"CoverPicker v{VERSION} 启动")
    logger.info("=" * 60)

    # 自动恢复最新备份
    auto_restore_backup(logger)

    app = QApplication(sys.argv)
    app.setApplicationName("CoverPicker")
    app.setOrganizationName("CoverPicker")

    crash_handler = CrashHandler("CoverPicker")
    crash_handler.install()

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = SegmentView()
    window.setWindowTitle(f"CoverPicker - v{VERSION}")
    window.resize(1200, 800)
    window.show()

    logger.info(f"主窗口已显示 (v{VERSION})")

    def on_exit():
        logger.info("应用退出")
        crash_handler.uninstall()

    app.aboutToQuit.connect(on_exit)

    # 安全退出：先让事件循环运行，退出时正确处理
    try:
        loop.run_forever()
    except (SystemExit, KeyboardInterrupt):
        # 正常退出信号，不做额外处理
        pass
    finally:
        # 清理事件循环
        try:
            loop.close()
        except Exception as e:
            logger.debug(f"关闭事件循环时忽略异常: {e}")
        # 确保应用退出
        sys.exit(0)


if __name__ == "__main__":
    main()