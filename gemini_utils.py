import streamlit as st
import google.generativeai as genai
import json
import re
import traceback
from config import GEMINI_MODEL_TEST_CASE, GEMINI_MODEL_SCRIPT, REQUEST_TIMEOUT_SECONDS

def call_gemini(prompt, model, api_key):
    """Sends a prompt to the Google Generative AI API and returns the response content."""
    try:
        genai.configure(api_key=api_key)
        llm = genai.GenerativeModel(model_name=model)
        response = llm.generate_content(
            prompt,
            request_options={'timeout': REQUEST_TIMEOUT_SECONDS},
            generation_config=genai.types.GenerationConfig(
                temperature=0.2
            )
        )

        if not response.parts:
            st.warning("Gemini response might have been blocked or is empty.")
            try:
                st.warning(f"Prompt Feedback: {response.prompt_feedback}")
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    st.error(f"Content blocked due to: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}")
            except ValueError:
                st.warning("Could not retrieve prompt feedback (response might be fully blocked).")
            return None

        response_content = response.text
        return response_content

    except Exception as e:
        st.error(f"Error communicating with Gemini API: {e}")
        st.error(traceback.format_exc())
        return None


def generate_test_cases(requirement_text, api_key):
    """Generates structured test cases using Gemini, with more flexible negative test expectations."""
    from config import GEMINI_MODEL_TEST_CASE

    prompt = f"""
    You are an expert Software Quality Assurance Engineer. Based on the following software requirement description, generate a comprehensive list of test cases in JSON format ONLY.

    Software Requirement:
    \"\"\"
    {requirement_text}
    \"\"\"

    Instructions:
    1.  Generate test cases covering positive scenarios, negative scenarios, edge cases, and boundary conditions relevant to the requirement.
    2.  Output MUST be a valid JSON array where each object represents a test case.
    3.  Each test case object MUST have the following fields:
        * `"id"`: A unique test case ID (e.g., "TC001").
        * `"description"`: A brief summary of the test objective.
        * `"preconditions"`: A list of strings describing the state required before starting the test (or an empty list []).
        * `"test_type"`: The category (e.g., "Functional", "UI", "Negative").
        * `"steps"`: An array of strings, each describing a clear action step. Be specific (e.g., "Enter 'user@test.com' into the username field").
        * `"expected_outcome"`:
            * For positive tests: A clear description of the successful result.
            * For negative tests: Describe the *nature* of the expected error. For example, instead of "Error message 'Your username is invalid!' is displayed", prefer "An error message indicating invalid credentials should be displayed." or "The system should prevent login and show an error related to incorrect password." If specific keywords are expected in an error, mention them like: "Error message containing 'invalid' or 'incorrect' should appear."
    4.  Do NOT include any explanations, summaries, apologies, or text outside the JSON array. Ensure the output starts with `[` and ends with `]`.
    5.  Ensure all string values within the JSON are enclosed in double quotes. Ensure array items are comma-separated. For empty arrays, use `[]`.

    Generate the JSON output now:
    """

    raw_response = call_gemini(prompt, GEMINI_MODEL_TEST_CASE, api_key)
    if raw_response:
        try:
            cleaned_response = raw_response.strip()
            # Remove markdown fences (```json ... ``` or ``` ... ```)
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]
            elif cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            json_start_index = cleaned_response.find('[')
            json_end_index = cleaned_response.rfind(']')

            if json_start_index != -1 and json_end_index != -1 and json_start_index < json_end_index:
                cleaned_response = cleaned_response[json_start_index : json_end_index + 1]
            else:
                first_brace = cleaned_response.find('{')
                last_brace = cleaned_response.rfind('}')
                if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                     cleaned_response = cleaned_response[first_brace : last_brace + 1]
                     if not cleaned_response.startswith('['):
                         cleaned_response = f"[{cleaned_response}]"
                else:
                    return None

            cleaned_response = re.sub(r",\s*(}|])", r"\1", cleaned_response)

            cleaned_response = re.sub(r'\[\s*\d+\s*:\s*', '[', cleaned_response)
            cleaned_response = re.sub(r',\s*\d+\s*:\s*', ',', cleaned_response)

            parsed_json = json.loads(cleaned_response)
            return parsed_json

        except json.JSONDecodeError as e:
            st.error(f"LLM generated invalid JSON even after cleaning attempts: {e}")
            st.text_area("JSON After Cleaning (Failed Parse):", cleaned_response, height=200)
            st.text_area("Original Raw Response from LLM:", raw_response, height=100)
            return None
        except Exception as e_clean:
            st.error(f"Unexpected error processing/cleaning LLM response: {e_clean}")
            st.text_area("Raw Response Causing Processing Error:", raw_response, height=200)
            return None
    else:
        st.warning("Received no response from LLM for test case generation.")
    return None


def generate_script(test_cases_list_of_dicts, url, html_excerpt, api_key):
    """Generates a Python Selenium script with structured output based on test cases and HTML."""
    from config import GEMINI_MODEL_SCRIPT

    try:
        test_cases_json_str = json.dumps(test_cases_list_of_dicts, indent=2)
    except Exception as e:
        st.error(f"Error converting test cases to JSON string: {e}")
        return None

    prompt = f"""
    You are an expert Python Test Automation Engineer specializing in Selenium WebDriver.
    Your task is to generate a complete Python script to automate the provided test cases (in JSON format) against a web application.
    The script MUST output results for each test case to `stdout` in a specific structured format.

    Target URL: {url}

    Test Cases (JSON):
    ```json
    {test_cases_json_str}
    ```

    HTML Excerpt (from the target URL's initial load, use for selector guidance):
    ```html
    {html_excerpt}
    ... (HTML may be truncated) ...
    ```

    **Critical Output Format for each test case (to `stdout`):**
    Each test function must print its result in the following multi-line format. This exact format is essential.
    ```
    TEST_RESULT_START
    ID: [Test Case ID from JSON (e.g., TC001)]
    DESCRIPTION: [Test Case Description from JSON]
    STATUS: [PASS|FAIL|ERROR]
    MESSAGE: [Details, e.g., "Assertion successful: User redirected to dashboard." or "FAIL: Expected error message containing 'invalid' not found." or "ERROR: Element 'username_field' not interactable."]
    TEST_RESULT_END
    ```
    - `STATUS: PASS` if all assertions pass.
    - `STATUS: FAIL` if an assertion fails or a specific expected negative outcome is not met correctly.
    - `STATUS: ERROR` if an unexpected Selenium exception (e.g., NoSuchElementException) occurs that prevents test completion.
    - `MESSAGE` should be concise and informative.

    Python Script Generation Instructions:
    1. **No writing the JSON data that was attached to the script:** Do not include the JSON data in the script. The script should be able to run without needing to parse or include the JSON data directly.
    2.  **Script Structure:**
        * Generate a complete, runnable Python script using Selenium with Python.
        * Include necessary imports: `selenium`, `time`, `argparse`, `sys`, `webdriver_manager.chrome`, `selenium.webdriver.support.ui.WebDriverWait`, `selenium.webdriver.support.expected_conditions as EC`, `selenium.webdriver.common.by.By`, `selenium.common.exceptions`.
        * Implement each test case from the JSON as a separate function (e.g., `def test_TC001(driver, test_case_data):`). Pass the `driver` and the corresponding `test_case_data` (dict for that TC) to each test function.
    3.  **Main Execution Block (`if __name__ == "__main__":`)**:
        * This block MUST orchestrate the running of ALL test functions.
        * It MUST handle WebDriver setup (using `webdriver_manager.chrome.ChromeDriverManager` and respecting a `--headless` argument via `argparse`).
        * For each test case mentioned in the JSON:
            * Call the corresponding test function (e.g., `test_TC001(driver, tc_data)`).
            * **Crucially, the call to EACH test function MUST be wrapped in its own `try...except Exception as e:` block.**
            * If an *unexpected* exception occurs within a test function's `try` block (not an `AssertionError` that you handle to set FAIL status), this main loop's `except` block should catch it. It should then print the structured output with `STATUS: ERROR` and the exception message.
            * Detailed tracebacks for these unexpected errors should still be printed to `sys.stderr` using `traceback.print_exc(file=sys.stderr)`.
        * Maintain counters for total passed, failed, and errored tests. Print a summary to `stdout` at the very end (e.g., "EXECUTION SUMMARY: Passed: X, Failed: Y, Errored: Z").
        * Ensure `driver.quit()` is in a `finally` block associated with the main WebDriver setup.
    4.  **Test Implementation (Inside each `def test_TCXXX(driver, test_case_data):` function):**
        * The function should start by printing the `TEST_RESULT_START`, `ID`, and `DESCRIPTION` lines using `test_case_data['id']` and `test_case_data['description']`.
        * Implement steps from `test_case_data['steps']`. Navigate to `{url}` at the start of each test for independence.
        * **Selector Strategy:** Use the HTML Excerpt for robust selectors (`By.ID`, `By.NAME`, `By.CSS_SELECTOR`, `By.XPATH`). Prioritize reliable ones. If HTML is limited, make reasonable choices and add a comment.
        * **Robustness:** Use `WebDriverWait` and `EC` for element presence, visibility, and interactability. Use reasonable timeouts (e.g., 10-15 seconds).
        * **Assertions & Reporting:**
            * For positive tests: Use `assert` statements. If all asserts pass, print `STATUS: PASS` and a success message. Then `TEST_RESULT_END`.
            * For negative tests (based on `test_case_data['expected_outcome']`):
                * If it expects an error message: Locate the error message element. Assert its visibility. If it mentions keywords, assert their presence (case-insensitive).
                * If it expects prevention of an action: Assert that the action did not lead to an undesired state (e.g., still on the same page, or a specific element is NOT present).
            * If an `AssertionError` occurs, it should be caught within the test function. Print `STATUS: FAIL` with a message detailing the assertion failure, then `TEST_RESULT_END`.
            * If an *unexpected* Selenium exception occurs (e.g. `TimeoutException`, `NoSuchElementException`), let it propagate to be caught by the main loop's `try...except`, which will then print the `STATUS: ERROR` block.
            * Ensure `TEST_RESULT_END` is always printed for each test attempt, even after a FAIL. If an unhandled exception causes it to be skipped, the main loop's error handler will deal with it.
    5.  **Output Format:** Generate ONLY the Python code block, enclosed in triple backticks (```python ... ```). No explanations outside the code block.
    Generate the Python script now:
    """

    response_content = call_gemini(prompt, GEMINI_MODEL_SCRIPT, api_key)
    if response_content:
        script_code = None
        match = re.search(r"```python\s*(.*?)\s*```", response_content, re.DOTALL | re.IGNORECASE)
        if match:
            script_code = match.group(1).strip()
        else:
            if response_content.strip().startswith("import ") or response_content.strip().startswith("from "):
                st.warning("Response did not contain ```python markers, but starts like Python code. Using the full response.")
                script_code = response_content.strip()
            else:
                st.error("Could not extract Python code block from the Gemini response.")
                # st.text_area("Raw Gemini Response (Code Block Extraction Failed):", response_content, height=200)
                return None

        return script_code
    else:
        st.warning("Received no response from LLM for script generation.")
    return None