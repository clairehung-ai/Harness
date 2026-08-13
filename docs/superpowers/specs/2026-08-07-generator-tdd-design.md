# Generator TDD 改造設計

**日期：** 2026-08-07
**狀態：** 已核准

---

## 概覽

本 spec 描述將 Harness Generator Agent 從「一次產出 code + tests」的模式，改造為符合 TDD 精神的兩階段流程：先由 test_writer skill 產出測試程式，經 red_light_check 驗證紅燈品質後，再由 code_writer skill 產出實作代碼。

---

## 設計目標

1. **Generator 下有兩個 Skill** — test_writer 和 code_writer，各自有 SKILL.md 和 prompt
2. **紅燈品質驗證** — red_light_check 確認測試是「正確的失敗」才進入 code_writer
3. **對稱架構** — Generator Skill 結構與 Evaluator Skill 結構一致
4. **向後相容** — 現有 evaluator、planner、state 欄位盡量不破壞

---

## 目錄結構變更

```
harness/
├── agents/
│   └── generator.py          MODIFY — 新增 test_writer_node、code_writer_node、red_light_check_node
│
├── prompts/
│   ├── generator.md          保留（不刪除，未來可棄用）
│   ├── test_writer.md        CREATE — test_writer skill 的 LLM prompt
│   └── code_writer.md        CREATE — code_writer skill 的 LLM prompt
│
├── skills/
│   ├── test_writer/
│   │   └── SKILL.md          CREATE — 說明 test_writer skill 的規範和使用情境
│   └── code_writer/
│       └── SKILL.md          CREATE — 說明 code_writer skill 的規範和使用情境
│
├── state.py                  MODIFY — HarnessState 新增 tdd_phase、red_light_round
│
└── graph.py                  MODIFY — 新增節點、重接條件邊
```

---

## State 變更

### HarnessState 新增欄位

```python
class HarnessState(TypedDict):
    # ... 現有欄位不變 ...
    tdd_phase: str        # "write_tests" | "write_code"，追蹤目前在哪個 TDD 階段
    red_light_round: int  # test_writer 的重試次數（上限 MAX_RED_LIGHT_ROUNDS = 2）
```

### config.py 新增常數

```python
MAX_RED_LIGHT_ROUNDS: int = 2  # test_writer 最多重試 2 次
```

---

## Skill 規範

### test_writer skill

**位置：** `harness/skills/test_writer/SKILL.md`

**用途：** 根據 Planner 的 task_cases 產出 pytest 測試程式，不產出實作代碼。

**使用情境：**
- 每個 task 的第一步
- 在 code_writer 之前執行
- red_light_check 失敗（SyntaxError）時重試

**輸出格式：** 只有一個 `tests` fenced code block，沒有 `implementation` block

**對應 prompt：** `harness/prompts/test_writer.md`

---

### code_writer skill

**位置：** `harness/skills/code_writer/SKILL.md`

**用途：** 看著已確認的測試程式，產出能讓所有測試通過的實作代碼。

**使用情境：**
- red_light_check 通過（正確紅燈）之後
- Evaluator 評估失敗需要 retry 時

**輸出格式：** 只有一個 `implementation` fenced code block，沒有 `tests` block

**對應 prompt：** `harness/prompts/code_writer.md`

---

## Prompt 規範

### test_writer.md

**輸入變數：**

| 變數 | 來源 | 說明 |
|------|------|------|
| `{{overall_goal}}` | Planner | 整個專案目標 |
| `{{task_description}}` | Planner | 當前任務描述 |
| `{{expected_output}}` | Planner | 預期產出物 |
| `{{test_cases}}` | Planner | 測試案例清單（必須全部覆蓋） |
| `{{test_type}}` | Planner | 決定測試格式（unit/api/integration/e2e_ui） |
| `{{red_light_feedback}}` | red_light_check | 若測試有 SyntaxError，說明問題所在 |

**輸出規範：**
- 只輸出一個 `tests` fenced code block
- 不輸出 `implementation` block
- 不輸出任何說明文字

---

### code_writer.md

**輸入變數：**

| 變數 | 來源 | 說明 |
|------|------|------|
| `{{overall_goal}}` | Planner | 整個專案目標 |
| `{{completed_steps_summary}}` | Orchestrator | 已完成任務摘要 |
| `{{task_description}}` | Planner | 當前任務描述 |
| `{{expected_output}}` | Planner | 預期產出物 |
| `{{test_type}}` | Planner | 測試類型 |
| `{{current_tests}}` | test_writer（已確認） | 已通過紅燈驗證的測試程式 |
| `{{evaluator_feedback}}` | Evaluator（上一輪） | 若有 retry，說明上一輪的問題 |

**輸出規範：**
- 只輸出一個 `implementation` fenced code block
- 不輸出 `tests` block（測試已存在）
- 不輸出任何說明文字

---

## 新的 Graph 流程

```
planner
  │
  ▼
test_writer_node
  產出：current_tests，tdd_phase = "write_tests"
  │
  ▼
red_light_check_node
  執行：runner.run(code="", tests=current_tests)
  判讀 pytest 輸出
  │
  ├── SyntaxError → test_writer_node（重試，red_light_round + 1）
  │   若 red_light_round >= MAX_RED_LIGHT_ROUNDS → 強制進入 code_writer + 警告
  │
  ├── 全部通過（弱測試）→ 記錄警告到 evaluator_feedback + 進入 code_writer
  │
  └── ImportError / AssertionError / ModuleNotFoundError（正確紅燈）
        │
        ▼
      code_writer_node
        產出：current_code，tdd_phase = "write_code"
        │
        ▼
      evaluator_node（正式評估，行為不變）
        │
        ├── pass → advance_task
        └── fail → code_writer_node（retry，受 MAX_ROUNDS 限制）
```

---

## 節點實作規範

### test_writer_node(state) -> dict

```python
{
    "current_tests": str,        # 測試程式
    "current_code": "",          # 清空 code
    "tdd_phase": "write_tests",
    "passed": False,
}
```

### red_light_check_node(state) -> dict

**不呼叫 LLM，純程式邏輯。**

```python
# 執行：空 code + current_tests
run_result = get_runner(test_type).run(code="", tests=state["current_tests"])
output = run_result["output"]

if "SyntaxError" in output:
    return {
        "red_light_round": state["red_light_round"] + 1,
        "evaluator_feedback": f"測試程式有語法錯誤，請修正：{output[:500]}"
    }
elif run_result["success"]:  # 全部通過（弱測試）
    return {
        "tdd_phase": "write_code",
        "red_light_round": 0,
        "evaluator_feedback": "⚠️ 警告：測試在沒有實作代碼的情況下全部通過，測試可能太弱。"
    }
else:  # ImportError / AssertionError = 正確紅燈
    return {
        "tdd_phase": "write_code",
        "red_light_round": 0,
        "evaluator_feedback": "",
    }
```

### route_after_red_light_check(state) -> str

```python
# red_light_round > 0 代表上一次是 SyntaxError 重試
if state["red_light_round"] > 0 and state["red_light_round"] < MAX_RED_LIGHT_ROUNDS:
    return "test_writer"   # SyntaxError，繼續重試
if state["red_light_round"] >= MAX_RED_LIGHT_ROUNDS:
    return "code_writer"   # 超過重試上限，強制通過
return "code_writer"       # 正確紅燈或弱測試警告
```

### code_writer_node(state) -> dict

```python
{
    "current_code": str,         # 實作代碼
    "tdd_phase": "write_code",
}
```

---

## Graph 節點和邊更新

```python
# 新增節點
g.add_node("test_writer", test_writer_node)
g.add_node("red_light_check", red_light_check_node)
g.add_node("code_writer", code_writer_node)

# 移除舊節點
# g.add_node("generator", generator_node)  ← 替換掉

# 新的邊
g.set_entry_point("planner")
g.add_edge("planner", "test_writer")
g.add_edge("test_writer", "red_light_check")
g.add_conditional_edges("red_light_check", route_after_red_light_check,
    {"test_writer": "test_writer", "code_writer": "code_writer"})
g.add_edge("code_writer", "evaluator")
g.add_conditional_edges("evaluator", route_after_evaluator,
    {"advance_task": "advance_task", "code_writer": "code_writer"})
g.add_conditional_edges("advance_task", route_after_advance,
    {"test_writer": "test_writer", END: END})
```

---

## 不在本 spec 範圍內

- generator.md 的棄用處理
- test_writer 和 code_writer 的平行化
- red_light_check 的 LLM 輔助判斷
- 多輪 TDD（同一 task 的多個 red-green 循環）

---

## 成功標準

- `test_writer_node` 只產出 `current_tests`，不產出 `current_code`
- `red_light_check_node` 正確區分 SyntaxError、弱測試、正確紅燈
- `code_writer_node` 只產出 `current_code`，不改動 `current_tests`
- graph 流程：planner → test_writer → red_light_check → code_writer → evaluator → advance_task
- SyntaxError 時 test_writer 重試，最多 MAX_RED_LIGHT_ROUNDS 次
- 弱測試時記錄警告並繼續
- 所有新增節點有對應測試
- smoke test 更新為新的流程

