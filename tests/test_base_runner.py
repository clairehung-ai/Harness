from harness.skills.base_runner import detect_test_type, BaseRunner
import pytest

def test_detect_unit_default():
    assert detect_test_type("def add(a, b):\n    return a + b\n") == "unit"

def test_detect_api_fastapi():
    assert detect_test_type("from fastapi import FastAPI\napp = FastAPI()\n") == "api"

def test_detect_api_flask():
    assert detect_test_type("from flask import Flask\napp = Flask(__name__)\n") == "api"

def test_detect_integration_sqlite():
    assert detect_test_type("import sqlite3\nimport os\ndef save(): pass\n") == "integration"

def test_detect_integration_file_io():
    assert detect_test_type("import csv\nimport os\ndef read(path):\n    with open(path) as f: pass\n") == "integration"

def test_detect_playwright():
    assert detect_test_type("from playwright.sync_api import Page\n") == "e2e_ui"

def test_detect_priority_playwright_over_api():
    assert detect_test_type("from playwright.sync_api import Page\nfrom fastapi import FastAPI\n") == "e2e_ui"

def test_base_runner_is_abstract():
    with pytest.raises(TypeError):
        BaseRunner()
