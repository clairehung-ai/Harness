# completed_code：code_writer 看到已產出代碼 設計

**日期：** 2026-08-07
**狀態：** 已核准

---

## 概覽

在 `HarnessState` 新增 `completed_code: dict` 欄位，讓 `code_writer_node` 在撰寫代碼時能看到前面所有 task 已產出的代碼，避免重複實作並保持介面一致性。

---

## 問題

目前 `code_writer_node` 只接收 `completed_steps_summary`（文字摘要），無法看到前面 task 的實際代碼。Task N 的 code_writer 可能重複實作 Task N-1 已有的函式，或使用不一致的介面。

---

## 設計

### State 變更

```python
class HarnessState(TypedDict):
    # ... 現有欄位不變 ...
    completed_code: dict  # {"1": "def add(a,b): ...", "2": "class Foo: ..."}
```

- key：`str(task_id)`
- value：該 task 的完整實作代碼字串

---

### advance_task 變更

```python
def advance_task(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    # 新增：把當前代碼存入 completed_code
    new_completed_code = dict(state["completed_code"])
    new_completed_code[str(task["id"])] = state["current_code"]
    return {
        ...
        "completed_code": new_completed_code,
    }
```

---

### code_writer_node 變更

新增 `{{completed_code}}` 注入：

```python
def _format_completed_code(completed_code: dict) -> str:
    if not completed_code:
        return "None"
    parts = []
    for task_id, code in completed_code.items():
        parts.append(f"### Task {task_id} 的代碼\n```python\n{code}\n```")
    return "\n\n".join(parts)

def code_writer_node(state: HarnessState) -> dict:
    ...
    prompt = (
        _load_code_writer_prompt()
        ...
        .replace("{{completed_code}}", _format_completed_code(state["completed_code"]))
    )
```

---

### code_writer.md prompt 變更

在「已完成步驟」之後新增區塊：

```
## 已產出的代碼（前面 task 的實作）

{{completed_code}}

閱讀以上代碼，了解：
- 已有哪些函式可以直接呼叫，不需重複實作
- 現有的介面和命名風格，保持一致
```

---

### main.py 變更

initial state 加入 `completed_code: {}`：

```python
initial: HarnessState = {
    ...
    "completed_code": {},
}
```

---

## 不在本 spec 範圍內

- 多檔案管理（completed_code 目前只存單一字串）
- code_writer 主動查詢特定 task 的代碼
- completed_code 的大小限制或 token 管理

---

## 成功標準

- `HarnessState` 有 `completed_code: dict` 欄位
- `advance_task` 將當前代碼存入 `completed_code`
- `code_writer_node` 注入 `{{completed_code}}` 到 prompt
- `code_writer.md` 有 `{{completed_code}}` 區塊說明
- `main.py` initial state 有 `completed_code: {}`
- 所有相關測試更新通過
