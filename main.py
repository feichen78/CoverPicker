# main.py
# CoverPicker 主入口
# v3.2: O3 + 3.2.1 数据库完整性检查与自动恢复
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

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer

import qasync

from src.logger_setup import setup_logger
from src.crash_handler import CrashHandler
from src.config_manager import ConfigManager
from src.version import VERSION
from ui.views.segment_view import SegmentView


def auto_restore_backup(logger) -> tuple:
    """
    自动恢复最新的备份文件（如果比当前数据库新）
    返回 (是否尝试恢复, 是否成功, 错误信息)
    """
    config = ConfigManager()
    backup_dir = config.get_backup_dir()
    if not backup_dir or not os.path.exists(backup_dir):
        logger.debug("备份目录不存在，跳过自动恢复")
        return False, False, "备份目录不存在"

    backup_files = []
    for f in os.listdir(backup_dir):
        if f.startswith("coverpicker_backup_") and f.endswith(".db"):
            file_path = os.path.join(backup_dir, f)
            mtime = os.path.getmtime(file_path)
            backup_files.append((file_path, mtime))

    if not backup_files:
        logger.debug("没有找到备份文件，跳过自动恢复")
        return False, False, "没有找到备份文件"

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
            return True, True, "数据库不存在，已从备份恢复"
        except Exception as e:
            logger.error(f"自动恢复失败: {e}")
            return True, False, f"备份恢复失败: {e}"

    current_mtime = os.path.getmtime(db_path)
    if latest_mtime > current_mtime:
        logger.info(f"发现更新的备份文件: {latest_backup_path}")
        try:
            shutil.copy2(latest_backup_path, db_path)
            logger.info("自动恢复成功")
            return True, True, "已从更新的备份文件恢复"
        except Exception as e:
            logger.error(f"自动恢复失败: {e}")
            return True, False, f"备份恢复失败: {e}"
    else:
        logger.debug("备份文件不比当前数据库新，跳过恢复")
        return False, False, "备份文件不比当前数据库新"


def check_and_restore_database_on_corruption(logger, parent_widget=None) -> bool:
    """
    3.2.1: 启动时检查数据库完整性，损坏时自动恢复
    返回 True 表示数据库正常或已恢复，False 表示恢复失败
    """
    from src.database import Database
    db = Database()
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA quick_check")
        result = cursor.fetchone()
        if result and result[0] == "ok":
            logger.debug("数据库 quick_check 通过")
            db.close()
            return True
        else:
            logger.warning(f"数据库 quick_check 失败: {result}")

        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()
        if integrity_result and integrity_result[0] == "ok":
            logger.debug("数据库 integrity_check 通过（quick_check 误报）")
            db.close()
            return True

        logger.error(f"数据库 integrity_check 失败: {integrity_result}")
        db.close()

        logger.info("数据库损坏，尝试从备份恢复...")
        config = ConfigManager()
        backup_dir = config.get_backup_dir()
        if not backup_dir or not os.path.exists(backup_dir):
            msg = "数据库已损坏，但未设置备份目录或目录不存在，无法自动恢复。\n请设置备份目录后手动恢复。"
            if parent_widget:
                QMessageBox.critical(parent_widget, "数据库损坏", msg)
            else:
                logger.critical(msg)
            return False

        backup_files = []
        for f in os.listdir(backup_dir):
            if f.startswith("coverpicker_backup_") and f.endswith(".db"):
                file_path = os.path.join(backup_dir, f)
                mtime = os.path.getmtime(file_path)
                backup_files.append((file_path, mtime))

        if not backup_files:
            msg = "数据库已损坏，但备份目录中未找到备份文件。\n请检查备份目录后手动恢复。"
            if parent_widget:
                QMessageBox.critical(parent_widget, "数据库损坏", msg)
            else:
                logger.critical(msg)
            return False

        backup_files.sort(key=lambda x: x[1], reverse=True)
        latest_backup_path = backup_files[0][0]

        logger.info(f"尝试从最新备份恢复: {latest_backup_path}")
        success, result = db.restore(latest_backup_path)
        if success:
            logger.info("数据库从备份恢复成功")
            if parent_widget:
                QMessageBox.information(
                    parent_widget,
                    "数据库已恢复",
                    f"数据库已从最新的备份文件恢复。\n\n备份文件: {os.path.basename(latest_backup_path)}"
                )
            return True
        else:
            msg = f"从备份恢复失败:\n{result}\n\n请尝试手动恢复。"
            if parent_widget:
                QMessageBox.critical(parent_widget, "数据库恢复失败", msg)
            else:
                logger.critical(msg)
            return False

    except Exception as e:
        logger.error(f"数据库完整性检查异常: {e}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "数据库错误", f"数据库检查时发生异常:\n{e}")
        return False


def main():
    logger = setup_logger("CoverPicker")
    logger.info("=" * 60)
    logger.info(f"CoverPicker v{VERSION} 启动")
    logger.info("=" * 60)

    attempted, success, msg = auto_restore_backup(logger)
    if attempted and not success:
        logger.warning(f"自动恢复备份失败: {msg}")
    elif attempted and success:
        logger.info(f"自动恢复备份成功: {msg}")

    app = QApplication(sys.argv)
    app.setApplicationName("CoverPicker")
    app.setOrganizationName("CoverPicker")

    crash_handler = CrashHandler("CoverPicker")
    crash_handler.install()

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    db_ok = check_and_restore_database_on_corruption(logger, parent_widget=None)

    window = SegmentView()
    window.setWindowTitle(f"CoverPicker - v{VERSION}")
    window.resize(1200, 800)
    window.show()

    if not db_ok:
        QTimer.singleShot(100, lambda: QMessageBox.critical(
            window,
            "数据库错误",
            "数据库已损坏且无法自动恢复。\n请检查备份目录并尝试手动恢复（左侧菜单 → 恢复状态）。"
        ))

    logger.info(f"主窗口已显示 (v{VERSION})")

    def on_exit():
        logger.info("应用退出")
        crash_handler.uninstall()

    app.aboutToQuit.connect(on_exit)

    try:
        loop.run_forever()
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        try:
            loop.close()
        except Exception as e:
            logger.debug(f"关闭事件循环时忽略异常: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()