📋 CoverPicker 项目进度日志
维护说明：本文件记录项目开发进度，对照 PRODUCT.md v4.0 进行状态跟踪。
当前版本基于 PySide6 重构，核心交互功能稳定。

🏷️ 当前版本信息
版本号：v1.0.0-stable

版本名称：核心交互稳定版

发布日期：2026-07-12

状态：✅ 稳定运行（截图显示、分区切换、锁定/收藏/导出均正常，协程任务取消已修复）

对应 PRODUCT.md 版本：v4.0

📊 整体完成度评估（对照 PRODUCT.md v4.0）
功能模块	权重	完成度	说明
视频分区浏览（7.2）	8%	85%	自动分段、切换已完成；分段状态标记（✓/★/▼）已实现；时间范围显示待实现
Grid 候选浏览（7.3）	10%	90%	密度切换、截图显示已完成；竖版拉伸已修复；截图编号已实现
收藏管理（7.6）	10%	90%	收藏池、查看收藏弹窗、分段星标已完成；SQLite持久化待实现
锁定功能（7.3/7.4）	8%	95%	锁定/解锁、刷新未锁定、全部重抽已完成
导出功能（7.4/7.5）	10%	40%	单张导出已完成；批量导出、视频片段导出待实现
Zoom 精修（7.3/7.4）	15%	0%	完全未实现（因稳定性问题暂时移除）
左侧视频列表状态标识（7.1）	5%	0%	👁️/⭐/✅ 状态标识未实现
右侧预览面板（7.4）	12%	0%	完全未实现（v1.3 规划）
搜索/导入/清理缓存（7.1/7.5）	5%	0%	完全未实现（v1.3 规划）
NAS 级持久化（9）	12%	10%	无状态持久化，仅内存缓存
UI/交互与基础框架（6/8）	5%	95%	布局稳定，交互规则统一
加权综合完成度：约 45%

✅ 已完成功能（当前版本 v1.0.0）
基础框架与界面
迁移至 PySide6（Qt for Python）桌面应用

综合布局：左侧视频列表 + 右侧主工作区

视频扫描：支持 Z:\ 目录下常见视频格式

视频信息显示：时长、大小

分段导航：A/B/C/D/E 五分区切换

网格密度切换：9/12/16/25 张布局

分段状态标记：已浏览 ✓、有收藏 ★、有导出 ▼

排除区间：手动设置排除时间段

截图生成与显示
异步调用 FFmpeg 提取关键帧

截图自动裁剪片头片尾

截图网格自适应显示（保持宽高比）

每张截图左下角显示时间戳

左上角显示截图序号

选中状态：左上角蓝色圆点

锁定状态：🔒 标记

跨视频状态缓存（内存中）

收藏管理（7.6）
收藏/取消收藏选中截图（⭐ 标记）

左侧面板显示收藏总数

分段按钮显示 ★ 标记

查看收藏弹窗（自适应布局，支持最大化）

收藏池跨分区持久

锁定功能
锁定/解锁选中截图

刷新未锁定

全部重抽

导出功能
导出选中的截图到 StillPic/视频名/ 目录

导出后右下角绿点标记

收藏弹窗中导出选中的收藏截图

交互操作
单击：选中/取消选中

双击：放大预览（滚轮缩放 + 拖动平移）

全选 / 取消全选

状态持久化（v1.0 部分）
_save_state_to_db() 方法：正确计算 is_starred 和 is_exported

修复：从 screenshots 中检查收藏状态，而非从 favorites

收藏弹窗布局（v1.0 修复）
修复：_get_viewport_size() 在窗口未渲染时返回正确值

修复：_calculate_optimal_layout() 考虑滚动条宽度

修复：列数变化时完全重建布局，而非只更新属性

修复：所有列数都被跳过时的兜底逻辑

协程任务管理（v1.0 修复）
load_video() 方法：添加任务取消逻辑，防止快速切换视频时的协程冲突

_load_segment() 方法：添加 CancelledError 捕获和取消检查

refresh_unlocked() 方法：添加 CancelledError 捕获

reset_all() 方法：添加 CancelledError 捕获

closeEvent() 方法：添加任务取消逻辑

导入兼容性（v1.0 修复）
从 src.video_scanner 导入 extract_frame，不再使用不存在的 VideoProcessor

🚧 未完成功能
🔴 高优先级（v1.1 规划）
SQLite 状态持久化（当前 _save_state_to_db() 已实现但未与数据库联动）

Zoom 精修（L1-L4）恢复

分区按钮显示时间范围

🟡 中优先级（v1.2 规划）
批量导出收藏截图

撤销/重做

自定义分区数量

🟢 低优先级（v1.3 规划）
右侧预览面板

时间轴选段 + 导出片段

搜索视频

导入视频

清理缓存

左侧视频列表状态标识

📁 当前项目结构
text
C:\CoverPicker
├── main.py
├── requirements.txt
├── .venv/
├── src/
│   ├── database.py
│   ├── video_scanner.py
│   └── __init__.py
├── ui/
│   └── views/
│       ├── segment_view.py (主视图，稳定版 ✅)
│       ├── zoom_dialog.py (Zoom 精修弹窗)
│       ├── zoom_preview.py (放大预览)
│       └── exclude_dialog.py (排除区间)
├── StillPic/ (截图导出目录)
└── docs/ (文档目录)
🛠️ 技术栈
组件	版本 / 说明
Python	3.13
GUI 框架	PySide6 6.11.1 (Qt for Python)
视频处理	FFmpeg / FFprobe
异步框架	asyncio + QEventLoop
数据库	未启用（v1.1 规划 SQLite）
⚠️ 已知问题
Zoom 精修未实现：产品核心差异化功能未实现

无状态持久化：关闭程序后所有状态丢失（_save_state_to_db() 已实现但数据库写入未完成）

分区时间范围未显示：PRODUCT.md 7.2 规划功能

📝 开发日志（2026-07-12）
今日修复：协程任务取消错误
问题现象：

快速切换视频时出现 RuntimeError: Cannot enter into task <Task> while another task is being executed

日志中出现 Task was destroyed but it is pending!

问题链条：

text
用户快速切换视频
↓
load_video() 被调用，创建新的 _load_segment 任务
↓
之前的 _load_segment 任务尚未完成
↓
两个任务同时执行，产生协程冲突
↓
RuntimeError: Cannot enter into task while another task is being executed
根本原因：

load_video() 在切换视频时没有取消正在进行的 _load_segment 任务

_load_segment() 中没有正确处理 CancelledError

refresh_unlocked() 和 reset_all() 中同样缺少取消处理

修复方案：

load_video() 方法：

python
# 取消正在进行的加载任务
if self._load_task and not self._load_task.done():
    self._load_task.cancel()
    logger.debug(f"取消之前的加载任务: {self.video_path}")
self._load_task = None
_load_segment() 方法：

python
# 检查当前任务是否被取消
current_task = asyncio.current_task()
if current_task and current_task.cancelled():
    logger.debug(f"分段 {seg_idx} 加载被取消（任务状态检查）")
    return

# 在循环中检查取消状态
if current_task and current_task.cancelled():
    logger.debug(f"分段 {seg_idx} 加载被取消（循环中检查）")
    return

# 捕获 CancelledError
try:
    success = await asyncio.to_thread(extract_frame, self.video_path, t, temp_path)
except asyncio.CancelledError:
    logger.debug(f"截图任务被取消: {label} {idx}")
    if os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except:
            pass
    raise
refresh_unlocked() 和 reset_all() 方法：

python
except asyncio.CancelledError:
    logger.debug("操作被取消")
closeEvent() 方法：

python
if self._load_task and not self._load_task.done():
    self._load_task.cancel()
经验教训：

异步任务必须显式取消，不能依赖垃圾回收

每个 create_task 的调用点都需要保存任务引用

在异步操作中要定期检查取消状态

asyncio.to_thread 中抛出的 CancelledError 需要被捕获并重新抛出

今日修复：is_starred 计算错误
问题现象：

日志中 is_starred=False，但实际已有收藏

分区 A 显示 has_starred=False，但该分区有收藏

根本原因：

_save_state_to_db() 从 self.favorites 计算 is_starred

但 self.favorites 包含所有视频的收藏，不只是当前视频

应直接从 self.screenshots 中检查当前视频的收藏状态

修复方案：

python
# 修复前
is_starred = any(
    f.get('segment') == seg_label
    for seg_label, items in self.screenshots.items()
    for f in self.favorites
    if f.get('video_path') == self.video_path and f.get('segment') == seg_label
)

# 修复后
is_starred = any(
    item.get('favorite', False)
    for seg_label, items in self.screenshots.items()
    for item in items
)
经验教训：

数据源要明确：screenshots 是当前视频的数据源

favorites 是跨视频的全局数据，不应直接用于计算当前视频状态

今日修复：收藏弹窗布局计算
问题现象：

所有列数都被跳过，触发 WARNING

布局计算失败，使用兜底逻辑

根本原因：

没有考虑滚动条宽度

使用单一维度比较（img_w > best_img_w），而非面积比较

兜底逻辑不够健壮

修复方案：

python
# 考虑滚动条宽度
scrollbar_width = 12
available_width = viewport_width - padding * 2 - scrollbar_width

# 使用面积比较
current_area = img_w * img_h
best_area = best_img_w * best_img_h
if current_area > best_area:
    best_cols = cols
    best_img_w = img_w
    best_img_h = img_h

# 改进兜底逻辑
if not found_valid:
    best_cols = max_cols_by_width
    scrollbar_width = 12
    available_width = viewport_width - padding * 2 - scrollbar_width
    best_img_w = max(self.MIN_IMG_W, (available_width - spacing * (best_cols - 1)) // best_cols)
    best_img_h = max(self.MIN_IMG_H, int(best_img_w * self.IMG_ASPECT))
经验教训：

布局计算要考虑所有影响宽度的因素（滚动条、边距、间距）

使用面积比较比单维度比较更合理

兜底逻辑要能处理所有边界情况

今日修复：导入兼容性
问题现象：

ModuleNotFoundError: No module named 'src.video_processor'

根本原因：

代码中使用了不存在的 VideoProcessor 类

项目实际使用 src.video_scanner 中的 extract_frame 函数

修复方案：

将 from src.video_scanner import VideoProcessor, extract_frame 改为 from src.video_scanner import extract_frame

移除 VideoProcessor 的所有引用

在 load_video() 中使用 get_video_duration 获取视频信息

经验教训：

修改代码前要确认项目实际存在的模块和类

不要引入不存在的依赖

📌 开发协作规则
基本原则
代码提供方式：

小修改（≤3处）：提供"修改1/2/3"格式，明确标注查找起始语句和结束语句，用户可精确替换。

大修改（>3处）或新增段落：必须提供该文件的完整代码（从头到尾）。

文件路径标注：每次提供代码时，必须明确标注文件路径（如 ui/views/segment_view.py）。

依赖说明：若新增或修改了依赖文件，也必须提供完整文件。

改错规则：

明确的报错代码（如 Traceback 信息）：直接修复，提供完整代码，不需要确认。

图片或文字描述（无明确报错代码）：先与用户确认错误现象，确认后分析原因并提供完整代码。

禁止让用户确认"分析是否正确"，确认现象后直接给代码。

AI 开发助手行为规则
规则1：写代码前先回答三个问题

数据生命周期：这次操作涉及哪些数据？是新建、修改还是删除？

操作粒度：这次修改需要完全重建界面，还是只需要更新已有控件的属性？

如果重建会怎样？如果只更新会怎样？

规则2：区分"初始化"和"更新"

操作类型	应该执行的操作
首次加载 / 数据变化	完全重建
窗口大小变化（列数不变）	只更新属性
窗口大小变化（列数变化）	完全重建
规则3：布局问题排查顺序

布局是否在创建时固定了？（如 GridLayout 的列数）

更新方法是否修改了布局结构？（只改属性 vs 重建结构）

数据来源是否正确？（如 viewport().width() 是否返回正确值？）

📌 下一阶段计划
v1.1 目标
SQLite 持久化：实现 _save_state_to_db() 与数据库的完整联动

Zoom 精修恢复：实现 L1-L4 精修截图功能

分区时间范围显示：在分段按钮上显示 00:00:00-00:32:20 格式

v1.0 稳定版验证清单
核心交互（网格、分区、收藏、锁定、导出）均正常

is_starred 计算正确

收藏弹窗布局自适应正确

协程任务取消正常

导入兼容性正确

最后更新：2026-07-12

# 📋 CoverPicker 项目进度日志

## 🏷️ 当前版本信息
- **版本号：** v1.0.0-stable
- **版本名称：** 核心交互稳定版
- **发布日期：** 2026-07-12
- **状态：** ⚠️ 存在收藏匹配精度问题（0.5秒阈值导致误匹配）
- **对应 PRODUCT.md 版本：** v4.0


## 📊 整体完成度评估

| 功能模块 | 权重 | 完成度 | 说明 |
|---------|------|--------|------|
| 视频分区浏览 | 8% | 85% | 自动分段、切换正常 |
| Grid 候选浏览 | 10% | 90% | 密度切换、截图显示正常 |
| 收藏管理 | 10% | 75% | 收藏池正常，但恢复匹配精度有误 |
| 锁定功能 | 8% | 95% | 锁定/解锁正常 |
| 导出功能 | 10% | 40% | 导出正常，但状态同步有 bug |
| 收藏弹窗 | 15% | 50% | 显示正常，但星星和绿点不显示 |

**加权综合完成度：约 45%**


## ✅ 已完成功能

### 基础框架与界面
- PySide6 桌面应用
- 左侧视频列表 + 右侧主工作区
- 视频扫描：Z:\ 目录
- 视频信息显示：时长、大小
- 分段导航：A/B/C/D/E 五分区切换
- 网格密度切换：9/12/16/25 张布局
- 分段状态标记：✓/★/▼

### 截图生成与显示
- 异步 FFmpeg 提取关键帧
- 截图自动裁剪片头片尾
- 截图网格自适应显示
- 时间戳显示
- 截图序号显示
- 选中状态：蓝色圆点
- 锁定状态：🔒 标记

### 收藏管理
- 收藏/取消收藏选中截图
- 左侧面板显示收藏总数
- 分段按钮显示 ★ 标记
- 查看收藏弹窗

### 锁定功能
- 锁定/解锁选中截图
- 刷新未锁定
- 全部重抽

### 导出功能
- 导出选中截图到 StillPic/
- 导出后绿点标记

### 交互操作
- 单击：选中/取消选中
- 双击：放大预览
- 全选/取消全选


## 🚧 未完成功能

### 🔴 高优先级
- 收藏弹窗中 ⭐ 不显示
- 收藏弹窗中绿色圆点不显示
- `_restore_favorites_to_screenshots()` 匹配精度问题（0.5秒阈值太宽松）

### 🟡 中优先级
- SQLite 持久化完善
- Zoom 精修恢复

### 🟢 低优先级
- 右侧预览面板
- 搜索/导入视频
- 清理缓存


## ⚠️ 已知问题

1. **收藏匹配精度问题**：`_restore_favorites_to_screenshots()` 使用 0.5 秒阈值匹配，导致截图时间与收藏时间相差 0.1-0.5 秒时仍然匹配成功，错误地将非收藏截图标记为收藏。
2. **收藏弹窗不显示 ⭐**：`FavImageLabel` 缺少 `set_favorite()` 调用。
3. **收藏弹窗不显示绿色圆点**：`FavImageLabel` 的绿点绘制位置不对。
4. **`_save_state_to_db()` 删除收藏**：增量更新逻辑会删除不在当前网格中的收藏。


## 📝 当前调试状态（2026-07-12）

### 问题现象
- 主界面 9 张截图全部显示 ⭐（错误）
- 收藏弹窗只有时间戳，没有 ⭐ 和绿色圆点

### 已确认
- `_restore_favorites_from_db()` 正确读取了 4 条收藏
- `_refresh_grid()` 中 `label.set_favorite()` 被调用

### 待确认
- `_restore_favorites_to_screenshots()` 的匹配逻辑是否正确
- 0.5 秒阈值是否导致错误匹配

### 下一步
1. 执行 5 个调试修改
2. 运行程序，收集日志
3. 对比收藏时间列表和截图时间列表


## 🛠️ 技术栈

| 组件 | 版本 |
|------|------|
| Python | 3.13 |
| GUI 框架 | PySide6 6.11.1 |
| 视频处理 | FFmpeg / FFprobe |
| 异步框架 | asyncio + QEventLoop |
| 数据库 | SQLite |


## 📌 开发协作规则

### 代码提供方式
- **小修改（≤3处）：** 提供"修改1/2/3"格式，标注查找起始语句和结束语句
- **大修改（>3处）：** 提供完整文件代码

### 改错规则
- 明确的报错代码（Traceback）：直接修复，提供完整代码
- 无明确报错代码：先确认现象，再提供代码

---

**最后更新：** 2026-07-12

# 📋 CoverPicker 项目进度日志

## 🏷️ 当前版本信息
- **版本号：** v1.0.0-stable
- **版本名称：** 核心交互稳定版
- **发布日期：** 2026-07-12
- **状态：** ⚠️ 存在收藏弹窗绿点不显示问题（数据流已验证，UI层待排查）
- **对应 PRODUCT.md 版本：** v4.0


## 📊 整体完成度评估

| 功能模块 | 权重 | 完成度 | 说明 |
|---------|------|--------|------|
| 视频分区浏览 | 8% | 85% | 自动分段、切换正常 |
| Grid 候选浏览 | 10% | 90% | 密度切换、截图显示正常 |
| 收藏管理 | 10% | 80% | 收藏池正常，恢复匹配精度已优化 |
| 锁定功能 | 8% | 95% | 锁定/解锁正常 |
| 导出功能 | 10% | 40% | 导出正常，状态同步有 bug |
| 收藏弹窗 | 15% | 60% | 数据显示正常，但星星和绿点不显示 |

**加权综合完成度：约 50%**


## ✅ 已完成功能

### 基础框架与界面
- PySide6 桌面应用
- 左侧视频列表 + 右侧主工作区
- 视频扫描：Z:\ 目录
- 视频信息显示：时长、大小
- 分段导航：A/B/C/D/E 五分区切换
- 网格密度切换：9/12/16/25 张布局
- 分段状态标记：✓/★/▼

### 截图生成与显示
- 异步 FFmpeg 提取关键帧
- 截图自动裁剪片头片尾
- 截图网格自适应显示
- 时间戳显示
- 截图序号显示
- 选中状态：蓝色圆点
- 锁定状态：🔒 标记

### 收藏管理
- 收藏/取消收藏选中截图
- 左侧面板显示收藏总数
- 分段按钮显示 ★ 标记
- 查看收藏弹窗
- 数据库持久化（收藏 + 导出状态）
- 收藏恢复匹配精度优化（0.1 秒阈值）

### 锁定功能
- 锁定/解锁选中截图
- 刷新未锁定
- 全部重抽

### 导出功能
- 导出选中截图到 StillPic/
- 导出后绿点标记（主界面正常）

### 交互操作
- 单击：选中/取消选中
- 双击：放大预览
- 全选/取消全选


## 🚧 未完成功能

### 🔴 高优先级（当前排查中）
- 收藏弹窗中 ⭐ 不显示
- 收藏弹窗中绿色圆点不显示

### 🟡 中优先级
- 收藏弹窗导出后状态同步

### 🟢 低优先级
- 右侧预览面板
- 搜索/导入视频
- 清理缓存


## ⚠️ 已知问题

1. **收藏弹窗星星不显示**：`FavImageLabel` 的 `paintEvent` 中星星绘制条件为 `if self.is_favorite:`，但 `self.is_favorite` 可能未被正确设置。
2. **收藏弹窗绿色圆点不显示**：数据流已验证 `exported=True` 正确传递到 `img_label.set_exported()`，但 `paintEvent` 中绿点未显示，疑似 `logger` 在 `FavImageLabel` 类中不可用或绘制位置被覆盖。
3. **主界面星星显示正常**：9 张图中只有匹配到的 2 张显示星星，逻辑正确。


## 📝 当前调试状态（2026-07-12 22:25）

### 已验证的数据流
数据库 is_exported=1
↓
_restore_favorites_from_db() → self.favorites (exported=True) ✅
↓
_restore_favorites_to_screenshots() → item['exported']=True ✅
↓
FavoritesDialog.load_favorites() → exported_val=True ✅
↓
img_label.set_exported(exported_val) → 调用成功 ✅
↓
FavImageLabel.set_exported() → ❓ 内部 logger.debug 未输出

text

### 待确认
- `FavImageLabel.set_exported()` 中的 `logger.debug` 为何不输出
- `paintEvent` 中 `self.is_exported` 的实际值
- 绿点绘制位置是否正确

### 下一步
1. 将 `logger.debug` 改为 `logger.info` 或 `print` 确认方法是否执行
2. 在 `paintEvent` 中添加日志确认 `self.is_exported` 值
3. 确认绿点绘制位置是否正确


## 🛠️ 技术栈

| 组件 | 版本 |
|------|------|
| Python | 3.13 |
| GUI 框架 | PySide6 6.11.1 |
| 视频处理 | FFmpeg / FFprobe |
| 异步框架 | asyncio + QEventLoop |
| 数据库 | SQLite |


## 📌 开发协作规则

### 代码提供方式
- **小修改（≤3处）：** 提供"修改1/2/3"格式，标注查找起始语句和结束语句
- **大修改（>3处）：** 提供完整文件代码

### 改错规则
- 明确的报错代码（Traceback）：直接修复，提供完整代码
- 无明确报错代码：先确认现象，再提供代码


## 📝 开发日志（2026-07-12）

### 今日进展
- ✅ 修复 `_save_state_to_db()` 删除收藏逻辑
- ✅ 优化收藏恢复匹配精度（0.5 秒 → 0.1 秒）
- ✅ 修复主界面星星显示逻辑（只显示真正收藏的）
- ✅ 验证收藏弹窗数据流（exported=True 正确传递）
- ⚠️ 收藏弹窗绿点仍不显示，待排查 UI 层

### 经验教训
- 数据流验证要分阶段：数据库 → 内存 → UI
- 日志输出要逐层确认，不能跳跃
- `logger.debug` 可能因日志级别不输出，需用 `logger.info` 或 `print` 验证

---

**最后更新：** 2026-07-12 22:25