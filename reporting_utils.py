import streamlit as st
import html
import re

def parse_structured_results(stdout):
    """Parses the structured test results from stdout."""
    results = []
    if not stdout:
        return results

    pattern = re.compile(
        r"TEST_RESULT_START\s*"
        r"ID:\s*(.*?)\s*"
        r"DESCRIPTION:\s*(.*?)\s*"
        r"STATUS:\s*(.*?)\s*"
        r"MESSAGE:\s*(.*?)\s*"
        r"TEST_RESULT_END",
        re.DOTALL
    )

    for match in pattern.finditer(stdout):
        results.append({
            "id": match.group(1).strip(),
            "description": match.group(2).strip(),
            "status": match.group(3).strip().upper(), # Normalize status
            "message": match.group(4).strip()
        })
    return results

def format_report(stdout, stderr, exit_code):
    """Formats the execution results into a markdown report, now with a results table."""
    report_parts = ["## Test Execution Report"]

    report_parts.append(f"**Overall Exit Code:** `{exit_code}`")
    if exit_code == 0:
        report_parts.append("**Overall Status:** <span style='color:green; font-weight:bold;'>Execution Completed</span> (Individual test statuses below)")
    elif exit_code == 1 and ("EXECUTION SUMMARY:" in (stdout or "") or any("FAIL" in r.get("status","") for r in parse_structured_results(stdout))): # common for test runners if failures exist
        report_parts.append("**Overall Status:** <span style='color:orange; font-weight:bold;'>Execution Completed with Failures</span> (See details below)")
    elif exit_code == 143 or exit_code == -9 or exit_code == -15: # TERM/KILL
        report_parts.append("**Overall Status:** <span style='color:red; font-weight:bold;'>Execution Terminated or Timed Out</span>")
    else:
        report_parts.append(f"**Overall Status:** <span style='color:red; font-weight:bold;'>Execution Failed or Errored</span> (Exit Code: {exit_code})")
    report_parts.append("\n---")

    parsed_results = parse_structured_results(stdout)
    if parsed_results:
        report_parts.append("### Individual Test Case Results")
        table_header = "| Test ID | Description | Status | Message |\n|---|---|---|---|"
        report_parts.append(table_header)
        for res in parsed_results:
            status_color = "green"
            if res['status'] == "FAIL":
                status_color = "red"
            elif res['status'] == "ERROR":
                status_color = "orange"
            
            esc_id = html.escape(res['id'])
            esc_desc = html.escape(res['description'])
            esc_status = html.escape(res['status'])
            esc_msg = html.escape(res['message'].replace("\n", "<br>"))

            table_row = f"| {esc_id} | {esc_desc} | <span style='color:{status_color}; font-weight:bold;'>{esc_status}</span> | {esc_msg} |"
            report_parts.append(table_row)
        report_parts.append("\n")
    else:
        report_parts.append("No structured test results found in standard output. The script might not have run correctly or produced output in the expected format.")

    summary_match = re.search(r"EXECUTION SUMMARY: Passed: (\d+), Failed: (\d+), Errored: (\d+)", stdout or "")
    if summary_match:
        passed, failed, errored = summary_match.groups()
        report_parts.append("### Script Execution Summary")
        report_parts.append(f"- **Total Passed:** {passed}")
        report_parts.append(f"- **Total Failed:** {failed}")
        report_parts.append(f"- **Total Errored:** {errored}")
    report_parts.append("\n---")

    escaped_stdout = html.escape(stdout or "No standard output captured.")
    escaped_stderr = html.escape(stderr or "No standard error output captured.")

    report_parts.append("<details>\n <summary><strong>Full Standard Output (`stdout`)</strong> - Click to expand</summary>\n"
                        f"<pre><code style='white-space: pre-wrap; word-wrap: break-word;'>{escaped_stdout}</code></pre>\n</details>\n")
    report_parts.append("<details>\n <summary><strong>Full Standard Error (`stderr`)</strong> - Click to expand</summary>\n"
                        f"<pre><code style='white-space: pre-wrap; word-wrap: break-word;'>{escaped_stderr}</code></pre>\n</details>\n")

    report_parts.append("--- \n **Analysis Notes:**")
    if any(r['status'] == "FAIL" for r in parsed_results) or any(r['status'] == "ERROR" for r in parsed_results):
        report_parts.append("<span style='color:red;'>One or more tests failed or encountered errors. Review the results table and `stderr` log.</span>")
    elif exit_code != 0:
         report_parts.append(f"<span style='color:red;'>Script exited with a non-zero code ({exit_code}). Review `stderr` for critical errors.</span>")
    elif not parsed_results and (stdout or stderr):
        report_parts.append("<span style='color:orange;'>Script ran, but no structured test results were parsed. Check `stdout` for output format compliance or `stderr` for errors during test execution.</span>")
    elif not parsed_results and not stdout and not stderr and exit_code == 0:
        report_parts.append("<span style='color:orange;'>Script executed with exit code 0 but produced no output to stdout or stderr. Verify script logging and assertions.</span>")
    elif all(r['status'] == "PASS" for r in parsed_results) and exit_code == 0:
        report_parts.append("<span style='color:green;'>All parsed tests passed and script exited successfully.</span>")
    else: # Catch-all
        report_parts.append("Review logs and exit code to determine execution status.")

    return "\n".join(report_parts)