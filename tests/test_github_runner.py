# tests/test_github_runner.py
import os
import pytest
from unittest.mock import patch, MagicMock
import subprocess
from harness.github_runner import (
    get_issue_input, build_user_input,
    push_branch, create_pr, comment_on_issue,
    main,
)


def test_get_issue_input_reads_env_vars():
    env = {
        "ISSUE_TITLE": "新增資產匯出功能",
        "ISSUE_BODY": "需要可以匯出 CSV",
        "ISSUE_NUMBER": "42",
        "REPO": "clairehung-ai/Asset_inventory",
        "EXPORT_DIR": "D:/projects/Asset_inventory",
    }
    with patch.dict(os.environ, env, clear=False):
        result = get_issue_input()
    assert result["title"] == "新增資產匯出功能"
    assert result["body"] == "需要可以匯出 CSV"
    assert result["number"] == 42
    assert result["repo"] == "clairehung-ai/Asset_inventory"
    assert result["export_dir"] == "D:/projects/Asset_inventory"


def test_get_issue_input_missing_env_raises():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(EnvironmentError):
            get_issue_input()


def test_build_user_input_combines_title_and_body():
    result = build_user_input("新增匯出功能", "需要匯出 CSV 格式")
    assert "新增匯出功能" in result
    assert "需要匯出 CSV 格式" in result


def test_build_user_input_empty_body():
    result = build_user_input("新增匯出功能", "")
    assert result == "新增匯出功能"


def test_push_branch_calls_git_push():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = push_branch("D:/projects/Asset_inventory", "run/asset-inventory")
    assert result is True
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "push" in call_args
    assert "run/asset-inventory" in call_args


def test_push_branch_returns_false_on_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = push_branch("D:/projects/Asset_inventory", "run/asset-inventory")
    assert result is False


def test_create_pr_returns_url_on_success():
    pr_url = "https://github.com/clairehung-ai/Asset_inventory/pull/1"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=pr_url, stderr="")
        result = create_pr(
            repo="clairehung-ai/Asset_inventory",
            branch="run/asset-inventory",
            title="新增匯出功能",
            issue_number=42,
        )
    assert result == pr_url


def test_create_pr_returns_none_on_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = create_pr(
            repo="clairehung-ai/Asset_inventory",
            branch="run/asset-inventory",
            title="新增匯出功能",
            issue_number=42,
        )
    assert result is None


def test_comment_on_issue_calls_gh():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = comment_on_issue(
            repo="clairehung-ai/Asset_inventory",
            issue_number=42,
            message="PR 已建立：https://github.com/..."
        )
    assert result is True
    call_args = mock_run.call_args[0][0]
    assert "issue" in call_args
    assert "comment" in call_args


def test_main_success_flow(tmp_path):
    """main() 成功時：run_harness → push → PR → Issue 留言含 PR URL"""
    env = {
        "ISSUE_TITLE": "新增匯出功能",
        "ISSUE_BODY": "匯出 CSV",
        "ISSUE_NUMBER": "42",
        "REPO": "clairehung-ai/Asset_inventory",
        "EXPORT_DIR": str(tmp_path),
    }
    mock_result = {
        "task_results": [],
        "total": 1, "passed": 1, "forced": 0, "failed": 0,
        "run_log_path": str(tmp_path / "run.jsonl"),
        "project_path": str(tmp_path),
        "git_branch": "run/asset-inventory",
        "git_worktree_path": str(tmp_path / "worktrees" / "asset-inventory"),
    }
    with patch.dict(os.environ, env, clear=False), \
         patch("harness.github_runner.run_harness", return_value=mock_result) as mock_rh, \
         patch("harness.github_runner.push_branch", return_value=True), \
         patch("harness.github_runner.create_pr", return_value="https://github.com/clairehung-ai/Asset_inventory/pull/1"), \
         patch("harness.github_runner.comment_on_issue", return_value=True) as mock_comment:
        main()
    mock_rh.assert_called_once()
    # Issue 留言應包含 PR URL
    call_args = mock_comment.call_args
    comment_msg = call_args[1].get("message") or call_args[0][2]
    assert "https://github.com/clairehung-ai/Asset_inventory/pull/1" in comment_msg


def test_main_harness_failure_comments_on_issue(tmp_path):
    """main() 當 run_harness 拋出例外時，在 Issue 留言說明失敗"""
    env = {
        "ISSUE_TITLE": "新增匯出功能",
        "ISSUE_BODY": "",
        "ISSUE_NUMBER": "42",
        "REPO": "clairehung-ai/Asset_inventory",
        "EXPORT_DIR": str(tmp_path),
    }
    with patch.dict(os.environ, env, clear=False), \
         patch("harness.github_runner.run_harness", side_effect=RuntimeError("LLM timeout")), \
         patch("harness.github_runner.comment_on_issue", return_value=True) as mock_comment:
        main()
    call_args = mock_comment.call_args
    comment_msg = call_args[1].get("message") or call_args[0][2]
    assert any(word in comment_msg for word in ["失敗", "error", "LLM timeout", "failed", "Error"])
