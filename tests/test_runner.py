from harness.sandbox.runner import run_tests

def test_passing_code():
    code = "def add(a, b):\n    return a + b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = run_tests(code, tests)
    assert result["success"] is True

def test_failing_code():
    code = "def add(a, b):\n    return a - b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = run_tests(code, tests)
    assert result["success"] is False

def test_syntax_error_code():
    code = "def add(a, b)\n    return a + b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = run_tests(code, tests)
    assert result["success"] is False

def test_timeout_enforced():
    code = "import time\ndef add(a, b):\n    time.sleep(30)\n    return a + b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = run_tests(code, tests)
    assert result["success"] is False
