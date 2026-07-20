# main.py
# CoverPicker 主入口

import sys
import os
import asyncio
import logging

# 在导入 PySide6 之前设置环境变量
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

# 导入 qasync
import qasync

# 导入日志和崩溃报告模块
from src.logger_setup import setup_logger
from src.crash_handler import CrashHandler
from ui.views.segment_view import SegmentView


def main():
    # 设置日志
    logger = setup_logger("CoverPicker")
    logger.info("=" * 60)
    logger.info("CoverPicker 启动")
    logger.info("=" * 60)

    # 创建 QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("CoverPicker")
    app.setOrganizationName("CoverPicker")

    # 安装崩溃报告处理器（保留生成功能，但不显示启动提示）
    crash_handler = CrashHandler("CoverPicker")
    crash_handler.install()

    # 不再检查并提示崩溃报告（用户要求取消提示）
    # 但崩溃报告仍会生成，如有需要用户可手动查看 log/crashes 目录

    # 创建 qasync 事件循环
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = SegmentView()
    window.setWindowTitle("CoverPicker - 视频截图工具")
    window.resize(1200, 800)
    window.show()

    logger.info("主窗口已显示")

    # 退出时清理
    def on_exit():
        logger.info("应用退出")
        crash_handler.uninstall()
    app.aboutToQuit.connect(on_exit)

    # 使用 qasync 运行事件循环
    with loop:
        sys.exit(loop.run_forever())


if __name__ == "__main__":
    main()