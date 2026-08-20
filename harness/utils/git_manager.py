# harness/utils/git_manager.py
import os
import re
import shutil
import subprocess
import time

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
    if os.environ.get("HARNESS_GIT_ENABLED", "true").lower() == "false":
        return False
    if _is_git_repo(project_path):
        return True

    ok, out = _run_git(["init"], cwd=project_path)
    if not ok:
        print(f"⚠️  git init failed: {out}")
        return False

    # 設定 initial branch 名稱為 main
    _run_git(["symbolic-ref", "HEAD", "refs/heads/main"], cwd=project_path)

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


def _unique_branch(project_path: str, base_branch: str) -> str:
    """若 base_branch 已存在，加 -2, -3 ... 後綴直到找到可用名稱。"""
    ok, out = _run_git(["branch", "--list", base_branch], cwd=project_path)
    if ok and out.strip():
        # 已存在，找下一個可用編號
        for i in range(2, 100):
            candidate = f"{base_branch}-{i}"
            ok2, out2 = _run_git(["branch", "--list", candidate], cwd=project_path)
            if ok2 and not out2.strip():
                return candidate
    return base_branch


def setup_git_worktree(project_path: str, user_input: str) -> dict:
    """
    1. git init（若需要）
    2. 從 user_input 產生 slug
    3. git worktree add <worktrees_dir>/<slug> -b run/<slug>
    回傳 {"branch": str, "worktree_path": str, "success": bool}
    """
    if os.environ.get("HARNESS_GIT_ENABLED", "true").lower() == "false":
        return {"branch": None, "worktree_path": None, "success": False}
    failure = {"branch": None, "worktree_path": None, "success": False}

    if not git_init_if_needed(project_path):
        return failure

    slug = slugify(user_input)
    base_branch = f"run/{slug}"
    branch = _unique_branch(project_path, base_branch)

    # worktree 目錄：與 project 同層，名稱為 <project_dirname>-worktrees/<slug>
    project_parent = os.path.dirname(os.path.abspath(project_path))
    project_dirname = os.path.basename(os.path.abspath(project_path))
    worktrees_root = os.path.join(project_parent, f"{project_dirname}-worktrees")
    # Extract just the suffix number from branch for dedup paths
    if branch == base_branch:
        wt_dirname = slug
    else:
        # branch is like "run/asset-inventory-2", slug is "asset-inventory"
        # We want dir name to be "asset-inventory-2"
        suffix = branch[len(base_branch):]  # e.g. "-2"
        wt_dirname = slug + suffix
    worktree_path = os.path.join(worktrees_root, wt_dirname)

    os.makedirs(worktrees_root, exist_ok=True)

    ok, out = _run_git(
        ["worktree", "add", worktree_path, "-b", branch],
        cwd=project_path,
    )
    if not ok:
        print(f"⚠️  git worktree add failed: {out}")
        return failure

    # 把 project_path 的檔案複製進 worktree（覆蓋）
    for item in os.listdir(project_path):
        if item == ".git":
            continue
        src = os.path.join(project_path, item)
        dst = os.path.join(worktree_path, item)
        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # 在 worktree 裡 commit
    _run_git(["add", "."], cwd=worktree_path)
    _run_git(
        ["commit", "-m", f"feat: harness run — {slug}"],
        cwd=worktree_path,
    )

    print(f"✅ git worktree created: {worktree_path}  (branch: {branch})")
    return {"branch": branch, "worktree_path": worktree_path, "success": True}
