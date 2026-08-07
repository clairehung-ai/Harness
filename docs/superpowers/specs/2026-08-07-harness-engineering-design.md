# Harness Engineering Architecture Design

**Date:** 2026-08-07  
**Status:** Approved

---

## Overview

Harness is a multi-agent software engineering system built on LangGraph. It separates three concerns that typically collapse onto a single agent in long-running tasks: planning, generation, and evaluation. By making these explicit and running them in a controlled loop, the system can iteratively improve its output without human intervention.

---

## Architecture

### Roles

| Role | Type | Responsibility |
|------|------|----------------|
| **Planner** | LLM Agent | Parses input (natural language or structured ticket), breaks it into atomic tasks, defines test cases per task |
| **Orchestrator** | LangGraph Graph | Manages task execution order, passes context between agents, controls retry loop and termination |
| **Generator** | LLM Agent | Implements code for a single task, writes corresponding test code based on Planner's test cases |
| **Evaluator** | LLM Agent + subprocess | Executes tests in a sandbox, performs static quality assessment, produces pass/fail verdict and feedback |

### System Flow

```
Input (natural language or structured ticket)
        |
        v
   [Planner]
   Produces: [task1, task2, task3, ...]
        |
        v
   [Orchestrator] -- iterates over tasks -->
        |
        v
   [Generator]
   Produces: implementation code + test code
        |
        v
   [Evaluator]
   Executes tests (subprocess/sandbox)
   Produces: { is_success, rating, feedback }
        |
        |-- pass --> next task (Orchestrator advances)
        |
        +-- fail --> retry Generator with feedback
                     (up to MAX_ROUNDS per task)
                     if MAX_ROUNDS exceeded -> force advance with warning
        |
        v
   All tasks complete -> Final Output
```

---

## LangGraph State

```python
class HarnessState(TypedDict):
    input: str                        # original user request
    overall_goal: str                 # extracted by Planner
    tasks: list[Task]                 # full task list from Planner
    current_task_index: int           # which task Orchestrator is on
    completed_steps_summary: str      # running summary of completed tasks
    current_code: str                 # Generator latest output
    current_tests: str                # Generator latest test output
    evaluator_feedback: str           # Evaluator latest feedback
    round: int                        # retry count for current task
    task_results: list[TaskResult]    # accumulated results per task
```

---

## Agent Specifications

### Planner

**Input:** Raw user request (natural language or structured ticket)

**Output:** JSON array of tasks

```json
[
  {
    "id": 1,
    "task_description": "Implement a function that calculates the average of a list",
    "dependencies": [],
    "expected_output": "a Python function named calculate_average in utils.py",
    "test_cases": [
      { "input": "[1, 2, 3]", "expected": "2.0" },
      { "input": "[]", "expected": "raise ValueError" }
    ]
  }
]
```

**Key constraints:**
- Tasks must be atomic - one clear deliverable per task
- `dependencies` must reference valid task IDs
- `test_cases` must be concrete and executable - Generator uses these directly
- Planner receives Evaluator feedback on retry and may revise the plan

---

### Generator

**Input:**
- `overall_goal` - from Planner
- `completed_steps_summary` - from Orchestrator
- `task_description` + `expected_output` + `test_cases` - from current task
- `evaluator_feedback` - from previous attempt (if any)

**Output:**
- Implementation code (in markdown code blocks)
- Test code (in markdown code blocks), covering all `test_cases` from Planner

**Key constraints:**
- Must address all feedback from Evaluator if present
- Must write tests that directly correspond to Planner test_cases
- Must not invent new requirements beyond the task scope

---

### Evaluator

**Input:**
- `task_description` - original task
- Implementation code + test code from Generator

**Evaluation process:**
1. Execute tests via subprocess/sandbox
2. If tests fail: produce fail verdict immediately with specific failure details
3. If tests pass: perform static quality assessment (correctness, robustness, completeness)

**Output:**
```json
{
  "is_success": false,
  "rating": 3,
  "feedback": "Error handling for empty list is missing. Add a ValueError check before computing mean.",
  "suggested_changes": "if not numbers:\n    raise ValueError('Input list cannot be empty')"
}
```

**Evaluation criteria:**
1. **Correctness** - does it fulfill the task description?
2. **Robustness** - does it handle edge cases and errors?
3. **Completeness** - does it produce the expected output artifact?
4. **Syntax & Execution** - do the tests actually pass?

---

### Orchestrator (LangGraph Graph)

**Responsibilities:**
- Iterate over task list from Planner in dependency order
- Pass correct context variables to Generator (overall_goal, completed_steps_summary, evaluator_feedback)
- After each Evaluator result: decide to advance, retry, or terminate
- Maintain `completed_steps_summary` as tasks complete
- Enforce `MAX_ROUNDS` per task as a safety ceiling

**Termination conditions:**
- `is_success == true` -> advance to next task
- `round >= MAX_ROUNDS` -> force advance, log warning
- All tasks complete -> return final output

---

## Project Structure

```
harness/
|-- state.py          # HarnessState TypedDict
|-- graph.py          # LangGraph graph definition (Orchestrator)
|-- agents/
|   |-- planner.py    # Planner agent + prompt
|   |-- generator.py  # Generator agent + prompt
|   +-- evaluator.py  # Evaluator agent + subprocess runner
|-- prompts/
|   |-- planner.md    # Planner system prompt
|   |-- generator.md  # Generator system prompt
|   +-- evaluator.md  # Evaluator system prompt
|-- sandbox/
|   +-- runner.py     # Subprocess/sandbox code execution
|-- main.py           # Entry point
+-- config.py         # MAX_ROUNDS, model settings, etc.
```

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_ROUNDS` | 3 | Maximum retry attempts per task |
| `LLM_MODEL` | gpt-4o | Model used for all agents |
| `SANDBOX_TIMEOUT` | 10s | Max execution time for test subprocess |

---

## Input Formats

The system accepts two input formats:

**Natural language:**
```
Build a Python utility that reads a CSV file and returns summary statistics
```

**Structured ticket:**
```json
{
  "title": "CSV Summary Utility",
  "description": "...",
  "acceptance_criteria": ["...", "..."]
}
```

Planner normalizes both formats into the same task list structure.

---

## Key Design Decisions

1. **Per-task loop, not per-round loop** - retry happens at the task level, not the whole plan. This is more efficient and allows partial progress to be preserved.

2. **Orchestrator is code, not an LLM** - orchestration logic (routing, context assembly, termination) lives in LangGraph graph edges, not in an LLM prompt. This makes control flow deterministic and debuggable.

3. **Planner owns test case specification** - Generator writes tests, but the test requirements come from Planner. This ensures tests are grounded in the original requirements, not invented by the implementer.

4. **Evaluator executes code** - static LLM assessment alone is insufficient. Real test execution via subprocess provides ground truth on whether the code actually works.
