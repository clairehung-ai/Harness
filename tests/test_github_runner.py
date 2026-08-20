# tests/test_github_runner.py
import os
import pytest
from unittest.mock import patch


def test_get_issue_input_reads_env_vars():
    env = {
        "ISSUE_TITLE": "新增資產匯出功能",
        "ISSUE_BODY": "需要可以匯出 CSV",
        "ISSUE_NUMBER": "42",
        "REPO": "clairehung-ai/Asset_inventory",
        "EXPORT_DIR": "D:/projects/Asset_inventory",
    }
    with patch.dict(os.environ, env, clear=False):
        from harness.github_runner import get_issue_input
        result = get_issue_input()
    assert result["title"] == "新增資產匯出功能"
    assert result["body"] == "需要可以匯出 CSV"
    assert result["number"] == 42
    assert result["repo"] == "clairehung-ai/Asset_inventory"
    assert result["export_dir"] == "D:/projects/Asset_inventory"


def test_get_issue_input_missing_env_raises():
    with patch.dict(os.environ, {}, clear=True):
        for k in ["ISSUE_TITLE", "ISSUE_BODY", "ISSUE_NUMBER", "REPO", "EXPORT_DIR"]:
            os.environ.pop(k, None)
        from harness.github_runner import get_issue_input
        with pytest.raises(EnvironmentError):
            get_issue_input()


def test_build_user_input_combines_title_and_body():
    from harness.github_runner import build_user_input
    result = build_user_input("新增匯出功能", "需要匯出 CSV 格式")
    assert "新增匯出功能" in result
    assert "需要匯出 CSV 格式" in result


def test_build_user_input_empty_body():
    from harness.github_runner import build_user_input
    result = build_user_input("新增匯出功能", "")
    assert result == "新增匯出功能"
