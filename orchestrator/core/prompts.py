from typing import Any

APPLY_EDITS_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "apply_search_replace_edits",
        "description": "Applies atomic search-and-replace edits to files in the repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "edits": {
                    "type": "array",
                    "description": "List of surgical search-and-replace blocks to apply.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Relative path to the file to modify.",
                            },
                            "search_content": {
                                "type": "string",
                                "description": "Exact character sequence in the target file to be replaced.",
                            },
                            "replace_content": {
                                "type": "string",
                                "description": "New content to replace search_content with.",
                            },
                        },
                        "required": ["file_path", "search_content", "replace_content"],
                    },
                },
            },
            "required": ["edits"],
        },
    },
}


def build_triage_prompt(
    issue_text: str,
    repo_map: str,
    grep_context: str | None = None,
    has_image: bool = False,
) -> str:
    prompt = (
        f"You are the Lead Triage Architect.\n\n"
        f"## Issue Description:\n{issue_text}\n\n"
    )
    if has_image:
        prompt += (
            "## Attached Screenshot:\n"
            "An image attachment is provided. Carefully inspect the visual elements, dialog headers, "
            "input fields, labels, icons, buttons, and anomalies in the screenshot.\n\n"
        )
    prompt += f"## Repository Map:\n{repo_map}\n\n"
    if grep_context:
        prompt += f"## Codebase Search Matches:\n{grep_context}\n\n"

    prompt += (
        "Analyze the repository structure and issue. Identify:\n"
        "1. Visual Defect Analysis: Detailed summary of what is visually wrong.\n"
        "2. Suspect Files: Exact file paths most likely responsible (templates, components, styles, or scripts).\n"
        "3. Targeted Plan: What lines or elements need to be adjusted."
    )
    return prompt


def build_reproduce_prompt(issue_text: str) -> str:
    return (
        f"You are the Test Engineer. Write a reproduction test case for this issue:\n\n"
        f"{issue_text}\n\n"
        f"Output the test file inside a code block, for example:\n"
        f"```python:tests/test_reproduce_issue.py\n"
        f"# test code that triggers the bug\n"
        f"```\n"
        f"The test MUST FAIL (Red) on the current buggy codebase."
    )


def build_plan_prompt(
    issue_text: str,
    reproduce_test_path: str | None,
    failing_test_output: str | None,
    human_hint: str | None = None,
    triage_analysis: str | None = None,
) -> str:
    prompt = (
        f"You are the Systems Architect. Review the bug and technical context:\n\n"
        f"## Issue:\n{issue_text}\n\n"
    )
    if triage_analysis:
        prompt += f"## Triage & Visual Defect Analysis:\n{triage_analysis}\n\n"

    if reproduce_test_path or failing_test_output:
        prompt += (
            f"Reproduction Test: {reproduce_test_path}\n"
            f"Error Output:\n{failing_test_output}\n\n"
        )
    if human_hint:
        prompt += f"## Developer Guidance / Hint:\n{human_hint}\n\n"

    prompt += "Formulate a surgical, step-by-step implementation plan. List the exact files and functions to modify."
    return prompt


def build_edit_prompt(
    plan_summary: str | None,
    last_error: str | None = None,
    human_hint: str | None = None,
    file_contexts: dict[str, str] | None = None,
    protocol: str = "delimited_blocks",
) -> str:
    prompt = (
        f"You are the Core Coder. Apply surgical edits to fix the issue according to the plan:\n\n"
        f"{plan_summary}\n\n"
    )
    if file_contexts:
        prompt += "## Verbatim Target File Contents:\n"
        for path, content in file_contexts.items():
            prompt += f"### File: {path}\n```\n{content}\n```\n\n"

    if human_hint:
        prompt += f"Developer Guidance / Hint:\n{human_hint}\n\n"

    if last_error:
        prompt += f"Previous failure to correct:\n{last_error}\n\n"

    if protocol == "json_tools":
        prompt += "Call the `apply_search_replace_edits` function with your list of surgical edits."
    else:
        prompt += (
            "Output your edits using EXACT SEARCH/REPLACE blocks. The SEARCH block MUST match the verbatim lines "
            "from the file contents above character-for-character including indentation:\n\n"
            "FILE: src/example.py\n"
            "<<<<<<< SEARCH\n"
            "exact lines to replace\n"
            "=======\n"
            "new replacement lines\n"
            ">>>>>>> REPLACE"
        )
    return prompt


def build_review_prompt(issue_text: str, git_diff: str) -> str:
    return (
        f"You are the Staff Code Reviewer. Review the verified git diff against the issue prompt:\n\n"
        f"Issue: {issue_text}\n"
        f"Git Diff:\n{git_diff}\n\n"
        f"Generate a Pull Request Title and detailed markdown PR Body summarizing the changes."
    )
