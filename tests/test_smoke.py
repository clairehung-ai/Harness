from unittest.mock import patch
from harness.main import run_harness

MOCK_PLANNER = '[{"id":1,"task_description":"implement add(a,b)","dependencies":[],"expected_output":"add fn","test_cases":[{"input":"1,2","expected":"3"}],"test_type":"unit"}]'
MOCK_GENERATOR = "```implementation\ndef add(a, b):\n    return a + b\n```\n\n```tests\nfrom solution import add\ndef test_add():\n    assert add(1, 2) == 3\n```"
MOCK_EVALUATOR = '{"is_success": true, "rating": 5, "feedback": "All tests pass."}'

def test_full_pipeline_smoke():
    from unittest.mock import MagicMock
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}

    with patch("harness.agents.planner.call_llm", return_value=MOCK_PLANNER):
        with patch("harness.agents.generator.call_llm", return_value=MOCK_GENERATOR):
            with patch("harness.agents.evaluator.call_llm", return_value=MOCK_EVALUATOR):
                with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
                    results = run_harness("build an add function")
    assert len(results) == 1
    assert results[0]["task_id"] == 1
    assert results[0]["passed"] is True
