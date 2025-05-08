import streamlit as st
import subprocess
import os
import traceback
import uuid # For generating unique filenames
from config import EXECUTION_TIMEOUT_SECONDS

TESTS_DIR = "tests"

def execute_script_subprocess(script_string, headless_mode):
    """Executes the generated script in a subprocess, saving it to a 'tests' folder."""
    stdout_data = ""
    stderr_data = ""
    exit_code = -1
    script_path = None
    process = None

    try:
        if not os.path.exists(TESTS_DIR):
            try:
                os.makedirs(TESTS_DIR)
                st.write(f"Created directory: {os.path.abspath(TESTS_DIR)}")
            except OSError as e:
                st.error(f"Failed to create directory {TESTS_DIR}: {e}")
                stderr_data = f"Failed to create directory {TESTS_DIR}: {e}"
                return stdout_data, stderr_data, 1 # Return error code

        script_filename = f"test_script_{uuid.uuid4()}.py"
        script_path = os.path.join(TESTS_DIR, script_filename)

        with open(script_path, mode='w', encoding='utf-8') as script_file:
            script_file.write(script_string)
            script_file.flush()
        st.write(f"Generated script saved to: {os.path.abspath(script_path)}")

        command = ["python", script_path]
        if headless_mode:
            command.append("--headless")

        st.write(f"Executing command: {' '.join(command)}")
        st.info(f"Test execution started... Max timeout: {EXECUTION_TIMEOUT_SECONDS} seconds.")

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,            # Decode stdout/stderr as text
            encoding='utf-8',     # Specify encoding for decoding
            errors='replace'      # Handle potential decoding errors gracefully
        )

        stdout_data, stderr_data = process.communicate(timeout=EXECUTION_TIMEOUT_SECONDS)
        exit_code = process.returncode # Get the final exit code

        if exit_code == 0:
            st.success(f"Script execution finished successfully (Exit Code: {exit_code}).")
        else:
            st.warning(f"Script execution finished with errors (Exit Code: {exit_code}). Check stderr.")

    except subprocess.TimeoutExpired:
        st.error(f"Script execution timed out after {EXECUTION_TIMEOUT_SECONDS} seconds.")
        stderr_data += "\n--- Execution Timed Out ---"
        exit_code = 143 # SIGTERM typically results in 143 or similar
        if process and process.poll() is None: # Check if process is still running
            try:
                st.write("Attempting to terminate timed-out process...")
                process.terminate() # Try graceful termination first
                try:
                    # Wait a short period for termination
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    st.write("Termination timed out, killing process forcefully...")
                    process.kill()
                stdout_after, stderr_after = process.communicate()
                stdout_data += stdout_after
                stderr_data += stderr_after
            except Exception as kill_err:
                 st.warning(f"Error during process termination/kill: {kill_err}")
        if exit_code == -1 or exit_code == 0: exit_code = 143

    except FileNotFoundError:
        st.error("Error: 'python' command not found. Is Python installed and in your system's PATH?")
        stderr_data = "'python' command not found. Please ensure Python is installed and accessible."
        exit_code = 1 # Use a specific code for this common setup issue
    except Exception as e:
        st.error(f"An unexpected error occurred during script execution: {e}")
        st.error(traceback.format_exc())
        stderr_data += f"\n--- Subprocess Wrapper Error: {e}\n{traceback.format_exc()} ---"
        exit_code = 1
    finally:
        if script_path:
            st.write(f"Script {os.path.abspath(script_path)} was used for execution.")

    stdout_data = stdout_data or ""
    stderr_data = stderr_data or ""

    return stdout_data, stderr_data, exit_code