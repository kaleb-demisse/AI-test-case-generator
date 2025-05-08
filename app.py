# app.py
import streamlit as st
import os
import json
from streamlit_ace import st_ace

# Assuming these utility files exist and are correct
from config import GEMINI_API_KEY
from gemini_utils import generate_test_cases, generate_script
from selenium_utils import scrape_url
from execution_utils import execute_script_subprocess
from reporting_utils import format_report

st.set_page_config(layout="wide", page_title="Auto Test Case Generator")

st.title("Auto Test Case Generator")
st.markdown("Generate Selenium test scripts from requirements using AI, edit them, then run.")
st.markdown("---")

if not GEMINI_API_KEY:
     st.error("**CRITICAL:** `GEMINI_API_KEY` environment variable not set.")
     st.warning("Please create a `.env` file with `GEMINI_API_KEY=YOUR_API_KEY` or set it system-wide.")
     st.stop()

def apply_editor_deltas(base_data_list, editor_deltas_dict):
    if not isinstance(base_data_list, list):
        # st.warning("Base data for delta application is not a list.")
        added_rows_val = editor_deltas_dict.get("added_rows", [])
        return added_rows_val[:] if isinstance(added_rows_val, list) else []

    current_rows_copy = [row.copy() for row in base_data_list]

    deleted_indices = set(editor_deltas_dict.get("deleted_rows", []))
    edited_row_instructions = editor_deltas_dict.get("edited_rows", {})
    added_row_data = editor_deltas_dict.get("added_rows", [])

    temp_rows_after_edits = []
    for original_idx, row in enumerate(current_rows_copy):
        if str(original_idx) in edited_row_instructions:
            changes = edited_row_instructions[str(original_idx)]
            if isinstance(changes, dict):
                 row.update(changes)
        temp_rows_after_edits.append(row)
    
    final_rows_after_deletes = []
    for original_idx, row in enumerate(temp_rows_after_edits):
        if original_idx not in deleted_indices:
            final_rows_after_deletes.append(row)
    
    if isinstance(added_row_data, list):
        for new_row in added_row_data:
            if isinstance(new_row, dict):
                final_rows_after_deletes.append(new_row.copy())
            # else:
                # st.warning(f"Encountered non-dictionary item in added_rows: {new_row}")
    
    return final_rows_after_deletes

default_requirement = "Users should be able to log in with valid credentials (student/Password123) and be redirected to the dashboard."
default_url = "https://practicetestautomation.com/practice-test-login/"

if 'requirement_text' not in st.session_state:
    st.session_state.requirement_text = default_requirement
if 'weburl' not in st.session_state:
    st.session_state.weburl = default_url
if 'test_cases_list_original' not in st.session_state:
    st.session_state.test_cases_list_original = None
if 'data_editor_base_data' not in st.session_state:
    st.session_state.data_editor_base_data = None
if 'test_cases_json_str' not in st.session_state:
    st.session_state.test_cases_json_str = None
if 'python_script' not in st.session_state:
    st.session_state.python_script = None
if 'json_generated_flag' not in st.session_state:
    st.session_state.json_generated_flag = False
if 'script_generated' not in st.session_state:
    st.session_state.script_generated = False
if 'data_editor_active_display_flag' not in st.session_state:
    st.session_state.data_editor_active_display_flag = False
if 'execution_stdout' not in st.session_state:
    st.session_state.execution_stdout = None
if 'execution_stderr' not in st.session_state:
    st.session_state.execution_stderr = None
if 'execution_exit_code' not in st.session_state:
    st.session_state.execution_exit_code = None

st.subheader("1. Define Requirement & Target URL")
st.session_state.requirement_text = st.text_area(
    "Enter Software Requirement Description:",
    value=st.session_state.requirement_text,
    height=120,
    key="requirement_input"
)
st.session_state.weburl = st.text_input(
    "Enter the Target Website URL:",
    value=st.session_state.weburl,
    key="url_input"
)

st.subheader("2. Generate Test Cases")
if st.button("Generate Test Cases", key="generate_json", type="primary"):
    st.session_state.test_cases_list_original = None
    st.session_state.data_editor_base_data = None
    st.session_state.test_cases_json_str = None
    st.session_state.python_script = None
    st.session_state.execution_stdout = None
    st.session_state.execution_stderr = None
    st.session_state.execution_exit_code = None
    st.session_state.json_generated_flag = False
    st.session_state.script_generated = False
    st.session_state.data_editor_active_display_flag = False
    if "data_editor_content" in st.session_state:
        del st.session_state.data_editor_content
    if "ace_editor" in st.session_state:
        del st.session_state.ace_editor

    req_text = st.session_state.requirement_text
    url_text = st.session_state.weburl

    if not req_text or not url_text:
        st.warning("Please provide both the requirement description and the target URL.")
    else:
        with st.spinner("Generating Test Cases via Gemini... This may take a minute."):
            test_cases_result_object = generate_test_cases(req_text, GEMINI_API_KEY)

            if test_cases_result_object is not None and isinstance(test_cases_result_object, list):
                st.session_state.test_cases_list_original = test_cases_result_object
                data_for_editor_display_initial = []
                for tc in test_cases_result_object:
                    if not isinstance(tc, dict): continue
                    editable_tc = tc.copy()
                    editable_tc['preconditions_edit'] = "\n".join(tc.get('preconditions', []) if isinstance(tc.get('preconditions'), list) else [])
                    editable_tc['steps_edit'] = "\n".join(tc.get('steps', []) if isinstance(tc.get('steps'), list) else [])
                    data_for_editor_display_initial.append(editable_tc)
                st.session_state.data_editor_base_data = data_for_editor_display_initial
                
                try:
                    st.session_state.test_cases_json_str = json.dumps(test_cases_result_object, indent=4)
                    st.session_state.json_generated_flag = True
                    st.success("Test cases generated successfully!")
                except Exception as e:
                    st.error(f"Failed to format generated test cases as JSON string: {e}")
                    st.session_state.test_cases_json_str = str(test_cases_result_object)
                    st.session_state.json_generated_flag = True
            elif test_cases_result_object is not None:
                st.error("Generated test cases are not in the expected list format. Displaying raw output.")
                st.session_state.test_cases_list_original = None
                st.session_state.data_editor_base_data = None
                st.session_state.test_cases_json_str = str(test_cases_result_object)
                st.session_state.json_generated_flag = True
            else:
                st.error("Failed to generate test cases or result was empty.")
                st.session_state.json_generated_flag = False

if st.session_state.json_generated_flag and isinstance(st.session_state.get('data_editor_base_data'), list):
    st.subheader("Review & Edit Test Cases")
    st.session_state.data_editor_active_display_flag = True
    st.data_editor(
        st.session_state.data_editor_base_data,
        key="data_editor_content", 
        column_config={
            "id": st.column_config.TextColumn("ID", help="Unique Test Case ID", width="small", required=True),
            "description": st.column_config.TextColumn("Description", width="large", required=True),
            "preconditions_edit": st.column_config.TextColumn("Preconditions", width="medium"),
            "steps_edit": st.column_config.TextColumn("Steps", width="large", required=True),
            "expected_outcome": st.column_config.TextColumn("Expected Outcome", width="large", required=True),
            "test_type": st.column_config.SelectboxColumn("Test Type", width="medium",
                options=["Functional", "UI", "Negative", "Security", "Performance", "Usability", "Accessibility", "Edge Case", "Boundary", "Other"], required=True),
            "preconditions": None, "steps": None,
        },
        num_rows="dynamic", use_container_width=True, height=max(350, len(st.session_state.data_editor_base_data) * 55 + 55) if st.session_state.data_editor_base_data else 350
    )
    st.info("Add, remove, or edit test cases. Click 'Generate Python Script' to use these edits.")

elif st.session_state.json_generated_flag and not isinstance(st.session_state.get('data_editor_base_data'), list):
    st.subheader("Review Test Cases (Read-Only)")
    st.warning("Generated test cases were not in a list format suitable for editing. Showing raw data.")
    st.text_area("Generated Data (read-only):", value=st.session_state.test_cases_json_str, height=250, disabled=True)
    st.session_state.data_editor_active_display_flag = False


if st.session_state.json_generated_flag:
    st.subheader("3. Generate Python Script")
    if st.button("Generate Python Script", key="generate_script_btn"):
        st.session_state.python_script = None
        st.session_state.script_generated = False
        st.session_state.execution_stdout = None
        st.session_state.execution_stderr = None
        st.session_state.execution_exit_code = None

        url_text = st.session_state.weburl
        processed_test_cases_for_script = [] 
        source_data_for_transformation = []

        # st.write("--- Debug Info: Inside 'Generate Python Script' ---")
        # st.write(f"1. `st.session_state.data_editor_active_display_flag`: {st.session_state.get('data_editor_active_display_flag')}")
        
        editor_content_raw = st.session_state.get('data_editor_content')
        editor_content_exists = editor_content_raw is not None
        # st.write(f"2. `'data_editor_content' exists`: {editor_content_exists}")
        
        # if editor_content_exists:
            # st.write(f"3. `st.session_state.data_editor_content` (Type: {type(editor_content_raw)}):")
            # try:
            #     st.json(editor_content_raw)
            # except Exception as ex:
            #     st.text(str(editor_content_raw))
        # else:
            # st.write("3. `st.session_state.data_editor_content` not found.")

        # st.write(f"4. `st.session_state.data_editor_base_data` (Type: {type(st.session_state.get('data_editor_base_data'))}):")
        # st.json(st.session_state.get('data_editor_base_data', "Not set")) # Can be large

        if st.session_state.get('data_editor_active_display_flag', False) and editor_content_exists:
            if isinstance(editor_content_raw, dict):
                # st.write("Processing DELTA structure from `data_editor_content`.")
                base_data = st.session_state.get('data_editor_base_data', [])
                if base_data is None: base_data = [] 
                source_data_for_transformation = apply_editor_deltas(base_data, editor_content_raw)
                # st.write(f"Data after applying deltas: {len(source_data_for_transformation)} rows.")
            elif isinstance(editor_content_raw, list):
                # st.write("Processing LIST structure from `data_editor_content` (unexpected based on logs).")
                source_data_for_transformation = editor_content_raw
            # else:
                # st.warning("`data_editor_content` is not a recognized dict (deltas) or list. Trying fallback.")
        
        if not source_data_for_transformation:
            # st.write("Editor data not used or resulted in no cases. Attempting to use original formatted base data.")
            base_data_for_fallback = st.session_state.get('data_editor_base_data')
            if isinstance(base_data_for_fallback, list):
                source_data_for_transformation = base_data_for_fallback
                # st.write(f"Using `data_editor_base_data` directly. Found {len(source_data_for_transformation)} cases.")
            else:
                # st.write("`data_editor_base_data` not usable. Attempting `test_cases_list_original`.")
                original_gemini_output = st.session_state.get('test_cases_list_original')
                if isinstance(original_gemini_output, list):
                    temp_formatted_list = []
                    for tc in original_gemini_output:
                        if not isinstance(tc, dict): continue
                        editable_tc = tc.copy()
                        editable_tc['preconditions_edit'] = "\n".join(tc.get('preconditions', []) if isinstance(tc.get('preconditions'), list) else [])
                        editable_tc['steps_edit'] = "\n".join(tc.get('steps', []) if isinstance(tc.get('steps'), list) else [])
                        temp_formatted_list.append(editable_tc)
                    source_data_for_transformation = temp_formatted_list
                    # st.write(f"Using formatted `test_cases_list_original`. Found {len(source_data_for_transformation)} cases.")
                # else:
                    # st.write("No valid source data found for transformation.")
                    # source_data_for_transformation = []

        if isinstance(source_data_for_transformation, list):
            for i, editor_row_dict in enumerate(source_data_for_transformation):
                if not isinstance(editor_row_dict, dict):
                    # st.warning(f"Skipping non-dictionary item #{i} during final transformation: {editor_row_dict}")
                    continue
                
                final_tc = {}
                final_tc['id'] = str(editor_row_dict.get('id', f"TC_AutoGen_ID_{len(processed_test_cases_for_script)+1}"))
                final_tc['description'] = str(editor_row_dict.get('description', 'N/A'))
                final_tc['test_type'] = str(editor_row_dict.get('test_type', 'Functional'))
                final_tc['expected_outcome'] = str(editor_row_dict.get('expected_outcome', 'N/A'))
                
                preconditions_str = editor_row_dict.get('preconditions_edit', '')
                final_tc['preconditions'] = [p.strip() for p in str(preconditions_str).split('\n') if p.strip()]
                
                steps_str = editor_row_dict.get('steps_edit', '')
                final_tc['steps'] = [s.strip() for s in str(steps_str).split('\n') if s.strip()]
                
                for key, value in editor_row_dict.items():
                    if key not in final_tc and not key.endswith('_edit') and key not in ['preconditions', 'steps']:
                        final_tc[key] = value
                processed_test_cases_for_script.append(final_tc)
            # st.write(f"Final transformation complete. {len(processed_test_cases_for_script)} test cases prepared for script generation.")
        # else:
            # st.error("Source data for transformation was not a list. Cannot proceed.")
            # processed_test_cases_for_script = []


        # st.write(f"Final check: `processed_test_cases_for_script` has {len(processed_test_cases_for_script)} items.")
        if not processed_test_cases_for_script:
            st.error("No valid test cases available to generate a script.")
            st.session_state.test_cases_json_str = "[]"
        else:
            # st.write("--- Debug: Structure of the FIRST processed test case for script: ---")
            # st.json(processed_test_cases_for_script[0])
            # st.write("--- End Debug ---")
            try:
                st.session_state.test_cases_json_str = json.dumps(processed_test_cases_for_script, indent=4)
            except Exception as e:
                st.error(f"Error serializing final test cases for display: {e}")

            with st.spinner("🕸️ Scraping target URL & Generating Selenium Script..."):
                html_content = scrape_url(url_text)
                if html_content:
                    html_excerpt = html_content[:75000]
                    script_result = generate_script(
                        processed_test_cases_for_script, url_text, html_excerpt, GEMINI_API_KEY
                    )
                    st.session_state.python_script = script_result
                    if st.session_state.python_script:
                        st.success("Python script generated successfully!")
                        st.session_state.script_generated = True
                    else:
                        st.error("Failed to generate Python script.")
                        st.session_state.script_generated = False
                else:
                    st.error("Failed to scrape target URL.")
                    st.session_state.script_generated = False

if st.session_state.script_generated and st.session_state.python_script is not None:
    st.subheader("✏️ Review & Edit Python Script")
    edited_script_from_ace = st_ace(
        value=st.session_state.python_script,
        language="python", key="ace_editor", theme="github", auto_update=True, height=400
    )
    if edited_script_from_ace != st.session_state.python_script:
        st.session_state.python_script = edited_script_from_ace
    st.info("Modify the Python script above if needed. Changes are live-updated.")
    st.markdown("---")

if st.session_state.script_generated:
    st.subheader("4. Execute Tests")
    headless_mode = st.toggle("Run in Headless Mode", True, key="headless_toggle")
    if st.button("🚀 Run Generated Script", key="run_script"):
         st.session_state.execution_stdout = None
         st.session_state.execution_stderr = None
         st.session_state.execution_exit_code = None
         script_to_run = st.session_state.python_script
         if not script_to_run:
             st.error("Cannot run an empty script.")
         else:
             with st.spinner("Executing script... Please wait."):
                stdout, stderr, exit_code = execute_script_subprocess(script_to_run, headless_mode)
                st.session_state.execution_stdout = stdout
                st.session_state.execution_stderr = stderr
                st.session_state.execution_exit_code = exit_code

if st.session_state.execution_exit_code is not None:
    st.subheader("Execution Report")
    st.markdown("---")
    report_md = format_report(
        st.session_state.execution_stdout, st.session_state.execution_stderr, st.session_state.execution_exit_code
    )
    st.markdown(report_md, unsafe_allow_html=True)