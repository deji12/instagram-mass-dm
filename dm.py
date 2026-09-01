# ============================================================
# bot.py – Final with account suspension/challenge auto‑skip
# ============================================================

import os
import json
import psutil
import re
import time
import math
import random
import tempfile
import zipfile
import shutil
import threading
from pathlib import Path
from sys import exit
from json import dump, load
from json.decoder import JSONDecodeError

from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    InvalidSessionIdException,
    WebDriverException,
)
from selenium.webdriver.chrome.service import Service

from hikerapi import Client as HikerClient
from instagrapi import Client as InstagrapiClient
from instagrapi.exceptions import DirectMessageRequestsDisabled

from configuration import *

# Global logger
LOGFILE = open("./cache/logs.txt", "a")

# Custom exceptions
class SessionDeadError(Exception):
    pass

class AccountUnavailableError(Exception):
    pass

# ============================================================
# Helper functions (unchanged)
# ============================================================

def account():
    if 'accounts_new.txt' not in os.listdir('.'):
        print(f"{WARNING}ERROR: accounts_new.txt is not in main folder.{ENDC}")
        return {}
    accounts = {}
    with open("accounts_new.txt", "r") as f:
        for line in f:
            ordered = re.findall(r"\[(.*?)\]", line)
            if len(ordered) >= 2:
                accounts[ordered[0]] = ordered[1]
    return accounts

def get_saved_user_ids(target):
    path = f"users/{target}.txt"
    if not os.path.isfile(path):
        return []
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]

def get_saved_session_id(username):
    path = f"cookies/{username}.json"
    if not os.path.isfile(path):
        return None
    with open(path, 'r') as f:
        data = load(f)
        return data.get('value')

def targets(targetted_usernames=False):
    if targetted_usernames:
        folder = Path('./targetted_mass_dm')
        return [f.stem for f in folder.iterdir() if f.is_file() and f.stem != 'targetted_usernames']
    else:
        path = "targets.txt"
        if not os.path.isfile(path):
            return []
        with open(path, "r") as f:
            return [line.strip() for line in f if line.strip()]

def chunk_and_split_targetted_followers():
    with open("targetted_mass_dm/targetted_usernames.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()
    total = len(lines)
    chunk_size = math.ceil(total / NUMBER_OF_THREADS_)
    for i in range(NUMBER_OF_THREADS_):
        start = i * chunk_size
        end = min(start + chunk_size, total)
        chunk = lines[start:end]
        with open(f"targetted_mass_dm/batch_{i+1}.txt", "w", encoding="utf-8") as out:
            out.writelines(chunk)
    print(f"{OKGREEN}Split {total} lines into {NUMBER_OF_THREADS_} batches.{ENDC}")

def clear_fetched_followers():
    users_folder = Path('./users')
    if not users_folder.exists():
        return
    for item in users_folder.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            print(f"Failed to delete {item}. Reason: {e}")

def find_user():
    hiker_client = HikerClient(token=HIKER_API_TOKEN)
    username = input(f"\n{HEADER}Enter username: {ENDC}")
    try:
        target_user_data = hiker_client.user_by_username_v2(username)
        print(json.dumps(target_user_data, indent=4))
    except Exception as e:
        print(f"\n{FAIL}An error occured:{ENDC} \n{WARNING}{e}{ENDC}\n")

def create_proxy_extension(host, port, username, password):
    """Creates or reuses a Chrome extension for proxy authentication."""
    ext_dir = "./proxy_extensions"
    os.makedirs(ext_dir, exist_ok=True)
    ext_filename = f"proxy_auth_{host}_{port}.zip"
    ext_path = os.path.join(ext_dir, ext_filename)

    if os.path.isfile(ext_path):
        return ext_path

    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Proxy Auth",
        "permissions": [
            "proxy",
            "webRequest",
            "webRequestAuthProvider",
            "<all_urls>"
        ],
        "background": {
            "scripts": ["background.js"]
        },
        "minimum_chrome_version": "22.0.0"
    }
    """

    background_js = f"""
    var config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "http",
                host: "{host}",
                port: parseInt("{port}")
            }},
            bypassList: ["localhost", "127.0.0.1"]
        }}
    }};

    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

    function callbackFn(details) {{
        return {{
            authCredentials: {{
                username: "{username}",
                password: "{password}"
            }}
        }};
    }}

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {{urls: ["<all_urls>"]}},
        ['blocking']
    );
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "manifest.json"), "w") as f:
            f.write(manifest_json)
        with open(os.path.join(tmpdir, "background.js"), "w") as f:
            f.write(background_js)

        with zipfile.ZipFile(ext_path, 'w', zipfile.ZIP_DEFLATED) as zp:
            zp.write(os.path.join(tmpdir, "manifest.json"), "manifest.json")
            zp.write(os.path.join(tmpdir, "background.js"), "background.js")

    return ext_path

# ============================================================
# Bot Class
# ============================================================

class Bot:
    def __init__(self, username, password, target, message, driver="Chrome", cookie=False, counter=None,
                 is_instagrapi_request=False, is_selenium_mass_dm=False):
        self.username = username
        self.password = password
        self.target = target
        self.message = message
        self.cookie = cookie
        self.is_instagrapi_request = is_instagrapi_request
        self.is_selenium_mass_dm = is_selenium_mass_dm
        self.counter = counter

        if not is_instagrapi_request:
            if driver == "Chrome":
                chrome_service = Service('chromedriver.exe')
                chrome_options = webdriver.ChromeOptions()
                chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
                chrome_options.add_argument('--log-level=3')
                chrome_options.add_argument("--start-maximized")
                # Headless is NOT used – full UI

                if PROXY_HOST and PROXY_PORT:
                    ext_path = create_proxy_extension(PROXY_HOST, PROXY_PORT, PROXY_LOGIN, PROXY_PASSWORD)
                    chrome_options.add_extension(ext_path)

                self.bot = webdriver.Chrome(options=chrome_options, service=chrome_service)
            elif driver == "Firefox":
                gecko_service = Service('geckodriver.exe')
                gecko_options = webdriver.FirefoxOptions()
                gecko_options.add_argument("--start-maximized")

                if PROXY_HOST and PROXY_PORT:
                    gecko_options.set_preference("network.proxy.type", 1)
                    gecko_options.set_preference("network.proxy.http", PROXY_HOST)
                    gecko_options.set_preference("network.proxy.http_port", PROXY_PORT)
                    gecko_options.set_preference("network.proxy.ssl", PROXY_HOST)
                    gecko_options.set_preference("network.proxy.ssl_port", PROXY_PORT)
                    gecko_options.set_preference("network.proxy.ftp", PROXY_HOST)
                    gecko_options.set_preference("network.proxy.ftp_port", PROXY_PORT)

                self.bot = webdriver.Firefox(options=gecko_options, service=gecko_service)
            else:
                raise ValueError("Unsupported driver")

            self.base_url = "https://www.instagram.com/"
            self.login()

    # ---------- Login and helpers ----------
    def challenge(self):
        time.sleep(3)
        try:
            challenge = self.bot.execute_script("""
                return window.location.href.includes("/challenge/") || 
                    window.location.href.includes("auth_platform/codeentry/") ||
                    window.location.href.includes("auth_platform/text_captcha/") ||
                    window.location.href.includes("auth_platform/") ||
                    window.location.href.includes("consent/") ||
                    window.location.href.includes("accounts/suspended/") ||
                    window.location.href.includes("auth_platform/no_challenge//") 
            """)
        except (InvalidSessionIdException, WebDriverException):
            raise SessionDeadError("Browser session dead during challenge check")
        if challenge:
            time.sleep(2)
            self.bot.execute_script("""
                Array.from(document.querySelectorAll("[role='button']")).forEach((button)=>{
                    if(button.innerText == "This Was Me"){
                        button.click();
                    }
                })
            """)
        return challenge

    def invalid_login_message_present(self, timeout=5):
        try:
            WebDriverWait(self.bot, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//span[contains(., 'The login information you entered is incorrect')]"))
            )
            return True
        except TimeoutException:
            return False
        except (InvalidSessionIdException, WebDriverException):
            raise SessionDeadError("Browser session dead during login check")

    def login(self):
        try:
            self.bot.get(self.base_url)
        except (InvalidSessionIdException, WebDriverException):
            raise SessionDeadError("Browser session dead while loading base URL")

        try:
            login_button = WebDriverWait(self.bot, 5, ignored_exceptions=(StaleElementReferenceException,)).until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[normalize-space()='Log in']]"))
            )
            login_button.click()
        except:
            print(f"\n{WARNING}Login link not found, proceeding...{ENDC}\n")

        cookie_path = f'cookies/{self.username}.json'
        if os.path.isfile(cookie_path):
            try:
                with open(cookie_path, 'r') as f:
                    cookie = load(f)
                    self.bot.add_cookie(cookie)
            except:
                pass

        try:
            enter_username = WebDriverWait(self.bot, 20).until(EC.presence_of_element_located((By.NAME, "email")))
            enter_username.send_keys(self.username)
            enter_password = WebDriverWait(self.bot, 20).until(EC.presence_of_element_located((By.NAME, "pass")))
            enter_password.send_keys(self.password)
            enter_password.send_keys(Keys.RETURN)
        except Exception as e:
            print(f"{FAIL}Failed to enter login credentials: {e}{ENDC}")
            self.bot.quit()
            return

        if self.invalid_login_message_present():
            print(f"{FAIL}Invalid login credentials for: {self.username}{ENDC}")
            self.bot.quit()
            return

        # Check if account is suspended or challenged
        current_url = self.bot.current_url
        if not self.cookie and ("suspended" in current_url or "challenge" in current_url or "auth_platform" in current_url):
            print(f"{FAIL}Account {self.username} is suspended or requires challenge – skipping.{ENDC}")
            self.bot.quit()
            raise AccountUnavailableError(f"Account {self.username} is unavailable")

        # If challenge is present, prompt for manual intervention (only if cookie mode is False)
        if self.challenge() and self.cookie:
            print(f"\n{WARNING}Challenge detected for {self.username}. Please complete manually.{ENDC}")

            while self.challenge():
                operation = input("1. Press ↵ Enter when done with challenge.\n2. Press 2 to skip account\n:")
                if operation == "2":  
                    self.bot.close()  
                    return

        # After manual challenge, re-check URL for suspension (just in case)
        current_url = self.bot.current_url
        if "suspended" in current_url or "challenge" in current_url or "auth_platform" in current_url:
            print(f"{FAIL}Account {self.username} still unavailable after challenge – skipping.{ENDC}")

            if self.cookie:
                return 
            else:
                self.bot.quit()
                raise AccountUnavailableError(f"Account {self.username} is unavailable")

        if self.cookie:
            with open(cookie_path, 'w') as f:
                dump(self.bot.get_cookie('sessionid'), f)
            self.bot.quit()
            return

    # ---------- Instagrapi send_message (unchanged) ----------
    def send_message(self, target, counter):
        user_ids = get_saved_user_ids(target)
        if not user_ids:
            print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{self.username}]{ENDC} {WARNING}-{ENDC} No usernames to process.")
            return 0, True

        history_file = f"./cache/{target}.json"  # Shared history
        last_line = 0
        if os.path.isfile(history_file):
            try:
                with open(history_file, 'r') as f:
                    data = load(f)
                    last_line = data.get('line', 0)
            except:
                pass

        cl = InstagrapiClient()
        proxy_url = f"http://{PROXY_LOGIN}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}"
        cl.set_proxy(proxy_url)

        session_id = get_saved_session_id(self.username)
        if not session_id:
            print(f"{FAIL}No session ID for {self.username}. Run cookie generation first.{ENDC}")
            return 0, False
        cl.login_by_sessionid(session_id)

        sent_count = 0
        completed = True
        for idx, user_id in enumerate(user_ids):
            if idx < last_line:
                continue
            if sent_count >= MAX_MESSAGE_PER_ROTATION:
                completed = False
                break

            try:
                cl.direct_send(text=self.message, user_ids=[user_id])
                print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{self.username}]{ENDC} {WARNING}-{ENDC} sent message to {WARNING}->{ENDC} {OKCYAN}{user_id}{ENDC}")
                sent_count += 1
                with open(history_file, 'w') as f:
                    dump({"line": idx + 1}, f)
                time.sleep(random.uniform(3, 7))
            except DirectMessageRequestsDisabled:
                print(f"{HEADER}[Account Group {counter}]{ENDC}{FAIL}The recipient {user_id} does not accept new DM requests.{ENDC}")
                with open(history_file, 'w') as f:
                    dump({"line": idx + 1}, f)
                continue
            except Exception as e:
                LOGFILE.write(f"[{self.username}] ERROR sending to {user_id}: {e}\n")
                print(f"{HEADER}[Account Group {counter}]{ENDC}{FAIL}Error sending to {user_id}: {e}{ENDC}")
                continue

        if sent_count == 0 and last_line >= len(user_ids):
            completed = True
        elif sent_count < MAX_MESSAGE_PER_ROTATION and last_line + sent_count >= len(user_ids):
            completed = True

        return sent_count, completed

    # ---------- Selenium send_message_via_selenium (FIXED) ----------
    def send_message_via_selenium(self, target, counter):
        """
        Send direct messages using Selenium – shared history and fatal error detection.
        """
        file_path = f"./targetted_mass_dm/{target}.txt"
        if not os.path.isfile(file_path):
            print(f"{HEADER}[Account Group {counter}]{ENDC}{FAIL}Target file {file_path} not found.{ENDC}")
            return 0, True

        with open(file_path, 'r') as f:
            usernames = [line.strip() for line in f if line.strip()]

        if not usernames:
            print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{self.username}]{ENDC} {WARNING}-{ENDC} No usernames to process.")
            return 0, True

        # Shared history file for this target
        history_file = f"./targetted_mass_dm/cache/{target}.json"
        last_line = 0
        if os.path.isfile(history_file):
            try:
                with open(history_file, 'r') as f:
                    data = load(f)
                    last_line = data.get('line', 0)
            except:
                pass

        sent_count = 0
        completed = True

        for idx, username in enumerate(usernames):
            if idx < last_line:
                continue
            if sent_count >= MAX_MESSAGE_PER_ROTATION:
                completed = False
                break

            if not username:
                continue

            try:
                # Navigate to new message page
                self.bot.get(self.base_url + "direct/new/")
                time.sleep(4)

                # Remove "Not Now" popup
                self.bot.execute_script("""
                    Array.from(document.querySelectorAll('button')).forEach(function(button){
                        if(button.innerText == 'Not Now'){
                            button.click();
                        }
                    });
                """)
                time.sleep(1)

                # Click pencil if needed (sometimes direct/new/ already has it)
                self.bot.execute_script("""
                    Array.from(document.querySelectorAll("[role='button']")).forEach(function(button){
                        if(button.querySelector("[aria-label='New message']")){
                            button.click();
                        }
                    });
                """)

                # Wait for search input
                search_input = WebDriverWait(self.bot, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="queryBox"]'))
                )
                self.bot.execute_script("arguments[0].click();", search_input)
                search_input.clear()
                search_input.send_keys(username)
                time.sleep(4)

                # Wait for results
                WebDriverWait(self.bot, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="listbox"] [role="option"]'))
                )

                # Select exact match
                options = self.bot.find_elements(By.CSS_SELECTOR, '[role="listbox"] [role="option"]')
                user_found = False
                for option in options:
                    spans = option.find_elements(By.CSS_SELECTOR, 'span[dir="auto"]')
                    if any(el.text.strip() == username for el in spans):
                        checkbox = option.find_element(By.CSS_SELECTOR, 'input[name="IGDRecipientContactSearchResultCheckbox"]')
                        self.bot.execute_script("arguments[0].click();", checkbox)
                        user_found = True
                        break

                if not user_found:
                    print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{self.username}]{ENDC} {WARNING}-{ENDC}{FAIL} Could not find{ENDC} {WARNING}->{ENDC} {OKCYAN}{username}{ENDC}")
                    # Skip user – update history
                    with open(history_file, 'w') as f:
                        dump({"line": idx + 1}, f)
                    continue

                # Click Chat
                chat_btn = WebDriverWait(self.bot, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and normalize-space()='Chat']"))
                )
                self.bot.execute_script("arguments[0].click();", chat_btn)
                time.sleep(4)

                # Send message
                msg_box = WebDriverWait(self.bot, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="textbox"][contenteditable="true"][data-lexical-editor="true"]'))
                )
                self.bot.execute_script("arguments[0].focus();", msg_box)
                self.bot.execute_script("""
                    const editor = arguments[0];
                    const message = arguments[1];
                    editor.focus();
                    const selection = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(editor);
                    range.collapse(false);
                    selection.removeAllRanges();
                    selection.addRange(range);
                    const textNode = document.createTextNode(message);
                    range.insertNode(textNode);
                    range.setStartAfter(textNode);
                    range.collapse(true);
                    selection.removeAllRanges();
                    selection.addRange(range);
                    editor.dispatchEvent(new InputEvent('input', {
                        inputType: 'insertText',
                        data: message,
                        bubbles: true
                    }));
                """, msg_box, self.message)

                msg_box.send_keys(Keys.ENTER)
                print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{self.username}]{ENDC} {WARNING}-{ENDC} sent message to {WARNING}->{ENDC} {OKCYAN}{username}{ENDC}")

                sent_count += 1
                # Update shared history after successful send
                with open(history_file, 'w') as f:
                    dump({"line": idx + 1}, f)

                time.sleep(random.uniform(5, 10))

            except (InvalidSessionIdException, WebDriverException, ConnectionError) as e:
                # Fatal: browser session is dead – DO NOT UPDATE HISTORY
                LOGFILE.write(f"[{self.username}] FATAL session error on {username}: {e}\n")
                print(f"{HEADER}[Account Group {counter}]{ENDC}{FAIL}Fatal session error on {username}: {e}{ENDC}")
                raise SessionDeadError(f"Session died at user {username}") from e

            except Exception as e:
                # Non-fatal error – skip this user and continue
                LOGFILE.write(f"[{self.username}] Error with {username}: {e}\n")
                print(f"{HEADER}[Account Group {counter}]{ENDC}{FAIL}Error with {username}: {e}{ENDC}")
                with open(history_file, 'w') as f:
                    dump({"line": idx + 1}, f)
                continue

        if sent_count == 0 and last_line >= len(usernames):
            completed = True
        elif sent_count < MAX_MESSAGE_PER_ROTATION and last_line + sent_count >= len(usernames):
            completed = True

        return sent_count, completed

    # ---------- Browser cleanup ----------
    def quit_browser(self):
        if hasattr(self, 'bot') and self.bot:
            try:
                self.bot.quit()
            except:
                pass

    def sigkill(self):
        if hasattr(self, 'bot') and self.bot:
            try:
                pid = self.bot.capabilities.get('moz:processID')
                if pid:
                    for proc in psutil.process_iter():
                        if proc.pid == pid:
                            proc.kill()
            except:
                pass

# ============================================================
# Thread worker functions with retry logic & account availability check
# ============================================================

def init(accounts, target, counter):
    state = {username: {'sent_today': 0, 'completed': False, 'fail_count': 0} for username in accounts}

    while True:
        active = [u for u in accounts if not state[u]['completed'] and state[u]['sent_today'] < MAX_MESSAGE_PER_DAY]
        if not active:
            break

        for username in active:
            if state[username]['completed'] or state[username]['sent_today'] >= MAX_MESSAGE_PER_DAY:
                continue

            bot = None
            try:
                bot = Bot(username, accounts[username], target, MESSAGE,
                          driver="Chrome", counter=counter, is_instagrapi_request=True)

                print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{username}]{ENDC} {WARNING}-{ENDC} Sending messages...")
                sent_count, completed = bot.send_message(target, counter)

                state[username]['sent_today'] += sent_count
                if completed:
                    state[username]['completed'] = True
                    print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{username}]{ENDC} {WARNING}-{ENDC} Completed all followers.")
                else:
                    print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{username}]{ENDC} {WARNING}-{ENDC} Sent {sent_count} messages this rotation.")
                state[username]['fail_count'] = 0  # reset on success

            except AccountUnavailableError as aue:
                print(f"{HEADER}[Account Group {counter}]{ENDC}{FAIL}[{username}] Account unavailable: {aue}{ENDC}")
                state[username]['completed'] = True  # skip permanently

            except Exception as e:
                LOGFILE.write(f"[{username}] ERROR: {e}\n")
                print(f"{HEADER}[Account Group {counter}]{ENDC}{FAIL}[{username}] ERROR -> {e}{ENDC}")
                # Not a fatal session error for instagrapi, just continue
            finally:
                if bot:
                    bot.quit_browser()
                time.sleep(random.uniform(3, 7))

        time.sleep(random.uniform(2, 5))

    print(f"{HEADER}[Thread {counter}]{ENDC}{OKGREEN}[Account Group {counter}]{ENDC} {WARNING}-{ENDC}{OKGREEN}All accounts finished for today.{ENDC}")

def init_selenium(accounts, target, counter):
    state = {username: {'sent_today': 0, 'completed': False, 'fail_count': 0} for username in accounts}

    while True:
        active = [u for u in accounts if not state[u]['completed'] and state[u]['sent_today'] < MAX_MESSAGE_PER_DAY]
        if not active:
            break

        for username in active:
            if state[username]['completed'] or state[username]['sent_today'] >= MAX_MESSAGE_PER_DAY:
                continue

            bot = None
            try:
                bot = Bot(username, accounts[username], target, MESSAGE,
                          driver="Chrome", counter=counter, is_selenium_mass_dm=True)

                # If challenge is detected during init, the login will raise AccountUnavailableError
                # so we don't need to call bot.challenge() again here.

                print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{username}]{ENDC} {WARNING}-{ENDC} Sending messages via Selenium...")
                sent_count, completed = bot.send_message_via_selenium(target, counter)

                state[username]['sent_today'] += sent_count
                if completed:
                    state[username]['completed'] = True
                    print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{username}]{ENDC} {WARNING}-{ENDC} Completed all targeted usernames.")
                else:
                    print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{username}]{ENDC} {WARNING}-{ENDC} Sent {sent_count} messages this rotation.")
                state[username]['fail_count'] = 0  # reset on success

            except AccountUnavailableError as aue:
                print(f"{HEADER}[Account Group {counter}]{ENDC}{FAIL}[{username}] Account unavailable: {aue}{ENDC}")
                state[username]['completed'] = True  # skip permanently

            except SessionDeadError as sde:
                # Fatal session error – retry up to 3 times
                state[username]['fail_count'] += 1
                LOGFILE.write(f"[{username}] Session dead (attempt {state[username]['fail_count']}): {sde}\n")
                print(f"{HEADER}[Account Group {counter}]{ENDC}{FAIL}[{username}] Session died (attempt {state[username]['fail_count']}/3). Retrying...{ENDC}")
                if state[username]['fail_count'] >= 3:
                    print(f"{HEADER}[Account Group {counter}]{ENDC}{FAIL}[{username}] Too many failures. Skipping account for today.{ENDC}")
                    state[username]['completed'] = True  # give up on this account
                # Do not update history – the shared history remains unchanged, so other accounts will process the pending users.
                # We will retry the same account in the next loop iteration.
                # The browser is already dead; we'll recreate it on next attempt.

            except Exception as e:
                LOGFILE.write(f"[{username}] ERROR: {e}\n")
                print(f"{HEADER}[Account Group {counter}]{ENDC}{FAIL}[{username}] ERROR -> {e}{ENDC}")
                # Non-fatal, continue to next account
            finally:
                if bot:
                    bot.quit_browser()
                time.sleep(random.uniform(5, 10))

        time.sleep(random.uniform(3, 6))

    print(f"{HEADER}[Thread {counter}]{ENDC}{OKGREEN}[Account Group {counter}]{ENDC} {WARNING}-{ENDC}{OKGREEN}Selenium batch finished.{ENDC}")

# ============================================================
# Rotation function
# ============================================================

def rotation(targeted_usernames=False):
    print(f"{HEADER}START\n{'='*75}{ENDC}")

    if targeted_usernames:
        print(f"\n{OKGREEN}Initialising targeted usernames...{ENDC}\n")

    accounts = account()
    if not accounts:
        print(f"{FAIL}No accounts found in accounts_new.txt{ENDC}")
        return

    targets_list = targets(targeted_usernames)
    if not targeted_usernames and len(targets_list) != NUMBER_OF_THREADS_:
        print(f"{FAIL}Your targets.txt must have exactly {NUMBER_OF_THREADS_} targets.{ENDC}")
        return

    account_keys = list(accounts.keys())
    account_groups = [account_keys[i:i+ACCOUNTS_PER_THREAD] for i in range(0, len(account_keys), ACCOUNTS_PER_THREAD)]
    account_groups = account_groups[:NUMBER_OF_THREADS_]

    threads = []
    for i, group in enumerate(account_groups):
        if not group:
            continue
        counter = i + 1
        group_accounts = {uname: accounts[uname] for uname in group}
        if targeted_usernames:
            if targets_list:
                target = targets_list[i % len(targets_list)]
            else:
                target = f"batch_{counter}"
        else:
            if targets_list:
                target = targets_list[i % len(targets_list)]
            else:
                target = input(f"Enter target for Account Group {counter}: ").strip()
                if not target:
                    target = "default"

        print(f"{HEADER}[Account Group {counter}]{ENDC} - {OKGREEN}{target} running with {len(group_accounts)} accounts{ENDC}")

        worker = init_selenium if targeted_usernames else init
        thread = threading.Thread(target=worker, name=f"Account Group {counter}",
                                  args=(group_accounts, target, counter))
        threads.append(thread)

    print(f"\n{OKGREEN}RUNNING\n{'='*75}{ENDC}")

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    LOGFILE.close()

# ============================================================
# Main menu
# ============================================================

if __name__ == "__main__":
    for d in ["./cache", "./cookies", "./users", "./targetted_mass_dm/cache"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    print(f"""{OKGREEN}
     _____          _                                        _           
    |_   _|        | |                                      | |          
      | | _ __  ___| |_ __ _   _ __ ___   __ _ ___ ___    __| |_ __ ___  
      | || '_ \/ __| __/ _` | | '_ ` _ \ / _` / __/ __|  / _` | '_ ` _ \ 
     _| || | | \__ \ || (_| | | | | | | | (_| \__ \__ \ | (_| | | | | | |
     \___/_| |_|___/\__\__,_| |_| |_| |_|\__,_|___/___/  \__,_|_| |_| |_|
                                                                         
    {ENDC}""")

    operation = input(
        f"\n\n{HEADER}Operations:{ENDC}"
        f"\n{OKGREEN}-> 1. Fetch followers of target accounts"
        "\n-> 2. Clear fetched followers of target accounts"
        f"\n-> 3. Run mass dm (instagrapi)"
        f"\n-> 4. Generate cookies for bot accounts"
        f"\n-> 5. Find user by username"
        f"\n-> 6. Run mass dm (Targeted usernames) -> Via selenium"
        f"\n-> 7. Exit{ENDC}"
        "\n: "
    )

    if operation == "3":
        try:
            rotation()
        except KeyboardInterrupt:
            print(f"{OKGREEN}Exiting....{ENDC}")
            exit(1)
        except Exception as e:
            LOGFILE.write(f"[ROTATION] - {e}\n")
            print(f"{FAIL}Something went wrong...{ENDC}\n{WARNING}Check your log files...{ENDC}")
        finally:
            LOGFILE.close()

    elif operation == "2":
        clear_fetched_followers()

    elif operation == "1":
        from followers import fetch_target_account_followers
        fetch_target_account_followers()

    elif operation == "4":
        from cookie import generate_cookies
        generate_cookies()

    elif operation == "5":
        find_user()

    elif operation == "6":
        try:
            if not os.path.isfile("targetted_mass_dm/targetted_usernames.txt"):
                print(f"{FAIL}You need a targetted_usernames.txt file in ./targetted_mass_dm{ENDC}")
            else:
                existing = [f for f in os.listdir("targetted_mass_dm") if f.startswith("batch_") and f.endswith(".txt")]
                if not existing:
                    chunk_and_split_targetted_followers()
                rotation(targeted_usernames=True)
        except KeyboardInterrupt:
            print(f"{OKGREEN}Exiting....{ENDC}")
            exit()
        except Exception as e:
            LOGFILE.write(f"[ROTATION] - {e}\n")
            print(f"{FAIL}Something went wrong...{ENDC}\n{WARNING}Check your log files...{ENDC}")
        finally:
            LOGFILE.close()

    elif operation == "7":
        exit()

    else:
        print(f"\n{FAIL}Invalid option entered{ENDC}\n")