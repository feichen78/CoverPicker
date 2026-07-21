import os
import shutil
import sys

def clean_pycache(root_dir):
    for root, dirs, files in os.walk(root_dir):
        if "__pycache__" in dirs:
            cache_path = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(cache_path)
                print(f"已删除: {cache_path}")
            except Exception as e:
                print(f"删除失败: {cache_path} - {e}")

if __name__ == "__main__":
    clean_pycache(os.path.dirname(os.path.abspath(__file__)))
    print("清理完成")