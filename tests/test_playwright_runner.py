from harness.skills.playwright_runner.playwright_runner import PlaywrightRunner

def test_is_html_true():
    runner = PlaywrightRunner()
    assert runner._is_html("<!DOCTYPE html><html><body></body></html>") is True

def test_is_html_false():
    runner = PlaywrightRunner()
    assert runner._is_html("from fastapi import FastAPI\n") is False

def test_returns_required_keys():
    runner = PlaywrightRunner()
    code = "<!DOCTYPE html><html><head><title>T</title></head><body></body></html>"
    tests = (
        "from playwright.sync_api import Page\nimport os\n"
        "def test_title(page: Page):\n"
        "    p = os.path.join(os.path.dirname(__file__), 'solution.html')\n"
        "    page.goto(f'file://{p}')\n"
        "    assert page.title() == 'T'\n"
    )
    result = runner.run(code, tests)
    assert "success" in result and "output" in result

def test_passing_html():
    runner = PlaywrightRunner()
    code = "<!DOCTYPE html><html><head><title>Hi</title></head><body><p id='msg'>Hello</p></body></html>"
    tests = (
        "from playwright.sync_api import Page\nimport os\n"
        "def test_msg(page: Page):\n"
        "    p = os.path.join(os.path.dirname(__file__), 'solution.html')\n"
        "    page.goto(f'file://{p}')\n"
        "    assert page.locator('#msg').text_content() == 'Hello'\n"
    )
    result = runner.run(code, tests)
    assert result["success"] is True

def test_failing_html():
    runner = PlaywrightRunner()
    code = "<!DOCTYPE html><html><head><title>Hi</title></head><body><p id='msg'>Hello</p></body></html>"
    tests = (
        "from playwright.sync_api import Page\nimport os\n"
        "def test_msg(page: Page):\n"
        "    p = os.path.join(os.path.dirname(__file__), 'solution.html')\n"
        "    page.goto(f'file://{p}')\n"
        "    assert page.locator('#msg').text_content() == 'Wrong'\n"
    )
    result = runner.run(code, tests)
    assert result["success"] is False
