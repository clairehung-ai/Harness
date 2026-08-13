# 多檔案管理設計

**日期：** 2026-08-07
**狀態：** 已核准

---

## 概覽

讓 Harness 能處理「模組之間有 import 關係」的真實專案。Planner 在每個 task 明確指定輸出檔名（`output_filename`），sandbox 執行測試時把所有已完成的代碼檔案都帶進 tempdir，讓 Task N 的測試可以正常 import Task 1..N-1 的代碼。同時將 `completed_code` 的 key 從 `str(task_id)` 改為 `filename`，讓 code_writer 的 LLM 直接知道可以 import 哪個模組。

---

## 問題

目前每個 task 的代碼都寫入同一個 `solution.py`，導致：
1. Task N 覆蓋 Task N-1 的代碼
2. Task N 的測試無法 import Task N-1 的模組
3. 無法處理跨模組的真實專案

---

## 設計決策

1. **`output_filename` 由 Planner 指定**（不讓 Generator 猜），確保行為一致
2. **`completed_code` key 改為 filename**（從 `str(task_id)` 改為 `task["output_filename"]`），讓 LLM 直接看出 import 關係
3. **sandbox 多檔案寫入**：執行測試前先把 `completed_code` 所有檔案寫進 tempdir，再寫當前代碼

---

## 變更清單

```
harness/state.py                MODIFY — Task 新增 output_filename: str
harness/graph.py                MODIFY — advance_task 用 output_filename 作為 completed_code key
harness/agents/generator.py     MODIFY — code_writer_node 和 test_writer_node 注入 output_filename
harness/prompts/code_writer.md  MODIFY — 新增 {{output_filename}} 說明
harness/prompts/test_writer.md  MODIFY — 新增 {{output_filename}} 讓測試知道 import 哪個模組
harness/prompts/planner.md      MODIFY — 新增 output_filename 欄位說明和判斷規則
harness/skills/pytest_runner/pytest_runner.py   MODIFY — run() 接收 completed_code，多檔案寫入
harness/skills/playwright_runner/playwright_runner.py  MODIFY — 同上
harness/skills/base_runner.py   MODIFY — BaseRunner.run() 介面加 completed_code 參數
harness/agents/evaluator.py     MODIFY — 呼叫 runner.run() 時傳入 completed_code
harness/agents/generator.py     MODIFY — red_light_check_node 呼叫 runner.run() 時傳入 completed_code
```

---

## State 變更

### Task TypedDict

```python
class Task(TypedDict):
    id: int
    task_description: str
    dependencies: list[int]
    expected_output: str
    output_filename: str   # 新增：例如 "models.py"、"api.py"、"solution.py"
    test_cases: list[TestCase]
    test_type: str
```

### output_filename 規則

| 任務類型 | output_filename |
|---------|----------------|
| 單一 Python 函式／工具 | `"solution.py"` |
| 特定模組（資料模型） | `"models.py"` |
| 服務層 | `"services.py"` |
| API 層 | `"api.py"` |
| HTML 頁面 | `"solution.html"` |
| 不確定 | `"solution.py"`（預設） |

### completed_code key 改為 filename

```python
# 之前
completed_code = {"1": "class User: ..."}

# 之後
completed_code = {"models.py": "class User: ..."}
```

advance_task 變更：

```python
# 之前
new_completed_code[str(task["id"])] = state["current_code"]

# 之後
new_completed_code[task["output_filename"]] = state["current_code"]
```

---

## BaseRunner 介面變更

```python
class BaseRunner(ABC):
    @abstractmethod
    def run(self, code: str, tests: str, completed_code: dict = None, output_filename: str = "solution.py") -> dict:
        """
        執行測試並回傳結果。

        Args:
            code: 當前 task 的實作代碼
            tests: pytest 測試程式
            completed_code: 已完成 task 的代碼 {filename: code_str}，執行前全部寫入 tempdir
            output_filename: 當前代碼寫入的檔名，預設 "solution.py"

        Returns:
            {"success": bool, "output": str}
        """
        ...
```

---

## PytestRunner 多檔案寫入

```python
def run(self, code: str, tests: str, completed_code: dict = None, output_filename: str = "solution.py") -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. 先寫入所有已完成的檔案（用真實檔名）
        for filename, file_code in (completed_code or {}).items():
            with open(os.path.join(tmpdir, filename), "w", encoding="utf-8") as f:
                f.write(file_code)

        # 2. 寫入當前代碼（用 output_filename）
        with open(os.path.join(tmpdir, output_filename), "w", encoding="utf-8") as f:
            f.write(code)

        # 3. 寫入測試
        with open(os.path.join(tmpdir, "test_solution.py"), "w", encoding="utf-8") as f:
            f.write(tests)

        # 4. 執行 pytest
        ...
```

**注意：** 當前代碼用 `output_filename` 寫入（例如 `services.py`）。
測試程式可以直接 `from services import get_user`，也可以 `from models import User`（已完成的檔案）。
`test_solution.py` 固定用這個名字。

---

## evaluator_node 變更

傳入 `completed_code` 和 `output_filename` 給 runner：

```python
task = state["tasks"][state["current_task_index"]]
run_result = runner.run(
    code=state["current_code"],
    tests=state["current_tests"],
    completed_code=state.get("completed_code", {}),
    output_filename=task.get("output_filename", "solution.py")
)
```

---

## red_light_check_node 變更

同樣傳入 `completed_code` 和 `output_filename`：

```python
run_result = runner.run(
    code="",
    tests=state["current_tests"],
    completed_code=state.get("completed_code", {}),
    output_filename=task.get("output_filename", "solution.py")
)
```

---

## Prompt 變更

### planner.md

欄位表格新增：

```
| `output_filename` | str | ✓ | 輸出檔名，例如 "models.py"、"api.py"、"solution.py"（預設） |
```

判斷規則新增：

```
| 任務特徵 | output_filename |
|---------|----------------|
| 單一函式、工具、計算邏輯 | "solution.py" |
| 資料模型、資料結構定義 | "models.py" |
| 業務邏輯、服務層 | "services.py" |
| API endpoints (FastAPI/Flask) | "api.py" |
| HTML 頁面、前端 UI | "solution.html" |
```

### test_writer.md 和 code_writer.md

新增 `{{output_filename}}` 變數說明，告訴 LLM：
- 當前代碼會寫入哪個檔案
- 測試應該 `from solution import ...`（當前 task）
- 測試可以 `from <filename> import ...`（已完成的 task）

---

## 不在本 spec 範圍內

- 一個 task 產出多個檔案（output_filename 目前只支援單一檔案）
- 依賴順序執行（拓撲排序）
- `output_filename` 衝突檢測（兩個 task 用同一個檔名）

---

## 成功標準

- `Task` TypedDict 有 `output_filename: str`
- `completed_code` key 是 filename（不是 task_id）
- `advance_task` 用 `task["output_filename"]` 作為 key
- `BaseRunner.run()` 接收 `completed_code` 參數
- `PytestRunner.run()` 在執行前把 `completed_code` 所有檔案寫進 tempdir
- `evaluator_node` 和 `red_light_check_node` 傳入 `completed_code`
- `planner.md` 有 `output_filename` 欄位說明和判斷規則
- `test_writer.md` 和 `code_writer.md` 有 `{{output_filename}}` 說明
- 所有測試通過
