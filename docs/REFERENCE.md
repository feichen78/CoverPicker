# 📘 CoverPicker 开发参考文档（Reference）

**版本**：v2.3
**最后更新**：2026-07-19
**适用版本**：CoverPicker v2.3.0

---

## 文档用途

本文档是 CoverPicker 开发过程中的技术参考手册，包含：

1. **技术参考**：FFmpeg/FFprobe 调用规范、SQLite 设计、异步架构
2. **开发规范**：布局开发原则、代码编写规范、问题排查流程
3. **决策记录**：已确定的技术方案和设计决策

---

## 目录

1. FFmpeg / FFprobe 调用规范
2. 异步任务架构
3. SQLite 数据库设计
4. 网格布局与渲染规范
5. 缓存管理策略
6. Zoom 精修界面设计参考
7. 开发规范与决策记录
8. 错误处理与日志规范
9. 性能优化清单

---

## 1. FFmpeg / FFprobe 调用规范

### 1.1 核心原则

- 所有 FFmpeg/FFprobe 调用必须**异步执行**，不阻塞 GUI 主线程
- 使用 `asyncio.create_subprocess_exec` 而非 `subprocess.run`
- **必须消费子进程的 stdout/stderr 管道**，否则管道缓冲区满时会导致死锁
- NAS 网络路径直接透传给 FFmpeg，**绝不复制源文件**

### 1.2 FFprobe 元数据解析

```bash
# 基础元数据
ffprobe -v error -print_format json -show_streams -show_format -show_chapters "{video_path}"

# 关键帧扫描
ffprobe -v error -select_streams v:0 -show_packets -print_format json -read_intervals "%+#1000" "{video_path}"
Python 异步封装模板：

python
import asyncio
import json

async def run_ffprobe_json(video_path: str, args: list = None) -> dict:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        *args or [],
        video_path
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFprobe failed: {stderr.decode()}")
    return json.loads(stdout.decode())
1.3 FFmpeg 三套参数模板
模板1：批量分区均匀抽帧（网格截图）

bash
ffmpeg -hide_banner -ss {start_sec} -i "{video_path}" -t {segment_duration} \
-vf "fps={calc_fps},scale=-1:{preview_height}" -q:v 7 -y "{output_dir}/frame_%03d.jpg"
参数	说明
-ss 在 -i 前	快速 Seek 模式，跳至最近关键帧
scale=-1:{height}	高度固定，宽度自适应，不拉伸
-q:v 7	JPG 中等压缩，平衡体积与清晰度
fps={calc_fps}	均匀抽帧，保证时间分布
模板2：单时间点高清帧导出（收藏截图 / 导出剧照）

bash
ffmpeg -hide_banner -i "{video_path}" -ss {exact_time} -frames:v 1 -q:v 2 -y "{output_path}.png"
参数	说明
-ss 在 -i 后	精确 Seek 模式，逐帧解码到目标位置
-frames:v 1	仅输出单帧，提前终止解码
-q:v 2	最高画质，无压缩损耗
模板3：无损视频片段导出

bash
ffmpeg -hide_banner -ss {start_keyframe} -i "{video_path}" -t {clip_duration} \
-c:v copy -c:a copy -avoid_negative_ts make_zero -map 0:v -map 0:a? -y "{output_path}.mp4"
参数	说明
-c:v copy -c:a copy	直接拷贝编码流，无转码、无画质损失
-avoid_negative_ts make_zero	修复剪切后 PTS 负值，避免黑屏
-map 0:v -map 0:a?	仅保留视频 + 可选音频
1.4 关键帧提取策略
bash
# 提取 I-帧作为候选
ffmpeg -i input.mp4 -vf "select='eq(pict_type,I)',scale=320:-1" -vsync vfr -q:v 2 keyframe_%04d.jpg
2. 异步任务架构
2.1 架构原则
GUI 主线程：仅负责界面渲染、用户交互、状态标记

媒体处理子进程：所有 FFmpeg/FFprobe 调用放入异步线程池

数据隔离：不读取完整视频到内存，仅读取元数据和按需局部流

2.2 任务调度规范
任务类型	优先级	说明
高清导出 / Zoom 精修	高	用户直接操作，需快速响应
区段抽帧	中	网格预览，可接受短暂等待
元数据批量扫描	低	后台执行，不阻塞用户操作
2.3 Python + asyncio 封装模板
python
import asyncio
from PySide6.QtCore import QObject, Signal

class FFmpegWorker(QObject):
    progress = Signal(int, int)  # current, total
    finished = Signal(object)    # result
    error = Signal(str)

    async def _run_ffmpeg(self, cmd, progress_callback=None):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            # 解析 frame=XXX time=HH:MM:SS.xxx
            # 更新进度
        stdout, stderr = await proc.communicate()
        return stdout

    def run(self, cmd):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._run_ffmpeg(cmd))
2.4 任务取消机制
切换视频 / 区段时，立即取消当前正在执行的抽帧任务

使用 asyncio.Task.cancel() + asyncio.CancelledError 处理

取消后释放 FFmpeg 子进程资源，避免内存泄漏

3. SQLite 数据库设计
3.1 三表结构
sql
-- 视频主表
CREATE TABLE videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    duration INTEGER,
    resolution TEXT,
    file_size INTEGER,
    modified_time INTEGER,
    is_viewed BOOLEAN DEFAULT 0,
    is_starred BOOLEAN DEFAULT 0,
    is_exported BOOLEAN DEFAULT 0,
    last_edited INTEGER,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);

-- 分区状态表
CREATE TABLE segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    segment_label TEXT NOT NULL,
    time_start INTEGER NOT NULL,
    time_end INTEGER NOT NULL,
    is_viewed BOOLEAN DEFAULT 0,
    has_starred BOOLEAN DEFAULT 0,
    has_exported BOOLEAN DEFAULT 0,
    excluded_ranges TEXT DEFAULT '[]',
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    UNIQUE(video_id, segment_label)
);

-- 收藏截图表
CREATE TABLE favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    segment_label TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    thumbnail_path TEXT,
    thumbnail_name TEXT,
    is_exported INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s','now')),
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);
3.2 索引策略
sql
CREATE INDEX idx_videos_viewed ON videos(is_viewed);
CREATE INDEX idx_videos_starred ON videos(is_starred);
CREATE INDEX idx_videos_exported ON videos(is_exported);
CREATE INDEX idx_favorites_video ON favorites(video_id);
CREATE INDEX idx_videos_file_path ON videos(file_path);
CREATE INDEX idx_videos_file_id ON videos(file_id);
3.3 状态优先级
查询时排序规则：ORDER BY is_exported DESC, is_starred DESC, is_viewed DESC

优先级	状态	图标
最高	已导出	✅ 绿色对勾
中	有收藏	⭐ 黄色星标
最低	已浏览	👁️ 眼睛
3.4 事务规范
python
# 使用事务保证状态一致性
with db_connection:
    db_connection.execute("UPDATE videos SET is_starred = 1 WHERE id = ?", (video_id,))
    db_connection.execute("INSERT INTO favorites (video_id, segment_id, timestamp_ms) VALUES (?, ?, ?)", ...)
4. 网格布局与渲染规范
4.1 弹性列数计算
python
def calculate_grid_cols(viewport_width: int, min_img_w: int = 160, spacing: int = 4) -> int:
    spacing = 4
    padding = 6
    max_cols = (viewport_width - padding * 2 + spacing) // (min_img_w + spacing)
    return max(1, min(9, max_cols))
4.2 图片尺寸计算
python
def calculate_img_size(viewport_width: int, cols: int, spacing: int = 4) -> Tuple[int, int]:
    padding = 6
    img_w = (viewport_width - padding * 2 - spacing * (cols - 1)) // cols
    img_h = int(img_w * 0.75)
    return max(160, img_w), max(120, img_h)
4.3 延迟加载机制
python
def _on_scroll(self, value):
    viewport_rect = self.scroll.viewport().rect()
    for label in self.image_labels:
        if viewport_rect.intersects(label.geometry()):
            label.load_image()
        else:
            label.release_image()
4.4 布局重建 vs 属性更新
场景	操作	说明
首次加载 / 数据变化	完全重建	重新创建所有 GridLayout
窗口大小变化（列数不变）	只更新尺寸	仅调整图片大小和列拉伸
窗口大小变化（列数变化）	完全重建	列数变化必须重建 GridLayout
5. 缓存管理策略
5.1 三级缓存分层
层级	存储位置	内容	生命周期
内存缓存	RAM	当前区段缩略图（≤25张）	切换区段/视频时清空
磁盘缓存	本地文件夹	所有缩略图（按视频ID/区段分层）	长期保存，手动/自动清理
SQLite索引	数据库	帧元数据（路径、状态）	长期保存
5.2 缓存目录结构
text
~/.coverpicker/cache/
├── {video_hash_1}/
│   ├── A/
│   │   ├── frame_01.jpg
│   │   └── frame_02.jpg
│   └── B/
│       └── frame_01.jpg
└── {video_hash_2}/
    └── A/
        └── frame_01.jpg
5.3 自动清理阈值
缓存总大小超过 5GB 时触发清理提示 ✅ v2.0 已实现

优先删除最早未操作的视频缩略图

锁定 / 收藏的截图保留

6. Zoom 精修界面设计参考
6.1 界面布局
text
┌─────────────────────────────────────────────────────────────┐
│  中心预览区（占据大部分窗口）                              │
│  展示当前帧高清预览                                        │
│  支持鼠标滚轮缩放（0.1x ~ 5.0x）                          │
│  支持拖拽平移                                              │
├─────────────────────────────────────────────────────────────┤
│  底部时间轴控件（QSlider）                                │
│  显示当前分区起止时间，可拖拽定位                          │
│  实时显示精确时间码（HH:mm:ss.zzz）                       │
├─────────────────────────────────────────────────────────────┤
│  ◀ 上一帧  ▶ 下一帧  [加锁] [收藏] [导出] [返回]         │
│  键盘：← → 逐帧切换                                       │
└─────────────────────────────────────────────────────────────┘
6.2 交互规范
交互	响应
鼠标滚轮	缩放预览图（0.1x ~ 5.0x）
拖拽平移	移动预览图（缩放后）
← / → 键	前后移动 1 帧
Shift + ← / →	前后移动 100ms
时间轴拖拽	跳转到目标位置
6.3 帧提取参数
bash
# Zoom 精修：前后4秒，高帧率提取
ffmpeg -i "{video_path}" -ss {t-4} -t 8 -vf "fps=10" -q:v 2 "{output_dir}/zoom_%04d.jpg"
7. 开发规范与决策记录
7.1 布局开发规范（2026-07-11 确立）
原则1：区分"初始化"和"更新"

操作类型	应该执行的操作
首次加载 / 数据变化	完全重建
窗口大小变化（列数不变）	只更新属性
窗口大小变化（列数变化）	完全重建
原则2：布局问题排查顺序

布局是否在创建时固定了？（如 GridLayout 的列数）

更新方法是否修改了布局结构？（只改属性 vs 重建结构）

数据来源是否正确？（如 viewport().width() 是否返回正确值？）

原则3：视口尺寸获取

python
def _get_viewport_size(self) -> Tuple[int, int]:
    vw = self.scroll.viewport().width() - 10
    vh = self.scroll.viewport().height() - 10
    if vw < 100 or vw < self.width() * 0.95:
        vw = self.width() - 20
    if vh < 100:
        vh = 700
    return vw, vh
7.2 AI 开发助手行为规范（2026-07-11 确立）
规则1：写代码前先回答三个问题

在写任何代码之前，必须先输出分析：

text
【分析】
1. 数据生命周期：这次操作涉及哪些数据？是新建、修改还是删除？
2. 操作粒度：这次修改需要完全重建界面，还是只需要更新已有控件的属性？
3. 如果重建会怎样？如果只更新会怎样？
规则2：代码提供方式

每次修改任何 .py 文件时，提供该文件的完整代码

明确标注文件路径（如 ui/views/segment_view.py）

新增或修改依赖文件时，也需提供完整文件

规则3：FFmpeg 调用规范

使用 asyncio.create_subprocess_exec 而非 subprocess.run

必须消费 stdout/stderr 管道，防止死锁

所有耗时操作放入异步线程池，不阻塞 GUI

7.3 错误处理规范
python
try:
    result = await run_ffmpeg(cmd)
except asyncio.CancelledError:
    logger.info("Task cancelled")
    return
except Exception as e:
    logger.error(f"FFmpeg failed: {e}")
    emit_progress_error(str(e))
    return
8. 错误处理与日志规范
8.1 日志级别
级别	用途	示例
DEBUG	开发调试	FFmpeg 命令参数
INFO	正常操作	加载视频、截图成功
WARNING	可恢复异常	截图失败，重试中
ERROR	需关注错误	FFprobe 解析失败
8.2 日志输出
同时输出到控制台和文件

日志文件：CoverPicker/log/CoverPicker.log

日志轮转：单文件最大 10MB，保留 5 个备份

崩溃报告：CoverPicker/log/crashes/crash_report_*.txt

8.3 用户错误提示
使用 QMessageBox 显示可操作的错误信息

状态栏显示轻量提示（非阻塞）

python
if duration is None:
    QMessageBox.critical(self, "错误", f"无法获取视频时长: {video_path}\n请检查文件是否损坏。")
    return
8.4 NAS 路径兼容
路径含空格自动加双引号

捕获网络 IO 超时，断线任务自动终止并更新界面状态

9. 性能优化清单
优化项	状态	说明
FFmpeg 异步调用	✅ 已实现	使用 asyncio + QEventLoop
网格延迟加载	⬜ 待实现	仅加载可见区域图片
缓存分级管理	⬜ 待实现	内存/磁盘/SQLite 三级缓存
批量任务串行排队	⬜ 待实现	避免并发 NAS IO 卡顿
任务取消机制	✅ 已实现	切换区段时取消未完成任务
缓存自动清理	✅ 已实现	超过 5GB 触发清理提示
元数据缓存	✅ 已实现	导入时缓存 duration/size/mtime
并发控制	✅ 已实现	信号量限制 FFmpeg 进程数（默认3）
快速关键帧提取	✅ 已实现	使用 -skip_frame nokey
崩溃报告	✅ 已实现	全局异常捕获 + 报告生成
最后更新：2026-07-19