# -*- coding: utf-8 -*-
"""
一键上传到 GitHub（无需安装 Git）
=================================================
本机没有安装 git，脚本使用 dulwich（纯 Python 的 Git 实现）完成
init → add → commit → push 全流程。

用法（首次上传）：
    D:\\Anaconda3\\python.exe upload_github.py --repo https://github.com/用户名/仓库名.git --token ghp_你的Token

用法（之后更新代码）：
    D:\\Anaconda3\\python.exe upload_github.py --repo https://github.com/用户名/仓库名.git --token ghp_你的Token

说明：
- 仓库必须先在 GitHub 网页上创建好（空仓库，不要勾选 README / .gitignore）
- Token 在 GitHub → Settings → Developer settings → Personal access tokens 生成，
  勾选 repo 权限即可；用完可随时撤销
- 也可以把 Token 放进环境变量 GITHUB_TOKEN，避免明文出现在命令行
"""

import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dulwich import porcelain
from dulwich.repo import Repo

BRANCH = "main"


def ensure_repo(path: str) -> Repo:
    """确保目录是一个 Git 仓库，并把默认分支设为 main。"""
    if not os.path.isdir(os.path.join(path, ".git")):
        porcelain.init(path)
        print("[1/4] 已初始化 Git 仓库")
    else:
        print("[1/4] 仓库已存在，跳过初始化")

    repo = Repo(path)
    # 尚无任何提交时，把 HEAD 指向 main（否则默认可能是 master）
    try:
        repo[repo.head()]
    except KeyError:
        repo.refs.set_symbolic_ref(b"HEAD", b"refs/heads/" + BRANCH.encode())
    return repo


def stage_and_commit(repo: Repo, message: str, author: str):
    """暂存全部文件并提交（自动遵循 .gitignore）。"""
    ignored = porcelain.add(repo.path)
    if ignored:
        print(f"[2/4] 已暂存文件，按 .gitignore 忽略了 {len(ignored)} 个文件/目录")
    else:
        print("[2/4] 已暂存文件")

    status = porcelain.status(repo)
    has_head = True
    try:
        repo[repo.head()]
    except KeyError:
        has_head = False

    has_changes = any(status.staged.values()) or status.unstaged or status.untracked
    if has_head and not has_changes:
        print("[3/4] 没有新的改动，跳过提交")
        return False

    commit_id = porcelain.commit(
        repo,
        message=message.encode("utf-8"),
        author=author.encode("utf-8"),
        committer=author.encode("utf-8"),
    )
    print(f"[3/4] 已提交：{commit_id.decode()[:8]}  {message}")
    return True


def push(repo: Repo, remote_url: str, token: str):
    """推送到 GitHub。把 token 拼进 URL 完成 HTTPS 认证。"""
    auth_url = remote_url
    if token and remote_url.startswith("https://"):
        auth_url = remote_url.replace("https://", f"https://{token}@", 1)

    print("[4/4] 正在推送到 GitHub ……")
    refspec = f"refs/heads/{BRANCH}:refs/heads/{BRANCH}".encode()
    result = porcelain.push(repo, auth_url, refspec)
    for ref in result:
        print(f"    {ref.decode(errors='ignore')}")
    print("\n✅ 上传完成，请到 GitHub 仓库页面刷新查看")


def main():
    parser = argparse.ArgumentParser(description="一键上传项目到 GitHub（无需安装 Git）")
    parser.add_argument("--repo", default="", help="GitHub 仓库地址，如 https://github.com/用户名/仓库名.git")
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN", ""),
                        help="GitHub Personal Access Token（也可用环境变量 GITHUB_TOKEN）")
    parser.add_argument("--name", default="Liu", help="提交者姓名")
    parser.add_argument("--email", default="liu@example.com", help="提交者邮箱")
    parser.add_argument("--message", default="feat: LLM 提示注入攻防实验平台", help="提交信息")
    parser.add_argument("--interactive", action="store_true", help="交互式输入仓库地址与 Token（供 bat 双击使用）")
    args = parser.parse_args()

    repo_url = (args.repo or "").strip().strip('"').strip("'")
    token = (args.token or "").strip().strip('"').strip("'")

    # 交互模式：缺什么就问什么，输错/空值会重新提示，不会一闪而过
    if args.interactive:
        if not repo_url:
            print("提示：示例格式  https://github.com/你的用户名/仓库名.git")
            repo_url = input("请输入 GitHub 仓库地址：").strip().strip('"').strip("'")
        if not token:
            print("提示：Token 形如 ghp_xxxxxxxx，粘贴后按回车（窗口内点鼠标右键即粘贴）")
            token = input("请输入 GitHub Token：").strip().strip('"').strip("'")

    if not repo_url:
        print("❌ 缺少仓库地址：请用 --repo 传入，或双击 bat 交互输入")
        sys.exit(1)
    while not token:
        print("❌ Token 不能为空，请重新输入：")
        token = input("请输入 GitHub Token：").strip().strip('"').strip("'")

    print(f"仓库：{repo_url}")
    print(f"Token：{token[:4]}****{token[-4:]}（已隐藏中间部分）")

    project_dir = os.path.dirname(os.path.abspath(__file__))
    author = f"{args.name} <{args.email}>"

    repo = ensure_repo(project_dir)
    stage_and_commit(repo, args.message, author)
    try:
        push(repo, repo_url.rstrip("/"), token)
    except Exception as e:
        print(f"\n❌ 推送失败：{type(e).__name__}: {e}")
        print("常见原因：")
        print("  1) Token 无效或已过期（重新生成，勾选 repo 权限）")
        print("  2) 仓库地址写错，或仓库不存在 / 不是空仓库")
        print("  3) 网络无法访问 github.com（可尝试开启代理）")
        print("  4) Token 没有该仓库的写权限")
        sys.exit(1)


if __name__ == "__main__":
    main()
