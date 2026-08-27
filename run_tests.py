# run_tests.py
# 一键运行所有测试（使用 pytest），并生成汇总报告

import sys
import pytest

def run_all_tests():
    """使用 pytest 运行所有测试，并输出汇总结果"""
    # 设置 pytest 参数：显示详细输出，捕获 stdout，不缓存
    args = [
        "tests/",                     # 测试目录
        "-v",                         # 详细输出
        "--tb=short",                 # 简短的错误回溯
        "--maxfail=1",                # 遇到第一个失败就停止（可调整）
        "--disable-warnings",         # 忽略警告
    ]
    
    # 运行 pytest，返回退出码
    exit_code = pytest.main(args)
    
    if exit_code == 0:
        print("\n" + "="*50)
        print("✅ 所有测试通过！")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("❌ 测试失败或出现错误，请查看上述输出。")
        print("="*50)
    
    return exit_code

if __name__ == "__main__":
    sys.exit(run_all_tests())