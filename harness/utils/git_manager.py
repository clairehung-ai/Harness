# harness/utils/git_manager.py
import os
import re
import subprocess
import time
from typing import Optional


def slugify(text: str) -> str:
    """從需求文字產生 git branch slug。
    - 取前 50 字元
    - 移除非英數字元，空白換連字號
    - 全中文（無英數）則 fallback 到 run-<timestamp>
    """
    sample = text[:50]
    # 只保留 ASCII 英數與空白
    ascii_only = re.sub(r'[^a-zA-Z0-9 ]', ' ', sample)
    words = ascii_only.lower().split()
    if not words:
        return f"run-{int(time.time())}"
    slug = "-".join(words)
    # 最長 60 字元
    return slug[:60]


def _run_git(args: list[str], cwd: str) -> tuple[bool, str]:
    """執行 git 指令，回傳 (success, output)。"""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def _is_git_repo(path: str) -> bool:
    ok, _ = _run_git(["rev-parse", "--git-dir"], cwd=path)
    return ok


def git_init_if_needed(project_path: str) -> bool:
    """若 project_path 不是 git repo，則 git init + 初始 commit。
    回傳 True 表示 repo 已就緒（新建或原本就有）。
    """
    if _is_git_repo(project_path):
        return True

    ok, out = _run_git(["init"], cwd=project_path)
    if not ok:
        print(f"⚠️  git init failed: {out}")
        return False

    # 設定 initial branch 名稱為 main
    _run_git(["checkout", "-b", "main"], cwd=project_path)

    # 設定最低限度的 git config（避免 CI 環境報錯）
    _run_git(["config", "user.email", "harness@local"], cwd=project_path)
    _run_git(["config", "user.name", "Harness"], cwd=project_path)

    ok, out = _run_git(["add", "."], cwd=project_path)
    if not ok:
        print(f"⚠️  git add failed: {out}")
        return False

    ok, out = _run_git(["commit", "-m", "init: initial project structure from Harness"], cwd=project_path)
    if not ok:
        print(f"⚠️  git commit failed: {out}")
        return False

    print(f"✅ git init + initial commit: {project_path}")
    return True
