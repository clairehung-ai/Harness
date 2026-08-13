# 多檔案管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 Harness 支援多檔案輸出，每個 task 指定 output_filename，sandbox 執行時把所有已完成的代碼檔案都帶進 tempdir，讓跨模組 import 可以正常運作。

**Architecture:** Task 新增 output_filename 欄位；completed_code key 改為 filename；BaseRunner.run() 新增 completed_code 和 output_filename 參數；evaluator 和 red_light_check 傳入這兩個參數。

**Tech Stack:** Python 3.11+, LangGraph, pytest

**Working directory:** D:\projects\Harness\.worktrees\feat-multi-file
**Git branch:** feat/multi-file

## Global Constraints

- Python >= 3.11
- output_filename 預設值："solution.py"
- completed_code key 格式：filename 字串（例如 "models.py"）
- BaseRunner.run() 新簽名：run(code, tests, completed_code=None, output_filename="solution.py") -> dict
- 當前代碼用 output_filename 寫入 tempdir（不固定 solution.py）
- completed_code 的所有檔案用原始 filename 寫入 tempdir
- test_solution.py 固定名稱
- 所有修改的代碼有對應測試

---

## File Map

```
harness/state.py                          MODIFY
harness/graph.py                          MODIFY
harness/skills/base_runner.py             MODIFY
harness/skills/pytest_runner/pytest_runner.py   MODIFY
harness/skills/playwright_runner/playwright_runner.py  MODIFY
harness/agents/evaluator.py               MODIFY
harness/agents/generator.py               MODIFY
harness/prompts/planner.md                MODIFY
harness/prompts/test_writer.md            MODIFY
harness/prompts/code_writer.md            MODIFY

tests/test_state.py                       MODIFY
tests/test_graph.py                       MODIFY
tests/test_base_runner.py                 MODIFY
tests/test_pytest_runner.py               MODIFY
tests/test_playwright_runner.py           MODIFY
tests/test_evaluator.py                   MODIFY
tests/test_generator.py                   MODIFY
tests/test_smoke.py                       MODIFY
```

---

### Task 1: state + graph — output_filename 欄位 + completed_code key 改為 filename

**Files:**
- Modify: `harness/state.py`
- Modify: `harness/graph.py`
- Modify: `tests/test_state.py`
- Modify: `tests/test_graph.py`
- Modify: `tests/test_smoke.py`

**Interfaces:**
- Produces:
  - `Task` TypedDict 新增 `output_filename: str`
  - `advance_task` 用 `task["output_filename"]` 作為 `completed_code` key
  - `make_state()` 和 `make_tdd_state()` fixture 更新

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_state.py` 新增：

```python
def test_task_has_output_filename():
    task: Task = {
        "id": 1,
        "task_description": "build User model",
        "dependencies": [],
        "expected_output": "models.py with User class",
        "output_filename": "models.py",
        "test_cases": [{"input": "User('alice')", "expected": "User object"}],
        "test_type": "unit"
    }
    assert task["output_filename"] == "models.py"
```

在 `tests/test_graph.py` 新增：

```python
def test_advance_task_uses_output_filename_as_completed_code_key():
    """advance_task 應用 output_filename 作為 completed_code 的 key"""
    state = make_tdd_state(current_task_index=0, passed=True)
    state["tasks"][0]["output_filename"] = "models.py"
    state["current_code"] = "class User:\n    def __init__(self, name): self.name = name\n"
    result = advance_task(state)
    assert "models.py" in result["completed_code"]
    assert "class User" in result["completed_code"]["models.py"]
    assert "1" not in result["completed_code"]  # 舊的 task_id key 不應存在
```

- [ ] **Step 2: 執行測試 — 確認失敗**

```
python -m pytest tests/test_state.py::test_task_has_output_filename tests/test_graph.py::test_advance_task_uses_output_filename_as_completed_code_key -v
```

Expected: KeyError 或 AssertionError

- [ ] **Step 3: 更新 harness/state.py**

```python
from typing import TypedDict

class TestCase(TypedDict):
    input: str
    expected: str

class Task(TypedDict):
    id: int
    task_description: str
    dependencies: list[int]
    expected_output: str
    output_filename: str   # 新增：例如 "models.py"、"api.py"、"solution.py"
    test_cases: list[TestCase]
    test_type: str  # "unit" | "api" | "integration" | "e2e_ui" | "auto"

class TaskResult(TypedDict):
    task_id: int
    code: str
    tests: str
    passed: bool
    rating: int
    feedback: str

class HarnessState(TypedDict):
    input: str
    overall_goal: str
    tasks: list[Task]
    current_task_index: int
    completed_steps_summary: str
    current_code: str
    current_tests: str
    evaluator_feedback: str
    passed: bool
    round: int
    task_results: list[TaskResult]
    tdd_phase: str
    red_light_round: int
    completed_code: dict  # {filename: code_str}，key 為檔名
```

- [ ] **Step 4: 更新 harness/graph.py 的 advance_task**

將 `new_completed_code[str(task["id"])]` 改為 `new_completed_code[task["output_filename"]]`：

```python
def advance_task(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    status = "PASSED" if state["passed"] else "FORCED"
    summary = f"{state['completed_steps_summary']}\n- Task {task['id']}: {task['task_description']} [{status}]".strip()
    result: TaskResult = {
        "task_id": task["id"], "code": state["current_code"],
        "tests": state["current_tests"], "passed": state["passed"],
        "rating": 0, "feedback": state["evaluator_feedback"],
    }
    new_completed_code = dict(state["completed_code"])
    new_completed_code[task["output_filename"]] = state["current_code"]
    return {
        "current_task_index": state["current_task_index"] + 1,
        "round": 0, "evaluator_feedback": "",
        "current_code": "", "current_tests": "",
        "passed": False, "completed_steps_summary": summary,
        "task_results": list(state["task_results"]) + [result],
        "tdd_phase": "write_tests",
        "red_light_round": 0,
        "completed_code": new_completed_code,
    }
```

- [ ] **Step 5: 更新所有 test fixtures**

在 `tests/test_graph.py` 的 `make_state()` base dict，Tasks 陣列裡的 task 物件加入 `"output_filename": "solution.py"`：

```python
def make_state(**kwargs):
    base: HarnessState = {
        ...
        "tasks": [
            {"id": 1, "task_description": "implement add", "dependencies": [],
             "expected_output": "add fn", "output_filename": "solution.py",
             "test_cases": [{"input": "1,2", "expected": "3"}], "test_type": "unit"},
            {"id": 2, "task_description": "implement sub", "dependencies": [1],
             "expected_output": "sub fn", "output_filename": "solution.py",
             "test_cases": [{"input": "3,1", "expected": "2"}], "test_type": "unit"},
        ],
        ...
    }
```

在 `tests/test_state.py` 的 `test_task_has_required_fields` 加入 `"output_filename": "solution.py"`。

在 `tests/test_smoke.py` 的 `MOCK_PLANNER` JSON 加入 `"output_filename":"solution.py"`。

- [ ] **Step 6: 執行測試 — 確認通過**

```
python -m pytest tests/test_state.py tests/test_graph.py tests/test_smoke.py -v
```

Expected: 全部通過

- [ ] **Step 7: Commit**

```
git -C "D:\projects\Harness\.worktrees\feat-multi-file" add harness/state.py harness/graph.py tests/test_state.py tests/test_graph.py tests/test_smoke.py
git -C "D:\projects\Harness\.worktrees\feat-multi-file" commit -m "feat: Task 新增 output_filename，advance_task 用 filename 作為 completed_code key"
```

---

### Task 2: BaseRunner + PytestRunner + PlaywrightRunner — 多檔案寫入

**Files:**
- Modify: `harness/skills/base_runner.py`
- Modify: `harness/skills/pytest_runner/pytest_runner.py`
- Modify: `harness/skills/playwright_runner/playwright_runner.py`
- Modify: `tests/test_base_runner.py`
- Modify: `tests/test_pytest_runner.py`

**Interfaces:**
- Consumes: nothing from Task 1 directly
- Produces:
  - `BaseRunner.run(code, tests, completed_code=None, output_filename="solution.py") -> dict`
  - `PytestRunner.run(...)` — 寫入 completed_code 所有檔案 + output_filename 代碼
  - `PlaywrightRunner.run(...)` — 同上（HTML 用 output_filename）

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_pytest_runner.py` 新增：

```python
def test_completed_code_files_available_in_sandbox():
    """completed_code 的檔案應在 tempdir 中可被 import"""
    runner = PytestRunner(mode="integration")
    # models.py 是已完成的代碼
    completed = {"models.py": "class User:\n    def __init__(self, name):\n        self.name = name\n"}
    # 當前代碼是 services.py，import models
    code = "from models import User\ndef get_user(name):\n    return User(name)\n"
    tests = (
        "from solution import get_user\n"
        "def test_get_user():\n"
        "    user = get_user('alice')\n"
        "    assert user.name == 'alice'\n"
    )
    result = runner.run(code, tests, completed_code=completed, output_filename="solution.py")
    assert result["success"] is True

def test_output_filename_used_for_current_code():
    """output_filename 決定當前代碼寫入的檔名"""
    runner = PytestRunner(mode="unit")
    code = "class Foo:\n    pass\n"
    tests = "from mymodule import Foo\ndef test_foo():\n    assert Foo() is not None\n"
    result = runner.run(code, tests, output_filename="mymodule.py")
    assert result["success"] is True
```

在 `tests/test_base_runner.py` 新增：

```python
def test_base_runner_run_signature_accepts_completed_code_and_output_filename():
    """BaseRunner.run() 簽名接受 completed_code 和 output_filename 參數"""
    import inspect
    from harness.skills.base_runner import BaseRunner
    sig = inspect.signature(BaseRunner.run)
    params = list(sig.parameters.keys())
    assert "completed_code" in params
    assert "output_filename" in params
```

- [ ] **Step 2: 執行測試 — 確認失敗**

```
python -m pytest tests/test_pytest_runner.py::test_completed_code_files_available_in_sandbox tests/test_base_runner.py::test_base_runner_run_signature_accepts_completed_code_and_output_filename -v
```

Expected: FAIL

- [ ] **Step 3: 更新 harness/skills/base_runner.py**

更新 `BaseRunner.run()` 抽象方法簽名：

```python
from abc import ABC, abstractmethod


class BaseRunner(ABC):
    """所有測試 Skill Runner 的抽象基底類別。"""

    @abstractmethod
    def run(self, code: str, tests: str, completed_code: dict = None, output_filename: str = "solution.py") -> dict:
        """
        執行測試並回傳結果。

        Args:
            code: Generator 產出的實作代碼字串
            tests: Generator 產出的測試程式字串
            completed_code: 已完成 task 的代碼 {filename: code_str}，執行前全部寫入 tempdir
            output_filename: 當前代碼寫入的檔名，預設 "solution.py"

        Returns:
            dict with keys:
                success (bool): 測試是否全部通過
                output (str): 測試執行的完整輸出（stdout + stderr）
        """
        ...
```

- [ ] **Step 4: 更新 harness/skills/pytest_runner/pytest_runner.py**

```python
import subprocess, tempfile, os, sys
from harness.skills.base_runner import BaseRunner
from harness.config import SANDBOX_TIMEOUT


class PytestRunner(BaseRunner):
    """pytest Skill Runner，支援 unit / api / integration 三種模式。"""

    VALID_MODES = ("unit", "api", "integration")

    def __init__(self, mode: str = "unit"):
        if mode not in self.VALID_MODES:
            raise ValueError(f"不支援的模式：{mode}，合法值為 {self.VALID_MODES}")
        self.mode = mode

    def run(self, code: str, tests: str, completed_code: dict = None, output_filename: str = "solution.py") -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. 寫入所有已完成的檔案
            for filename, file_code in (completed_code or {}).items():
                with open(os.path.join(tmpdir, filename), "w", encoding="utf-8") as f:
                    f.write(file_code)
            # 2. 寫入當前代碼（用 output_filename）
            with open(os.path.join(tmpdir, output_filename), "w", encoding="utf-8") as f:
                f.write(code)
            # 3. 寫入測試
            with open(os.path.join(tmpdir, "test_solution.py"), "w", encoding="utf-8") as f:
                f.write(tests)
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "test_solution.py", "-v", "--tb=short"],
                    capture_output=True, text=True,
                    timeout=SANDBOX_TIMEOUT, cwd=tmpdir,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
            except subprocess.TimeoutExpired:
                return {"success": False, "output": "timeout: 測試執行超過時間限制"}
            except Exception as e:
                return {"success": False, "output": f"runner 錯誤: {e}"}
```

- [ ] **Step 5: 更新 harness/skills/playwright_runner/playwright_runner.py**

更新 `run()` 簽名和寫入邏輯：

```python
def run(self, code: str, tests: str, completed_code: dict = None, output_filename: str = "solution.html") -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. 寫入所有已完成的檔案
        for filename, file_code in (completed_code or {}).items():
            with open(os.path.join(tmpdir, filename), "w", encoding="utf-8") as f:
                f.write(file_code)
        # 2. 寫入當前代碼（HTML 或 Python）
        actual_filename = output_filename if output_filename else (
            "solution.html" if self._is_html(code) else "solution.py"
        )
        with open(os.path.join(tmpdir, actual_filename), "w", encoding="utf-8") as f:
            f.write(code)
        # 3. 寫入測試
        with open(os.path.join(tmpdir, "test_solution.py"), "w", encoding="utf-8") as f:
            f.write(tests)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "test_solution.py", "-v", "--tb=short", "--browser", "chromium"],
                capture_output=True, text=True,
                timeout=SANDBOX_TIMEOUT * 3,
                cwd=tmpdir,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "timeout: Playwright 測試超過時間限制"}
        except Exception as e:
            return {"success": False, "output": f"playwright runner 錯誤: {e}"}
```

- [ ] **Step 6: 執行測試 — 確認通過**

```
python -m pytest tests/test_base_runner.py tests/test_pytest_runner.py -v
```

Expected: 全部通過（含新增的 2 個）

- [ ] **Step 7: Commit**

```
git -C "D:\projects\Harness\.worktrees\feat-multi-file" add harness/skills/ tests/test_base_runner.py tests/test_pytest_runner.py
git -C "D:\projects\Harness\.worktrees\feat-multi-file" commit -m "feat: BaseRunner/PytestRunner/PlaywrightRunner 支援多檔案寫入"
```

---

### Task 3: evaluator + generator — 傳入新參數

**Files:**
- Modify: `harness/agents/evaluator.py`
- Modify: `harness/agents/generator.py`
- Modify: `tests/test_evaluator.py`
- Modify: `tests/test_generator.py`

**Interfaces:**
- Consumes:
  - `BaseRunner.run(code, tests, completed_code, output_filename)` from Task 2
  - `Task["output_filename"]` from Task 1
  - `HarnessState["completed_code"]` (existing)
- Produces:
  - `evaluator_node` 傳入 `completed_code` 和 `output_filename` 給 runner
  - `red_light_check_node` 傳入 `completed_code` 和 `output_filename` 給 runner

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_evaluator.py` 新增：

```python
def test_evaluator_passes_completed_code_to_runner():
    """evaluator 應把 completed_code 和 output_filename 傳給 runner"""
    from unittest.mock import MagicMock
    state = make_state()
    state["tasks"][0]["output_filename"] = "services.py"
    state["completed_code"] = {"models.py": "class User: pass"}
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}
    with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
        with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
            evaluator_node(state)
    call_kwargs = mock_runner.run.call_args
    assert call_kwargs.kwargs.get("completed_code") == {"models.py": "class User: pass"} or \
           (len(call_kwargs.args) >= 3 and call_kwargs.args[2] == {"models.py": "class User: pass"})
```

在 `tests/test_generator.py` 新增：

```python
def test_red_light_check_passes_completed_code_to_runner():
    """red_light_check 應把 completed_code 和 output_filename 傳給 runner"""
    from unittest.mock import MagicMock
    state = make_state()
    state["tasks"][0]["output_filename"] = "services.py"
    state["current_tests"] = "from solution import f\ndef test_f(): assert f()==1\n"
    state["completed_code"] = {"models.py": "class User: pass"}
    state["red_light_round"] = 0
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": False, "output": "ImportError"}
    with patch("harness.agents.generator.get_runner", return_value=mock_runner):
        red_light_check_node(state)
    call_kwargs = mock_runner.run.call_args
    assert call_kwargs.kwargs.get("completed_code") == {"models.py": "class User: pass"} or \
           (len(call_kwargs.args) >= 3 and call_kwargs.args[2] == {"models.py": "class User: pass"})
```

- [ ] **Step 2: 執行測試 — 確認失敗**

```
python -m pytest tests/test_evaluator.py::test_evaluator_passes_completed_code_to_runner tests/test_generator.py::test_red_light_check_passes_completed_code_to_runner -v
```

Expected: FAIL（runner.run 未收到 completed_code）

- [ ] **Step 3: 更新 harness/agents/evaluator.py**

更新 `evaluator_node` 中 runner.run() 的呼叫：

```python
def evaluator_node(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]

    test_type = task.get("test_type", "auto")
    if test_type == "auto":
        test_type = detect_test_type(state["current_code"])

    runner = get_runner(test_type)
    run_result = runner.run(
        state["current_code"],
        state["current_tests"],
        completed_code=state.get("completed_code", {}),
        output_filename=task.get("output_filename", "solution.py"),
    )
    test_passed = run_result["success"]
    test_output = run_result["output"]

    prompt = (
        _load_prompt()
        .replace("{{task_description}}", task["task_description"])
        .replace("{{test_result}}", "passed" if test_passed else "failed")
        .replace("{{test_output}}", test_output[:2000])
        .replace("{{code}}", state["current_code"])
    )
    raw = call_llm(prompt).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]

    try:
        eval_result = json.loads(raw.strip())
    except json.JSONDecodeError:
        eval_result = {"is_success": False, "rating": 1, "feedback": f"LLM returned unparseable JSON: {raw[:200]}"}

    passed = test_passed and eval_result.get("is_success", False)
    feedback = eval_result.get("feedback", "")
    if not test_passed:
        feedback = f"Tests failed: {test_output[:500]}\n{feedback}"

    return {"passed": passed, "evaluator_feedback": feedback, "round": state["round"] + 1}
```

- [ ] **Step 4: 更新 harness/agents/generator.py 的 red_light_check_node**

更新 runner.run() 呼叫：

```python
def red_light_check_node(state: HarnessState) -> dict:
    """驗證 test_writer 產出的測試是否為「正確的紅燈」。不呼叫 LLM。"""
    task = state["tasks"][state["current_task_index"]]
    test_type = task.get("test_type", "auto")
    if test_type == "auto":
        test_type = detect_test_type(state["current_tests"])

    runner = get_runner(test_type)
    run_result = runner.run(
        code="",
        tests=state["current_tests"],
        completed_code=state.get("completed_code", {}),
        output_filename=task.get("output_filename", "solution.py"),
    )
    output = run_result["output"]

    if "SyntaxError" in output:
        return {
            "red_light_round": state["red_light_round"] + 1,
            "evaluator_feedback": f"測試程式有語法錯誤，請修正：{output[:500]}",
        }
    elif run_result["success"]:
        return {
            "tdd_phase": "write_code",
            "red_light_round": 0,
            "evaluator_feedback": "⚠️ 警告：測試在沒有實作代碼的情況下全部通過，測試可能太弱。",
        }
    else:
        return {
            "tdd_phase": "write_code",
            "red_light_round": 0,
            "evaluator_feedback": "",
        }
```

- [ ] **Step 5: 執行測試**

```
python -m pytest tests/test_evaluator.py tests/test_generator.py -v
```

Expected: 全部通過

- [ ] **Step 6: Commit**

```
git -C "D:\projects\Harness\.worktrees\feat-multi-file" add harness/agents/evaluator.py harness/agents/generator.py tests/test_evaluator.py tests/test_generator.py
git -C "D:\projects\Harness\.worktrees\feat-multi-file" commit -m "feat: evaluator 和 red_light_check 傳入 completed_code 和 output_filename 給 runner"
```

---

### Task 4: prompts 更新 + smoke test + 全套驗證

**Files:**
- Modify: `harness/prompts/planner.md`
- Modify: `harness/prompts/test_writer.md`
- Modify: `harness/prompts/code_writer.md`
- Modify: `tests/test_smoke.py`

- [ ] **Step 1: 更新 harness/prompts/planner.md**

在欄位表格中，在 `test_cases` 行之後加入 `output_filename` 行：

```
| `output_filename` | str | ✓ | 輸出檔名。決定代碼寫入哪個檔案，讓跨模組 import 正常運作。預設 `"solution.py"` |
```

在 `test_type 判斷規則` 區塊之後，新增 `output_filename 判斷規則`：

```markdown
### output_filename 判斷規則

| 任務特徵 | 填入值 |
|---------|-------|
| 單一函式、工具類、計算邏輯 | `"solution.py"` |
| 資料模型、資料結構定義（dataclass、TypedDict） | `"models.py"` |
| 業務邏輯、服務層、資料庫操作 | `"services.py"` |
| API endpoints（FastAPI / Flask） | `"api.py"` |
| HTML 頁面、前端 UI | `"solution.html"` |
| 工具函式庫 | `"utils.py"` |
| 不確定或獨立任務 | `"solution.py"`（預設） |
```

並更新完整範例的 JSON，加入 `"output_filename": "solution.py"`。

- [ ] **Step 2: 更新 harness/prompts/test_writer.md**

在輸入變數表格新增 `{{output_filename}}` 行：

```
| `{{output_filename}}` | Planner | 當前 task 代碼會寫入的檔名，測試應從這個模組匯入 |
```

在「測試格式規範」區塊前新增說明：

```markdown
## 重要：import 路徑說明

- **當前 task 的代碼** 寫入 `{{output_filename}}`，測試匯入時用去掉 .py 的模組名
  - 例如：output_filename = "services.py" → `from services import get_user`
  - 例如：output_filename = "solution.py" → `from solution import add`
- **已完成 task 的代碼** 可直接 import（檔案已在 sandbox 中）
  - 例如：`from models import User`（若 Task 1 的 output_filename = "models.py"）
```

在 prompt 的輸入區塊加入 `{{output_filename}}` 填充位：

```
**輸出檔名：** {{output_filename}}
```

- [ ] **Step 3: 更新 harness/prompts/code_writer.md**

在輸入變數表格新增 `{{output_filename}}` 行：

```
| `{{output_filename}}` | Planner | 當前 task 代碼會寫入的檔名 |
```

在「已產出的代碼」區塊說明更新，加入 import 路徑說明。

在 prompt 的輸入區塊加入 `{{output_filename}}` 填充位：

```
**輸出檔名：** {{output_filename}}（你的代碼將寫入這個檔案）
```

- [ ] **Step 4: 更新 harness/agents/generator.py — test_writer_node 和 code_writer_node 注入 output_filename**

在 `test_writer_node` 加入 `.replace("{{output_filename}}", task.get("output_filename", "solution.py"))`：

```python
def test_writer_node(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    prompt = (
        _load_test_writer_prompt()
        .replace("{{overall_goal}}", state["overall_goal"])
        .replace("{{task_description}}", task["task_description"])
        .replace("{{expected_output}}", task["expected_output"])
        .replace("{{test_cases}}", json.dumps(task["test_cases"], indent=2))
        .replace("{{test_type}}", task.get("test_type", "unit"))
        .replace("{{output_filename}}", task.get("output_filename", "solution.py"))
        .replace("{{red_light_feedback}}", state["evaluator_feedback"] or "None")
    )
    raw = call_test_writer_llm(prompt)
    tests = _extract_block(raw, "tests")
    return {
        "current_tests": tests,
        "current_code": "",
        "tdd_phase": "write_tests",
        "passed": False,
    }
```

在 `code_writer_node` 加入 `.replace("{{output_filename}}", task.get("output_filename", "solution.py"))`：

```python
def code_writer_node(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    prompt = (
        _load_code_writer_prompt()
        .replace("{{overall_goal}}", state["overall_goal"])
        .replace("{{completed_steps_summary}}", state["completed_steps_summary"] or "None")
        .replace("{{task_description}}", task["task_description"])
        .replace("{{expected_output}}", task["expected_output"])
        .replace("{{test_type}}", task.get("test_type", "unit"))
        .replace("{{output_filename}}", task.get("output_filename", "solution.py"))
        .replace("{{current_tests}}", state["current_tests"])
        .replace("{{completed_code}}", _format_completed_code(state.get("completed_code", {})))
        .replace("{{evaluator_feedback}}", state["evaluator_feedback"] or "None")
    )
    raw = call_code_writer_llm(prompt)
    code = _extract_block(raw, "implementation")
    return {
        "current_code": code,
        "tdd_phase": "write_code",
    }
```

- [ ] **Step 5: 執行完整測試套件**

```
python -m pytest tests/ --ignore=tests/test_playwright_runner.py --ignore=tests/test_pytest_runner.py --ignore=tests/test_runner.py -v --tb=short
```

Expected: 全部通過

- [ ] **Step 6: Commit**

```
git -C "D:\projects\Harness\.worktrees\feat-multi-file" add harness/prompts/ harness/agents/generator.py
git -C "D:\projects\Harness\.worktrees\feat-multi-file" commit -m "feat: prompts 新增 output_filename 說明和 import 路徑指引"
```

---

## Summary

| Task | 產出 |
|------|------|
| 1 | Task 新增 output_filename，advance_task 用 filename 作為 key |
| 2 | BaseRunner/PytestRunner/PlaywrightRunner 支援多檔案寫入 |
| 3 | evaluator + red_light_check 傳入 completed_code + output_filename |
| 4 | prompts 更新，test_writer/code_writer 注入 output_filename |
