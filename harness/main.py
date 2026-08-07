import sys
from harness.graph import build_graph
from harness.state import HarnessState, TaskResult

def run_harness(user_input: str) -> list[TaskResult]:
    graph = build_graph()
    initial: HarnessState = {
        "input": user_input, "overall_goal": "",
        "tasks": [], "current_task_index": 0,
        "completed_steps_summary": "",
        "current_code": "", "current_tests": "",
        "evaluator_feedback": "", "passed": False,
        "round": 0, "task_results": [],
    }
    final = graph.invoke(initial)
    return final["task_results"]

if __name__ == "__main__":
    user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter your request: ")
    results = run_harness(user_input)
    print("\n=== Harness Results ===")
    for r in results:
        print(f"Task {r['task_id']}: [{'PASS' if r['passed'] else 'FAIL'}] {r['feedback'][:100]}")
