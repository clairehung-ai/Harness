### Task 1: Project Scaffold + Config + State

**Files:**
- Create: `harness/__init__.py`
- Create: `harness/config.py`
- Create: `harness/state.py`
- Create: `harness/agents/__init__.py`
- Create: `harness/sandbox/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_state.py`
- Create: `requirements.txt`

**Interfaces:**
- Produces: `HarnessState`, `Task`, `TaskResult` TypedDicts; `MAX_ROUNDS`, `MODEL`, `SANDBOX_TIMEOUT` from config

- [ ] **Step 1: Create requirements.txt**

```
langgraph>=0.2
langchain-openai>=0.1
openai>=1.0
pytest>=8.0
```

- [ ] **Step 2: Write failing test**

Create `tests/test_state.py`:

```python
from harness.state import HarnessState, Task, TaskResult

def test_task_has_required_fields():
    task: Task = {
        "id": 1,
        "task_description": "do something",
        "dependencies": [],
        "expected_output": "a function",
        "test_cases": [{"input": "x", "expected": "y"}]
    }
    assert task["id"] == 1

def test_task_result_has_required_fields():
    result: TaskResult = {
        "task_id": 1, "code": "def foo(): pass",
        "tests": "def test_foo(): pass",
        "passed": True, "rating": 5, "feedback": "ok"
    }
    assert result["passed"] is True

def test_harness_state_shape():
    state: HarnessState = {
        "input": "build a calculator",
        "overall_goal": "build a calculator",
        "tasks": [], "current_task_index": 0,
        "completed_steps_summary": "",
        "current_code": "", "current_tests": "",
        "evaluator_feedback": "", "passed": False,
        "round": 0, "task_results": []
    }
    assert state["current_task_index"] == 0
```

- [ ] **Step 3: Run test - verify it fails**

```
pytest tests/test_state.py -v
```

Expected: ImportError (module not found)

- [ ] **Step 4: Create scaffold files**

`harness/__init__.py` — empty  
`harness/agents/__init__.py` — empty  
`harness/sandbox/__init__.py` — empty  
`tests/__init__.py` — empty

`harness/config.py`:
```python
MAX_ROUNDS: int = 3
MODEL: str = "gpt-4o"
SANDBOX_TIMEOUT: int = 10
```

`harness/state.py`:
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
    test_cases: list[TestCase]

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
```

- [ ] **Step 5: Run test - verify it passes**

```
pytest tests/test_state.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```
git init
git add .
git commit -m "feat: project scaffold, config, and state types"
```

---


