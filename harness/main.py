import sys
from harness.graph import build_graph
from harness.state import HarnessState, TaskResult
from harness.utils.logger import init_run_log

def run_harness(user_input: str, log_dir: str = ".") -> list[TaskResult]:
    graph = build_graph()
    run_log_path = init_run_log(log_dir)
    initial: HarnessState = {
        "input": user_input, "overall_goal": "",
        "tasks": [], "current_task_index": 0,
        "completed_steps_summary": "",
        "current_code": "", "current_tests": "",
        "evaluator_feedback": "", "passed": False,
        "round": 0, "task_results": [],
        "tdd_phase": "write_tests",
        "red_light_round": 0,
        "completed_code": {},
        "run_log_path": run_log_path,
    }
    final = graph.invoke(initial)
    print(f"\n📋 Run log: {run_log_path}")
    return final["task_results"]

if __name__ == "__main__":
    user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter your request: ")
    results = run_harness(user_input)
    print("\n=== Harness Results ===")
    for r in results:
        print(f"Task {r['task_id']}: [{'PASS' if r['passed'] else 'FAIL'}] {r['feedback'][:100]}")
