import streamlit as st
import time
import traceback
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver(headless_mode=True):
    """Initializes and returns a Selenium WebDriver."""
    st.write(f"Setting up WebDriver (Headless: {headless_mode})...")
    options = Options()
    if headless_mode:
        options.add_argument('--headless')
        options.add_argument("--disable-gpu")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')
    options.add_argument("--window-size=1920,1080")
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    try:
        log_level = 'ERROR'
        os_environ = os.environ.copy()
        os_environ['WDM_LOG_LEVEL'] = log_level
        os_environ['WDM_PRINT_FIRST_EXEC'] = 'False'

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except ValueError as ve:
         # Catch common error if Chrome is not installed or path is wrong
         st.error(f"Error setting up WebDriver: {ve}")
         st.error(traceback.format_exc())
         return None
    except Exception as e:
        st.error(f"Error setting up WebDriver: {e}")
        st.error(traceback.format_exc())
        return None

def extract_body_content(html_source):
    """Extracts content within the <body> tags."""
    body_match = re.search(r"<body.*?>(.*?)</body>", html_source, re.IGNORECASE | re.DOTALL)
    if body_match:
        return body_match.group(1).strip()
    else:
        return html_source

def scrape_url(url):
    """Fetches HTML content of a URL using Selenium."""
    driver = None
    html_content = None
    try:
        driver = setup_driver(headless_mode=True)
        if driver:
            st.write(f"Navigating to {url} for scraping...")
            driver.get(url)
            time.sleep(5)
            html_content = driver.page_source
            html_content = extract_body_content(html_content)
            if html_content:
                print(f"Scraping complete. Got {len(html_content)} bytes of HTML.")
            else:
                st.warning("Scraping finished, but no HTML content retrieved.")
            return html_content
        else:
            st.error("Failed to initialize WebDriver for scraping.")
            return None
    except Exception as e:
        st.error(f"Error scraping URL {url}: {e}")
        st.error(traceback.format_exc())
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e_quit:
                 st.warning(f"Error closing WebDriver after scraping: {e_quit}")