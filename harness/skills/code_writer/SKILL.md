# Skill: code_writer

## 用途

看著已確認通過紅燈驗證的測試程式，產出能讓所有測試通過的實作代碼。
不產出測試程式（測試已由 test_writer 產出並確認）。

## 使用情境

- red_light_check 通過（正確紅燈）之後
- Evaluator 評估失敗需要 retry 時（feedback 傳入）

## 輸入

- `{{overall_goal}}` — 整個專案目標
- `{{completed_steps_summary}}` — 已完成任務摘要
- `{{task_description}}` — 當前任務描述
- `{{expected_output}}` — 預期產出物
- `{{test_type}}` — 測試類型
- `{{current_tests}}` — 已確認的測試程式（red_light_check 通過）
- `{{evaluator_feedback}}` — Evaluator 的修正建議（retry 時）

## 輸出格式

只輸出一個 fenced code block，標籤為 `implementation`：

```implementation
def my_function(x):
    return x + 1
```

不輸出 `tests` block。不輸出任何說明文字。

## 對應 prompt

`harness/prompts/code_writer.md`
