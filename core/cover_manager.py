from pathlib import Path
import shutil
import hashlib


class CoverManager:
    def __init__(self, base_dir="StillPic"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _video_id(self, video_path):
        """
        用路径生成唯一ID（避免同名冲突）
        """
        return hashlib.md5(str(video_path).encode("utf-8")).hexdigest()[:8]

    def _video_name(self, video_path):
        return Path(video_path).stem

    def get_video_folder(self, video_path):
        video_path = Path(video_path)

        name = self._video_name(video_path)
        vid = self._video_id(video_path)

        folder_name = f"{name}_{vid}"

        target_dir = self.base_dir / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        return target_dir

    def save_cover(self, video_path, image_path):
        target_dir = self.get_video_folder(video_path)
        target_file = target_dir / "cover.jpg"

        shutil.copy2(image_path, target_file)

        print(f"✅ 封面已保存: {target_file}")

        return target_file

    def cover_exists(self, video_path):
        target_dir = self.get_video_folder(video_path)
        return (target_dir / "cover.jpg").exists()