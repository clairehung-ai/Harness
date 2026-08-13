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

def test_get_runner_unit():
    from harness.skills.pytest_runner.pytest_runner import PytestRunner
    from harness.skills.base_runner import get_runner
    runner = get_runner("unit")
    assert isinstance(runner, PytestRunner)
    assert runner.mode == "unit"

def test_get_runner_api():
    from harness.skills.pytest_runner.pytest_runner import PytestRunner
    from harness.skills.base_runner import get_runner
    runner = get_runner("api")
    assert isinstance(runner, PytestRunner)
    assert runner.mode == "api"

def test_get_runner_integration():
    from harness.skills.pytest_runner.pytest_runner import PytestRunner
    from harness.skills.base_runner import get_runner
    runner = get_runner("integration")
    assert isinstance(runner, PytestRunner)
    assert runner.mode == "integration"

def test_get_runner_e2e_ui():
    from harness.skills.playwright_runner.playwright_runner import PlaywrightRunner
    from harness.skills.base_runner import get_runner
    runner = get_runner("e2e_ui")
    assert isinstance(runner, PlaywrightRunner)

def test_get_runner_unknown_falls_back_to_unit():
    from harness.skills.pytest_runner.pytest_runner import PytestRunner
    from harness.skills.base_runner import get_runner
    runner = get_runner("unknown_type")
    assert isinstance(runner, PytestRunner)
    assert runner.mode == "unit"

def test_get_runner_auto_falls_back_to_unit():
    from harness.skills.pytest_runner.pytest_runner import PytestRunner
    from harness.skills.base_runner import get_runner
    runner = get_runner("auto")
    assert isinstance(runner, PytestRunner)
    assert runner.mode == "unit"

def test_base_runner_run_signature_accepts_completed_code_and_output_filename():
    """BaseRunner.run() 簽名接受 completed_code 和 output_filename 參數"""
    import inspect
    from harness.skills.base_runner import BaseRunner
    sig = inspect.signature(BaseRunner.run)
    params = list(sig.parameters.keys())
    assert "completed_code" in params
    assert "output_filename" in params
