from unittest.mock import patch
from harness.main import run_harness

MOCK_PLANNER = '[{"id":1,"task_description":"implement add(a,b)","dependencies":[],"expected_output":"add fn","output_filename":"solution.py","test_cases":[{"input":"1,2","expected":"3"}],"test_type":"unit"}]'
MOCK_TESTS = "```tests\nfrom solution import add\ndef test_add():\n    assert add(1, 2) == 3\n```"
MOCK_CODE = "```implementation\ndef add(a, b):\n    return a + b\n```"
MOCK_EVALUATOR = '{"is_success": true, "rating": 5, "feedback": "All tests pass."}'

def test_full_pipeline_smoke():
    from unittest.mock import MagicMock
    mock_runner = MagicMock()
    # 第一次執行（red_light_check）：ImportError = 正確紅燈
    mock_runner.run.return_value = {"success": False, "output": "ImportError: No module named 'solution'"}

    mock_eval_runner = MagicMock()
    mock_eval_runner.run.return_value = {"success": True, "output": "1 passed"}

    with patch("harness.agents.planner.call_llm", return_value=MOCK_PLANNER):
        with patch("harness.agents.generator.call_test_writer_llm", return_value=MOCK_TESTS):
            with patch("harness.agents.generator.call_code_writer_llm", return_value=MOCK_CODE):
                with patch("harness.agents.generator.get_runner", return_value=mock_runner):
                    with patch("harness.agents.evaluator.call_llm", return_value=MOCK_EVALUATOR):
                        with patch("harness.agents.evaluator.get_runner", return_value=mock_eval_runner):
                            results = run_harness("build an add function")

    assert len(results) == 1
    assert results[0]["task_id"] == 1
    assert results[0]["passed"] is True
