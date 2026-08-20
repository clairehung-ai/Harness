"""
harness/github_runner.py — GitHub Actions 觸發入口。

從環境變數讀取 Issue 資訊，呼叫 run_harness()，
push branch，開 PR，在 Issue 留言。

環境變數：
  ISSUE_TITLE     — Issue 標題
  ISSUE_BODY      — Issue 內容
  ISSUE_NUMBER    — Issue 編號（整數）
  REPO            — GitHub repo（格式：owner/repo）
  EXPORT_DIR      — 生成專案的輸出路徑
"""
import os
import subprocess
import sys


def get_issue_input() -> dict:
    """從環境變數讀取 Issue 資訊。

    Returns:
        {"title": str, "body": str, "number": int, "repo": str, "export_dir": str}

    Raises:
        EnvironmentError: 若缺少必要環境變數
    """
    missing = []
    for key in ["ISSUE_TITLE", "ISSUE_NUMBER", "REPO", "EXPORT_DIR"]:
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

    return {
        "title": os.environ["ISSUE_TITLE"],
        "body": os.environ.get("ISSUE_BODY", ""),
        "number": int(os.environ["ISSUE_NUMBER"]),
        "repo": os.environ["REPO"],
        "export_dir": os.environ["EXPORT_DIR"],
    }


def build_user_input(title: str, body: str) -> str:
    """合併 Issue title 和 body 為 run_harness 的 user_input。

    若 body 為空，只回傳 title。
    否則回傳 "title\n\nbody"。
    """
    if not body.strip():
        return title
    return f"{title}\n\n{body}"
