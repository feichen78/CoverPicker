1. 打开项目（每天第一步）

打开 PowerShell

进入项目：

cd C:\Personal\CoverPicker


2. 激活 Python 虚拟环境

什么时候用？

准备运行 Python、安装库、运行 main.py 前。

提示符应该变成：

(.venv) PS C:\Personal\CoverPicker>

输入：

.\.venv\Scripts\Activate.ps1

成功以后：

(.venv) PS C:\Personal\CoverPicker>

如果没有看到：

(.venv)

说明没有激活成功。

3. 退出虚拟环境

什么时候用？

不用了。

输入：

deactivate

提示符会恢复：

PS C:\Personal\CoverPicker>
4. 运行程序

什么时候？

每次测试。

提示符必须：

(.venv)

输入：

python main.py
5. 安装新的 Python 库

例如：

安装 OpenCV

提示符必须：

(.venv)

输入：

pip install opencv-python

安装 Pillow：

pip install pillow
6. 保存依赖

什么时候？

安装了新的库以后。

输入：

pip freeze > requirements.txt

以后换电脑：

只需要：

pip install -r requirements.txt
7. 查看 Git 状态

什么时候？

提交以前。

输入：

git status
8. 提交到 Git

什么时候？

一个稳定版本完成。

输入：

git add .

然后：

git commit -m "v3.0 Segment Browser"

然后：

git push
9. 查看最近提交

输入：

git log --oneline
10. 从 GitHub 下载最新版本（新电脑）

进入准备放项目的位置：

cd C:\Personal

下载：

git clone https://github.com/feichen78/CoverPicker.git
11. 新电脑第一次运行

进入：

cd CoverPicker

建立环境：

python -m venv .venv

激活：

.\.venv\Scripts\Activate.ps1

安装依赖：

pip install -r requirements.txt

运行：

python main.py
12. 更新本地代码（另一台电脑开发后）

进入项目：

cd C:\Personal\CoverPicker

拉取最新：

git pull
13. 打开 VS Code

进入项目目录：

code .

会自动打开整个项目。

（第一次如果提示找不到 code 命令，我们再配置一次即可。）

14. 创建发布版本（以后）

例如：

git tag v3.0
git push origin v3.0

✅ 一、正确 Git 上传流程（标准安全版）

在项目根目录执行：

① 查看状态（必须先做）
git status

确认：

docs/ 新文件在不在
有没有 cache / 临时文件被误加入
② 添加文件
git add .
③ 提交（非常重要，不能跳）
git commit -m "Add v3.1 documentation (ENGINE_SPEC + ROADMAP + runtime flow)"
④ 推送到 GitHub
git push origin main
⚠️ 二、你可能会遇到的3个问题（提前帮你避坑）
❗问题1：没有 commit 会 push 失败

如果你只做：

git add .
git push

👉 会报错或什么都没上传

✔ 必须有 commit

❗问题2：main / master 分支问题

如果报错：

error: src refspec main does not match

说明你是 master 分支：

git push origin master
❗问题3：GitHub没登录 / token问题

如果提示：

authentication failed
password rejected

👉 你需要 GitHub Token（不是密码）


🚀 四、建议你加一个“版本标签”（很重要）

上传完成后建议加：

git tag v3.1-docs
git push origin v3.1-docs

👉 这样以后可以：

回到这个设计版本
不怕后面代码乱掉
📌 五、一句话总结

你现在正确流程是：

git status
git add .
git commit -m "v3.1 docs"
git push origin main

开发备忘卡

打开项目
cd C:\Personal\CoverPicker
激活环境
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& .\.venv\Scripts\Activate.ps1)

看到：

(.venv) PS C:\Personal\CoverPicker>

说明成功。

运行程序
python main.py
安装新库
pip install 包名

安装完成后，如果项目需要记录依赖：

pip freeze > requirements.txt
Git 开发流程（以后固定）

完成一个功能后：

git status
git add .
git commit -m "完成内容"
git push

例如：

git commit -m "Add core models for v3.2 foundation"

当你换电脑时：

git clone ...

↓

py -3.13 -m venv .venv

↓

激活：

.\.venv\Scripts\Activate.ps1

↓

安装项目依赖：

python -m pip install -r requirements.txt

这样所有依赖都会装好。

任何电脑：

只需要：

python -m pip install -r requirements.txt

整个开发环境 5 分钟就能恢复。

以后无论换电脑还是新成员加入，都按这个流程：

git clone

↓

创建 .venv

↓

激活 .venv

↓

python -m pip install -r requirements.txt

↓

python main.py

不再手动安装 PySide6、Pillow 等任何单独的库。

# 先删除原有origin
git remote remove origin
# 添加镜像远程仓库
git remote add origin https://kgithub.com/feichen78/CoverPicker.git
# 推送
git push -u origin main


不要激活虚拟环境，直接在当前 CMD 中运行（系统 Python 环境）
cd C:\Personal\CoverPicker
pyinstaller --onedir --name CoverPicker --windowed --paths .venv\Lib\site-packages --collect-all PySide6 --collect-all shiboken6 --hidden-import qasync --hidden-import src.database --hidden-import src.video_scanner --hidden-import src.controllers.segment_controller --noconfirm main.py

在项目根目录（C:\Personal\CoverPicker\）打开PowerShell，执行以下命令删除所有 __pycache__ 目录：

powershell
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force