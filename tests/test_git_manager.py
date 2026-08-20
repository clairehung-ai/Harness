# tests/test_git_manager.py
import os
import pytest
import tempfile
import shutil
from harness.utils.git_manager import slugify, setup_git_worktree, git_init_if_needed

def test_slugify_english():
    assert slugify("asset inventory web system") == "asset-inventory-web-system"

def test_slugify_mixed_chinese_english():
    # 中文字移除，英數保留
    assert slugify("資產清冊 asset inventory") == "asset-inventory"

def test_slugify_pure_chinese_fallback():
    # 全中文 → fallback 不是空字串（有 timestamp）
    result = slugify("資產清冊管理系統")
    assert result.startswith("run-")

def test_slugify_truncates_long_text():
    long_text = "a " * 30  # 60 字元
    result = slugify(long_text)
    assert len(result) <= 60

def test_slugify_strips_special_chars():
    assert slugify("hello! world? foo_bar") == "hello-world-foo-bar"


def test_setup_git_worktree_creates_branch(tmp_path):
    # 建一個有檔案的臨時目錄模擬 project
    (tmp_path / "main.py").write_text("# hello")
    result = setup_git_worktree(str(tmp_path), "asset inventory system")
    assert result["success"] is True
    assert result["branch"] == "run/asset-inventory-system"
    assert os.path.isdir(result["worktree_path"])

def test_setup_git_worktree_deduplicates_branch(tmp_path):
    (tmp_path / "main.py").write_text("# hello")
    r1 = setup_git_worktree(str(tmp_path), "asset inventory")
    r2 = setup_git_worktree(str(tmp_path), "asset inventory")
    assert r1["success"] and r2["success"]
    assert r1["branch"] != r2["branch"]
    # 第二次應該是 run/asset-inventory-2
    assert r2["branch"] == "run/asset-inventory-2"
