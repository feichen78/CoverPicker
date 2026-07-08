# region --- 视频扫描引擎 ---
import os
import asyncio

class VideoScanner:
    """视频扫描器"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.supported_extensions = self.config.get("supported_extensions", [
            ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".ts", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"
        ])
        self.nas_path = self.config.get("nas_video_path", "Z:\\")
        print(f"[VideoScanner] 初始化，扫描路径: {self.nas_path}")
        print(f"[VideoScanner] 支持格式: {self.supported_extensions}")
    
    async def scan_videos(self, root_path: str = None) -> list:
        """递归扫描目录下的视频文件"""
        if root_path is None:
            root_path = self.nas_path
        
        print(f"[扫描] 正在扫描目录: {root_path}")
        videos = []
        
        if not os.path.exists(root_path):
            print(f"[扫描] ❌ 路径不存在: {root_path}")
            return videos
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._scan_sync_recursive, root_path)
            videos = result
            print(f"[扫描] ✅ 完成，找到 {len(videos)} 个视频")
            
            if videos:
                print("[扫描] 找到的视频:")
                for v in videos[:5]:
                    print(f"  - {os.path.basename(v)}")
                if len(videos) > 5:
                    print(f"  ... 还有 {len(videos)-5} 个")
            else:
                print("[扫描] ⚠️ 没有找到视频文件")
                print("[扫描] 请确认目录下是否有 .mp4, .mkv, .avi 等格式的视频")
                
        except Exception as e:
            print(f"[扫描异常] {e}")
        
        return videos
    
    def _scan_sync_recursive(self, root_path: str) -> list:
        """递归扫描（在executor中运行）"""
        videos = []
        try:
            for dirpath, dirnames, filenames in os.walk(root_path):
                # 跳过系统隐藏文件夹
                dirnames[:] = [d for d in dirnames if not d.startswith('.') and not d.startswith('$')]
                
                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in self.supported_extensions:
                        full_path = os.path.join(dirpath, filename)
                        videos.append(full_path)
                        
                # 限制扫描深度，避免扫描过久（可选）
                # 如果目录层级太深，可以限制 max_depth
                
        except Exception as e:
            print(f"[扫描异常] {e}")
        return videos
    
    # 保留旧的单目录扫描方法（备用）
    def _scan_sync(self, root_path: str) -> list:
        """单目录扫描（不递归）"""
        videos = []
        try:
            for item in os.listdir(root_path):
                full_path = os.path.join(root_path, item)
                if os.path.isfile(full_path):
                    ext = os.path.splitext(item)[1].lower()
                    if ext in self.supported_extensions:
                        videos.append(full_path)
        except Exception as e:
            print(f"[扫描异常] {e}")
        return videos
    
    @staticmethod
    def calculate_segments(duration: float) -> list:
        """计算分段（<5分钟合并，≥5分钟均分5段）"""
        if duration <= 0:
            return []
        
        if duration < 300:  # 5分钟
            return [{"name": "A", "start": 0, "end": duration}]
        
        seg_duration = duration / 5
        segments = []
        for i in range(5):
            start = i * seg_duration
            end = (i + 1) * seg_duration if i < 4 else duration
            segments.append({
                "name": chr(ord('A') + i),
                "start": start,
                "end": end
            })
        return segments
# endregion