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
    tdd_phase: str        # "write_tests" | "write_code"
    red_light_round: int  # test_writer 重試次數
    completed_code: dict  # {filename: code_str}，key 為檔名
    run_log_path: str     # JSONL log 檔案路徑，由 main.py 初始化
