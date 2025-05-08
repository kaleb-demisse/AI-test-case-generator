import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# GEMINI_MODEL_TEST_CASE = 'models/gemini-2.5-pro-exp-03-25'
GEMINI_MODEL_TEST_CASE = 'models/gemini-2.5-flash-preview-04-17'
# GEMINI_MODEL_SCRIPT = 'models/gemini-2.5-flash-preview-04-17'
GEMINI_MODEL_SCRIPT = 'models/gemini-2.5-pro-exp-03-25'
REQUEST_TIMEOUT_SECONDS = 180
EXECUTION_TIMEOUT_SECONDS = 3000
