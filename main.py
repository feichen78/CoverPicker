# main.py
# CoverPicker 主入口

import sys
import os
import asyncio
import logging

# 在导入 PySide6 之前设置环境变量
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

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

    # 先创建 QApplication，再创建其他需要 Qt 的对象
    app = QApplication(sys.argv)
    app.setApplicationName("CoverPicker")
    app.setOrganizationName("CoverPicker")

    # 安装崩溃报告处理器
    crash_handler = CrashHandler("CoverPicker")
    crash_handler.install()

    # 检查是否有崩溃报告
    last_crash = crash_handler.check_crashes_on_startup()
    if last_crash:
        logger.info(f"检测到上次崩溃报告: {last_crash}")
        def show_crash_notice():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("上次运行崩溃")
            msg.setText("检测到上次运行时发生了崩溃。")
            msg.setInformativeText(f"崩溃报告已保存。\n\n报告文件: {os.path.basename(last_crash)}\n\n建议您将报告提交给开发者。")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
        QTimer.singleShot(500, show_crash_notice)

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