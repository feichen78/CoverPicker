CoverPicker 开发命令文档
版本：v3.2
最后更新：2026-07-28

📌 目录
环境准备（新电脑首次）

日常开发（每天第一步）

运行与调试

Python 包管理

Git 基础概念（必读）

Git 常用命令速查

切换分支报错怎么办（必读）

Git 完整工作流

项目构建与发布

VS Code 终端配置

开发备忘卡

1. 环境准备（新电脑首次）
1.1 安装 Python 3.13
从官网下载并安装 Python 3.13，安装时勾选 "Add Python to PATH"。

验证安装：

powershell
python --version
# 应显示：Python 3.13.x
1.2 克隆项目
powershell
cd C:\Personal
git clone https://github.com/feichen78/CoverPicker.git
cd CoverPicker
1.3 创建虚拟环境
powershell
python -m venv .venv
1.4 激活虚拟环境
powershell
.\.venv\Scripts\Activate.ps1
成功后提示符变为：

text
(.venv) PS C:\Personal\CoverPicker>
1.5 安装所有依赖
powershell
pip install -r requirements.txt
1.6 验证运行
powershell
python main.py
1.7 （可选）配置 VS Code
powershell
code .
如果提示找不到 code 命令，在 VS Code 中按 Ctrl+Shift+P，输入 Shell Command: Install 'code' command in PATH。

2. 日常开发（每天第一步）
2.1 打开项目目录
powershell
cd C:\Personal\CoverPicker
2.2 激活虚拟环境
powershell
.\.venv\Scripts\Activate.ps1
如果遇到执行策略报错，使用：

powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
2.3 确认环境
powershell
(.venv) PS C:\Personal\CoverPicker> python --version
# 应显示：Python 3.13.x
2.4 退出虚拟环境
powershell
deactivate
3. 运行与调试
3.1 正常运行（需激活虚拟环境）
powershell
python main.py
3.2 查看日志
日志文件位置：log/CoverPicker_YYYY-MM-DD.log

崩溃报告位置：log/crashes/crash_report_*.txt

3.3 清理 Python 缓存
当 Python 版本更换或包结构变化时，删除 __pycache__（不需要虚拟环境）：

powershell
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
4. Python 包管理
⚠️ 以下所有命令必须在虚拟环境（提示符 (.venv)）下执行。

4.1 安装新包
powershell
pip install 包名
示例：

powershell
pip install opencv-python
pip install pillow
4.2 更新依赖文件
安装新包后，必须更新 requirements.txt：

powershell
pip freeze > requirements.txt
4.3 查看已安装的包
powershell
pip list
4.4 新电脑一键安装所有依赖
powershell
pip install -r requirements.txt
5. Git 基础概念（必读）
5.1 提交（Commit）
是什么：一次快照，记录当前所有文件的完整状态。

为什么重要：每次提交都是一个可回溯的版本点。

示例：

powershell
git commit -m "修复GIF导出bug"
5.2 分支（Branch）
是什么：一条独立的开发线，从主线上分叉出来的“施工便道”。

为什么重要：在不影响主干（main）的前提下开发新功能。

示例：

powershell
# 查看所有本地分支
git branch

# 创建并切换到新分支
git checkout -b v3.3

# 切换到已有分支
git checkout main
5.3 HEAD
是什么：指向当前所在位置的“箭头”。它通常指向一个分支，分支再指向一个提交。

为什么重要：HEAD 决定了您正在查看/修改哪个版本。

示例：

powershell
# 查看 HEAD 指向哪里
git log --oneline -1
# 输出：5c32ed7 (HEAD -> v3.2) 开发命令文档更新
# 表示 HEAD 指向 v3.2 分支的最新提交
5.4 Detached HEAD（悬空 HEAD）
是什么：HEAD 不指向任何分支，而是直接指向某个历史提交。此时任何修改都不会关联到分支上。

危险：如果切换到其他分支，这些修改会丢失（除非创建新分支保存）。

如何进入：

powershell
git checkout 5c32ed7   # ← 执行这个操作 → 进入 Detached HEAD
                       # 此时 Git 会提示 "You are in 'detached HEAD' state..."
如何退出：切换到已有分支：

powershell
git checkout main      # 回到 main 分支
git checkout v3.2      # 回到 v3.2 分支
5.5 origin（远程仓库别名）
是什么：GitHub 服务器的本地代号。origin = https://github.com/feichen78/CoverPicker.git。

为什么重要：不用每次都输完整网址。

查看当前远程仓库：

powershell
git remote -v
5.6 origin/main vs 本地 main
名称	位置	说明
main	您的电脑	本地主干分支
origin/main	GitHub 服务器	远程主干分支
v3.2	您的电脑	本地 v3.2 分支
origin/v3.2	GitHub 服务器	远程 v3.2 分支
重要：origin/main 和本地 main 可能不同步！git fetch 会更新本地的 origin/* 信息。

6. Git 常用命令速查
6.1 查看状态
是什么：查看哪些文件被修改了、哪些在暂存区、当前在哪个分支。

为什么用：提交前必须检查，确保提交正确的内容。

powershell
git status
示例输出：

text
On branch v3.2
Changes not staged for commit:
  modified:   src/controllers/segment_controller.py
Untracked files:
  docs/DEVELOPMENT.md
6.2 添加文件到暂存区
是什么：告诉 Git “我要提交这些文件”。

为什么用：选择性提交，避免把临时文件也提交。

powershell
# 添加单个文件
git add docs/DEVELOPMENT.md

# 添加当前目录所有修改（推荐）
git add .

# 添加所有已跟踪文件的修改（不包含新文件）
git add -u
6.3 提交（创建版本快照）
是什么：把暂存区的文件打包成一个版本快照，永久保存在 Git 历史中。

为什么用：每个可工作的版本都应该提交，方便回溯。

powershell
git commit -m "提交信息（描述本次修改内容）"
示例：

powershell
git commit -m "修复GIF导出时界面卡住的问题"
提交信息格式：

text
类型: 简短描述

- 类型：feat（新功能）/ fix（修复）/ docs（文档）/ refactor（重构）
- 描述：50字以内，中文
提交后输出：

text
[v3.2 5c32ed7] 修复GIF导出时界面卡住的问题
 1 file changed, 15 insertions(+), 3 deletions(-)
⚠️ 注意：[v3.2 5c32ed7] 中的 v3.2 是当前所在分支，5c32ed7 是提交哈希。一定要确认分支名称正确！

6.4 推送（上传到 GitHub）
是什么：把本地分支的提交上传到 GitHub 对应的远程分支。

为什么用：让其他人（或其他电脑）能获取您的代码。

首次推送新分支（设置上游追踪）：

powershell
git push -u origin v3.2
-u 的意思是“设置上游追踪”，以后在这个分支上只需 git push。

如果不确定是否用过 -u，就始终用完整命令：

powershell
git push origin v3.2
推送指定分支到远程指定分支：

powershell
git push origin 本地分支名:远程分支名
示例：

powershell
git push origin v3.2          # 推送本地 v3.2 → 远程 v3.2
git push origin main          # 推送本地 main → 远程 main
常见错误：

powershell
# ❌ 错误：推送了错误的分支
git push origin main    # 如果您在 v3.2 分支上做了修改，这条命令不会推送您的修改！
正确做法：推送当前所在分支：

powershell
git push origin v3.2    # 如果您在 v3.2 分支上
6.5 拉取（下载最新代码并合并）
是什么：从 GitHub 下载最新代码并合并到本地当前分支。

为什么用：在开始工作前，确保本地代码与远程同步。

⚠️ 重要：git pull 只更新当前所在分支。拉取其他分支前，必须先 git checkout 切换到该分支。

powershell
# 先切换到要更新的分支
git checkout v3.2

# 再拉取该分支的更新
git pull origin v3.2
正确流程：

powershell
git checkout v3.2               # 切换到 v3.2
git pull origin v3.2            # 拉取 v3.2 的更新

git checkout v3.0.1             # 切换到 v3.0.1
git pull origin v3.0.1          # 拉取 v3.0.1 的更新
6.6 获取远程更新信息（不合并）
是什么：只下载远程的更新信息到本地的远程跟踪分支（origin/*），不自动合并到本地工作区。

为什么用：想先看看别人做了什么，再决定是否合并。

powershell
git fetch --all
查看下载的信息：

powershell
# 查看远程 main 分支的最新提交
git log origin/main --oneline -5

# 查看远程 v3.2 分支的最新提交
git log origin/v3.2 --oneline -5

# 查看本地与远程的差异
git diff main origin/main
fetch vs pull 对比：

操作	下载数据	合并到工作区	适用场景
git fetch	✅ 是	❌ 否	先查看远程做了什么，再决定是否合并
git pull	✅ 是	✅ 是	直接获取最新代码并合并
6.7 git stash（暂存修改）
是什么：当您有未提交的修改，但需要切换分支时，可以临时把修改“藏起来”，切换完再“取出来”。

为什么用：Git 阻止您在修改未提交时切换分支（会覆盖文件）。stash 是绕过这个限制的干净方式。

powershell
# 查看当前有哪些修改
git status

# 把当前分支的未提交修改暂存起来
git stash

# 现在工作区变干净了，可以安全切换分支
git checkout v3.2

# 切换完成后，把暂存的修改取回来
git stash pop
其他 stash 命令：

powershell
# 查看暂存列表
git stash list

# 应用最近一次暂存（但保留暂存记录）
git stash apply

# 删除最近一次暂存
git stash drop
6.8 查看提交历史
是什么：查看所有提交记录。

powershell
# 简洁模式（一行一个提交）
git log --oneline

# 带图形（显示分支结构）
git log --oneline --graph --all

# 查看最近 3 条
git log --oneline -3
示例输出：

text
5c32ed7 (HEAD -> v3.2) 开发命令文档更新
d104902 (origin/v3.2) 移除GIF文件夹（大文件不上传）
620c395 v3.2
解读：

HEAD -> v3.2 → 当前在 v3.2 分支

origin/v3.2 → 远程 v3.2 分支最新提交（本地缓存，需 git fetch 更新）

如果两者不一致，说明本地比远程领先或落后

git log 输出格式详解（以 git log --oneline -1 为例）：

text
4a1ca14 (HEAD -> v2.5.2, origin/v2.5.2) v2.5.2
部分	含义
4a1ca14	提交哈希（唯一 ID）
(HEAD -> v2.5.2, origin/v2.5.2)	分支信息：当前在本地 v2.5.2，且与远程同步
v2.5.2（括号外）	提交信息（git commit -m 的内容）
6.9 分支操作
powershell
# 查看所有本地分支
git branch

# 查看所有远程分支
git branch -r

# 查看所有分支（本地+远程）
git branch -a

# 创建新分支（不切换）
git branch v3.3

# 创建并切换到新分支
git checkout -b v3.3

# 切换到已有分支
git checkout v3.2

# 删除本地分支（已合并）
git branch -d v3.3

# 删除远程分支
git push origin --delete v3.3
6.10 从标签创建分支
是什么：标签（tag）是某个历史提交的“别名”，常用于标记发布版本。

powershell
# 查看所有标签
git tag

# 从标签创建分支
git checkout -b v2.5.2 v2.5.2

# 推送新分支到远程
git push origin v2.5.2
6.11 创建标签
是什么：给某个提交起一个容易记住的名字（如版本号）。

powershell
# 创建标签
git tag v3.2

# 推送标签到远程
git push origin v3.2

# 一次性推送所有标签
git push --tags
6.12 合并分支
是什么：把一个分支的修改合并到另一个分支。

powershell
# 先切换到目标分支（如 main）
git checkout main

# 拉取最新代码
git pull origin main

# 合并 v3.2 分支
git merge v3.2

# 推送到远程 main
git push origin main
6.13 撤销操作
powershell
# 撤销最近一次提交，保留修改到工作区（文件修改还在）
git reset --soft HEAD^

# 撤销最近一次提交，保留修改到暂存区（默认）
git reset --mixed HEAD^

# 彻底丢弃最近一次提交（危险，不可恢复）
git reset --hard HEAD^

# 安全撤销某次提交（创建一个反向提交）
git revert 5c32ed7
6.14 忽略文件（.gitignore）
是什么：告诉 Git 哪些文件不要跟踪。

powershell
# 添加忽略规则
echo "GIF/" >> .gitignore

# 从 Git 中移除但保留本地文件
git rm -r --cached GIF/
6.15 查看文件差异
powershell
# 查看工作区与暂存区的差异
git diff

# 查看暂存区与最新提交的差异
git diff --staged

# 查看两个分支的差异
git diff main..v3.2
7. 切换分支报错怎么办（必读）
7.1 报错现象
当您执行 git checkout 分支名 时，遇到：

text
error: Your local changes to the following files would be overwritten by checkout:
        docs/DEVELOPMENT.md
Please commit your changes or stash them before you switch branches.
Aborting
7.2 报错原因
您在当前分支上修改了文件（还没提交），想切换到另一个分支。Git 阻止切换，因为新分支可能也有同名文件，切换会覆盖您的修改。

7.3 解决方案（三选一）
场景	解决方案	命令
您想把修改保留到新分支	先暂存，再切换，再恢复	git stash → git checkout v3.2 → git stash pop
您想把修改提交到当前分支，再合并到新分支	在当前分支提交，切换，合并	git add . → git commit -m "xxx" → git checkout v3.2 → git merge v2.5.2
您想丢弃修改（不保留）	直接丢弃	git checkout -- . → git checkout v3.2
7.4 最推荐的方式：stash
powershell
# 1. 查看当前修改
git status

# 2. 暂存修改（藏起来）
git stash

# 3. 切换分支（现在安全了）
git checkout v3.2

# 4. 把修改取回来
git stash pop
8. Git 完整工作流
8.1 日常开发流程
powershell
# 1. 确认当前分支
git branch
# 输出应显示 * v3.2（或您要工作的分支）

# 2. 查看状态
git status

# 3. 添加修改
git add .

# 4. 查看状态（确认添加正确）
git status

# 5. 提交
git commit -m "feat: 添加新功能xxx"

# 6. 推送到远程同名分支
git push origin v3.2
8.2 什么时候需要合并到 main？
场景	是否需要合入 main
日常开发中（还在写代码）	❌ 不需要
新功能开发完成，经过测试，准备发布	✅ 需要
修复了关键 bug，需要让所有用户都能用	✅ 需要
只是实验性功能，不一定最终保留	❌ 不需要
核心原则：main 分支永远是“稳定版本”。只有确定要发布的内容才合并进去。

8.3 合并到 main 流程
powershell
# 1. 切换到 main
git checkout main

# 2. 拉取最新
git pull origin main

# 3. 合并 v3.2
git merge v3.2

# 4. 推送到远程 main
git push origin main

# 5. 切换回开发分支
git checkout v3.2
8.4 新电脑获取代码
powershell
# 1. 克隆仓库
git clone https://github.com/feichen78/CoverPicker.git

# 2. 进入目录
cd CoverPicker

# 3. 查看所有分支
git branch -a

# 4. 切换到需要的分支
git checkout v3.2

# 5. 创建并激活虚拟环境（见第1节）
9. 项目构建与发布
9.1 打包可执行文件（PyInstaller）
在项目根目录执行（不需要激活虚拟环境，使用系统 Python）：

powershell
cd C:\Personal\CoverPicker
pyinstaller --onedir --name CoverPicker --windowed --paths .venv\Lib\site-packages --collect-all PySide6 --collect-all shiboken6 --hidden-import qasync --hidden-import src.database --hidden-import src.video_scanner --hidden-import src.controllers.segment_controller --noconfirm main.py
打包后位置：dist/CoverPicker/

9.2 创建版本标签
powershell
git tag v3.2
git push origin v3.2
10. VS Code 终端配置
10.1 问题描述
在 VS Code 终端中粘贴多行命令时，会出现确认对话框（正常行为），但终端背景变黑（异常行为）。

10.2 解决方案
方案一：粘贴后按 Esc 键

text
粘贴多行命令 → 确认框出现 → 点击“粘贴” → 按 Esc 键 → 退出选择模式，背景恢复正常
方案二：修改 settings.json

按 Ctrl+Shift+P 打开命令面板

输入 Preferences: Open User Settings (JSON) 并回车

在文件中添加以下配置：

json
{
    "terminal.integrated.shellIntegration.enabled": false,
    "terminal.integrated.enableMultiLinePasteWarning": true
}
保存文件（Ctrl+S）

配置说明：

配置项	作用
"terminal.integrated.shellIntegration.enabled": false	禁用 shell integration，粘贴时不会再自动进入选择模式
"terminal.integrated.enableMultiLinePasteWarning": true	保留多行粘贴确认框
11. 开发备忘卡
每天开始
powershell
cd C:\Personal\CoverPicker
.\.venv\Scripts\Activate.ps1
python main.py
提交代码
powershell
git status
git add .
git commit -m "描述本次修改"
git push origin v3.2
切换分支遇到报错（有未提交的修改）
powershell
# 1. 暂存修改
git stash

# 2. 切换分支
git checkout v3.2

# 3. 恢复修改
git stash pop
拉取最新
powershell
# 先切换到目标分支
git checkout v3.2
git pull origin v3.2
切换分支
powershell
git branch          # 查看当前分支
git checkout v3.2   # 切换到 v3.2
查看提交历史
powershell
git log --oneline -5
查看远程更新（不合并）
powershell
git fetch --all
git log origin/v3.2 --oneline -5
📌 常见错误及解决
错误	原因	解决方案
fatal: not a git repository	不在项目根目录	cd C:\Personal\CoverPicker
src refspec main does not match any	分支名错误	检查分支名：git branch
Everything up-to-date	没有新提交需要推送	检查是否已 commit，或推错了分支
Authentication failed	未登录 GitHub	使用 token 登录
Cannot enter into task...	Python asyncio 底层行为	不影响功能，可忽略
No such method	Qt 信号/槽错误	检查方法名是否匹配
Your local changes would be overwritten...	切换分支时有未提交修改	用 git stash 暂存，或提交修改
VS Code 终端粘贴时背景变黑	shell integration 自动选择模式	粘贴后按 Esc，或修改 settings.json（见第10节）
VS Code 找不到 code 命令	PATH 未配置	VS Code 中 Ctrl+Shift+P → Install 'code' command in PATH
最后更新：2026-07-28