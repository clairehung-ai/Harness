from harness.skills.pytest_runner.pytest_runner import PytestRunner

def test_unit_passing():
    runner = PytestRunner(mode="unit")
    code = "def add(a, b):\n    return a + b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = runner.run(code, tests)
    assert result["success"] is True

def test_unit_failing():
    runner = PytestRunner(mode="unit")
    code = "def add(a, b):\n    return a - b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = runner.run(code, tests)
    assert result["success"] is False

def test_api_mode_fastapi():
    runner = PytestRunner(mode="api")
    code = (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/hello')\n"
        "def hello():\n"
        "    return {'message': 'hello world'}\n"
    )
    tests = (
        "from fastapi.testclient import TestClient\n"
        "from solution import app\n"
        "client = TestClient(app)\n"
        "def test_hello():\n"
        "    r = client.get('/hello')\n"
        "    assert r.status_code == 200\n"
        "    assert r.json() == {'message': 'hello world'}\n"
    )
    result = runner.run(code, tests)
    assert result["success"] is True

def test_integration_file_io():
    runner = PytestRunner(mode="integration")
    code = (
        "import os\n"
        "def write_and_read(path, content):\n"
        "    with open(path, 'w') as f: f.write(content)\n"
        "    with open(path) as f: return f.read()\n"
    )
    tests = (
        "import os\n"
        "from solution import write_and_read\n"
        "def test_write_and_read(tmp_path):\n"
        "    p = str(tmp_path / 'test.txt')\n"
        "    assert write_and_read(p, 'hello') == 'hello'\n"
    )
    result = runner.run(code, tests)
    assert result["success"] is True

def test_syntax_error_returns_failure():
    runner = PytestRunner(mode="unit")
    code = "def add(a, b)\n    return a + b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1,2)==3\n"
    result = runner.run(code, tests)
    assert result["success"] is False

def test_returns_required_keys():
    runner = PytestRunner(mode="unit")
    result = runner.run("def f(): return 1\n", "from solution import f\ndef test_f():\n    assert f()==1\n")
    assert "success" in result and "output" in result
    assert isinstance(result["success"], bool)
    assert isinstance(result["output"], str)

def test_invalid_mode_raises():
    import pytest
    with pytest.raises(ValueError):
        PytestRunner(mode="invalid")
