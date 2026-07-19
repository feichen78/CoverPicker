# src/crash_handler.py
# 崩溃报告生成模块

import os
import sys
import platform
import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_app_dir() -> Path:
    """获取应用所在目录"""
    return Path(__file__).parent.parent.absolute()


class CrashHandler:
    """全局异常捕获和崩溃报告生成"""

    def __init__(self, app_name: str = "CoverPicker", report_dir: str = None):
        self.app_name = app_name
        if report_dir is None:
            app_dir = get_app_dir()
            report_dir = app_dir / "log" / "crashes"
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._orig_excepthook = sys.excepthook

    def install(self):
        """安装全局异常捕获"""
        sys.excepthook = self._excepthook
        logger.info("崩溃报告处理器已安装，报告目录: %s", self.report_dir)

    def uninstall(self):
        """恢复原始异常处理"""
        sys.excepthook = self._orig_excepthook

    def _excepthook(self, exc_type, exc_value, exc_tb):
        """异常捕获钩子"""
        report_path = self._generate_report(exc_type, exc_value, exc_tb)

        logger.critical(
            f"未捕获的异常: {exc_type.__name__}: {exc_value}\n"
            f"崩溃报告已保存: {report_path}"
        )

        self._orig_excepthook(exc_type, exc_value, exc_tb)

    def _generate_report(self, exc_type, exc_value, exc_tb) -> str:
        """生成崩溃报告文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"crash_report_{timestamp}.txt"
        report_path = self.report_dir / filename

        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        stack_trace = ''.join(tb_lines)

        system_info = {
            "操作系统": platform.system(),
            "操作系统版本": platform.version(),
            "操作系统发行版": platform.platform(),
            "Python版本": sys.version,
            "Python实现": platform.python_implementation(),
            "应用名称": self.app_name,
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write(f"  崩溃报告 - {self.app_name}\n")
            f.write("=" * 70 + "\n\n")

            f.write("系统信息:\n")
            f.write("-" * 70 + "\n")
            for key, value in system_info.items():
                f.write(f"  {key}: {value}\n")
            f.write("\n")

            f.write("异常信息:\n")
            f.write("-" * 70 + "\n")
            f.write(f"  异常类型: {exc_type.__name__}\n")
            f.write(f"  异常消息: {exc_value}\n")
            f.write("\n")

            f.write("堆栈跟踪:\n")
            f.write("-" * 70 + "\n")
            f.write(stack_trace)
            f.write("\n")

            f.write("=" * 70 + "\n")
            f.write("请将此报告提交给开发者以帮助修复问题。\n")
            f.write("=" * 70 + "\n")

        return str(report_path)

    def get_crash_reports(self, limit: int = 10) -> list:
        """获取崩溃报告列表"""
        reports = []
        for f in sorted(self.report_dir.glob("crash_report_*.txt"), reverse=True)[:limit]:
            reports.append({
                "path": str(f),
                "name": f.name,
                "size": f.stat().st_size,
                "mtime": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
        return reports

    def check_crashes_on_startup(self) -> Optional[str]:
        """启动时检查是否有崩溃报告"""
        reports = self.get_crash_reports(limit=1)
        if reports:
            return reports[0]["path"]
        return None