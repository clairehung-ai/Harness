import sys
import os
import json
from harness.graph import build_graph
from harness.state import HarnessState, TaskResult, HarnessRunResult
from harness.utils.logger import init_run_log
from harness.utils.exporter import create_project_structure
from harness.config import AUTO_EXPORT, EXPORT_DIR, EXPORT_TESTS, GIT_ENABLED
from harness.utils.git_manager import setup_git_worktree


def run_harness(user_input: str, log_dir: str = ".", auto_export: bool | None = None, export_dir: str | None = None, git_slug: str | None = None) -> HarnessRunResult:
    graph = build_graph()
    run_log_path = init_run_log(log_dir)
    if export_dir is None:
        export_dir = EXPORT_DIR

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
        "export_dir": export_dir,
        "last_test_output": "",
    }
    final = graph.invoke(initial)
    task_results: list[TaskResult] = final["task_results"]

    passed = sum(1 for r in task_results if r["passed"] and not r["forced"])
    forced = sum(1 for r in task_results if r["forced"])

    # 自動導出代碼到專案目錄
    project_path = None
    if auto_export is None:
        auto_export = AUTO_EXPORT

    if auto_export:
        # 優先用 final state，若為空則從 JSONL log fallback 讀取
        completed_code = final.get("completed_code") or {}
        if not completed_code and run_log_path and os.path.exists(run_log_path):
            with open(run_log_path, encoding="utf-8") as _f:
                for _line in _f:
                    try:
                        _entry = json.loads(_line)
                        _fn = _entry.get("output_filename")
                        _code = _entry.get("current_code")
                        if _fn and _code:
                            completed_code[_fn] = _code
                    except Exception:
                        pass
            if completed_code:
                print(f"⚠️  completed_code was empty, recovered {len(completed_code)} files from JSONL log")

        if completed_code:
            project_name = export_dir if export_dir != "./output" else "generated_project"
            try:
                project_path = create_project_structure(
                    completed_code=completed_code,
                    task_results=task_results,
                    project_name=project_name,
                    include_tests=EXPORT_TESTS
                )
            except Exception as e:
                print(f"⚠️  Export failed: {e}")

    # Git worktree — 用 git_slug（若有）避免 body 的 HTML 雜訊污染 branch 名稱
    git_branch = None
    git_worktree_path = None
    if auto_export and project_path and GIT_ENABLED:
        git_result = setup_git_worktree(project_path, git_slug or user_input)
        if git_result["success"]:
            git_branch = git_result["branch"]
            git_worktree_path = git_result["worktree_path"]

    result: HarnessRunResult = {
        "task_results": task_results,
        "total": len(task_results),
        "passed": passed,
        "forced": forced,
        "failed": 0,
        "run_log_path": run_log_path,
        "project_path": project_path,
        "git_branch": git_branch,
        "git_worktree_path": git_worktree_path,
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
    if run_result.get("project_path"):
        print(f"📦 Project exported to: {run_result['project_path']}")
    if run_result.get("git_worktree_path"):
        print(f"🌿 Git worktree: {run_result['git_worktree_path']}  (branch: {run_result['git_branch']})")
