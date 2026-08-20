# tests/test_git_manager.py
import pytest
from harness.utils.git_manager import slugify

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
