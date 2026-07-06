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