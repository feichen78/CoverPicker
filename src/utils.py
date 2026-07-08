# region --- 通用工具函数 ---
import os

def get_unique_filepath(filepath):
    """
    检查文件是否存在，如果存在则自动在文件名后追加 _01, _02 等后缀，防止覆盖。
    """
    if not os.path.exists(filepath):
        return filepath

    directory, filename = os.path.split(filepath)
    name, ext = os.path.splitext(filename)
    
    counter = 1
    while True:
        new_filename = f"{name}_{counter:02d}{ext}"
        new_filepath = os.path.join(directory, new_filename)
        if not os.path.exists(new_filepath):
            return new_filepath
        counter += 1

# endregion