import sys
from harness.graph import build_graph
from harness.state import HarnessState, TaskResult, HarnessRunResult
from harness.utils.logger import init_run_log


def run_harness(user_input: str, log_dir: str = ".") -> HarnessRunResult:
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
    task_results: list[TaskResult] = final["task_results"]

    passed = sum(1 for r in task_results if r["passed"] and not r["forced"])
    forced = sum(1 for r in task_results if r["forced"])

    result: HarnessRunResult = {
        "task_results": task_results,
        "total": len(task_results),
        "passed": passed,
        "forced": forced,
        "failed": 0,
        "run_log_path": run_log_path,
    }
    return result


if __name__ == "__main__":
    user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter your request: ")
    run_result = run_harness(user_input)

    print("\n=== Harness Results ===")
    for r in run_result["task_results"]:
        if r["forced"]:
            status = "⚠️  FORCED"
        elif r["passed"]:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        print(f"Task {r['task_id']}: [{status}] {r['feedback'][:100]}")

    print(f"\n📊 Summary: {run_result['passed']}/{run_result['total']} passed"
          + (f", {run_result['forced']} forced" if run_result["forced"] else ""))
    print(f"📋 Run log: {run_result['run_log_path']}")
