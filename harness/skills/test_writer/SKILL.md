# Skill: test_writer

## 用途

根據 Planner 提供的 task_description 和 test_cases，產出完整的 pytest 測試程式。
不產出實作代碼。

## 使用情境

- 每個 task 的 TDD 流程第一步
- 在 code_writer 之前執行
- red_light_check 偵測到 SyntaxError 時重試

## 輸入

- `{{overall_goal}}` — 整個專案目標
- `{{task_description}}` — 當前任務描述
- `{{expected_output}}` — 預期產出物
- `{{test_cases}}` — 測試案例清單（JSON）
- `{{test_type}}` — 測試格式類型
- `{{red_light_feedback}}` — SyntaxError 時的修正建議（可為 None）

## 輸出格式

只輸出一個 fenced code block，標籤為 `tests`：

```tests
from solution import my_function
import pytest

def test_xxx():
    assert my_function(input) == expected
```

不輸出 `implementation` block。不輸出任何說明文字。

## 對應 prompt

`harness/prompts/test_writer.md`
