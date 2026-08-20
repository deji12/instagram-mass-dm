# OS, PSUTIL, Regular Expression & Time Dependencies
import os
import json
import psutil
import re
import time
from pathlib import Path
import shutil

# Selenium Dependencies
from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys 
from selenium.common.exceptions import JavascriptException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.service import Service

# Threading & Sys
from itertools import zip_longest
from sys import exit
import threading

# JSON
from json import dump, load
from json.decoder import JSONDecodeError

from hikerapi import Client as HikerClient
from instagrapi import Client as InstagrapiClient
from instagrapi.exceptions import DirectMessageRequestsDisabled

# Configurations
from configuration import *

# Services
gecko_service = Service('geckodriver.exe')
chrome_service = Service('chromedriver.exe')

class Bot:
    def __init__(self, username, password, target, message, driver="Chrome", cookie=False, counter=None, is_instagrapi_request=False):
        # Initialized variables
        self.username = username
        self.password = password
        self.target = target
        self.message = message
        self.cookie = cookie
        self.is_instagrapi_request = is_instagrapi_request

        if not is_instagrapi_request and cookie:

            # Setting up Chrome with Options
            if driver == "Chrome":
                chrome_options = webdriver.ChromeOptions()
                # if self.cookie is False: 
                #     chrome_options.add_argument('--headless=new')

                chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
                chrome_options.add_argument('--log-level=3')
                chrome_options.add_argument("--start-maximized")
                driver = webdriver.Chrome(options=chrome_options, service=chrome_service)

            # Setting up Firefox with options
            elif driver == "Firefox":
                # Setting up Firefox with Options
                gecko_options = webdriver.FirefoxOptions()
                gecko_options.add_argument("--start-maximized")
                # gecko_options.add_argument("--disable-infobars")
                # gecko_options.add_argument("--disable-extensions")
                # gecko_options.add_argument('--no-sandbox')
                # gecko_options.add_argument('--disable-application-cache')
                # gecko_options.add_argument('--disable-gpu')
                # gecko_options.add_argument("--disable-dev-shm-usage")
                # if self.cookie is False: gecko_options.add_argument('--headless')
                # gecko_options.add_argument('--log-level=3')
                driver = webdriver.Firefox(options=gecko_options, service=gecko_service)

            # Declared variables
            self.base_url = "https://www.instagram.com/"
            self.bot = driver

            # Login specified user
            self.login(counter)

    def challenge(self):
        # Detect challenge
        # Delay
        if self.cookie is True: time.sleep(5)

        # Try to beat the challenge if it is a click challange
        challenge = self.bot.execute_script("""
            return window.location.href.includes("/challenge/") || 
                window.location.href.includes("auth_platform/codeentry/") ||
                window.location.href.includes("accounts/suspended/") ||
                window.location.href.includes("auth_platform/no_challenge//") 
        """)
        
        if challenge:
            # Delay for a bit
            time.sleep(3)

            # Attempt to beat challenge
            self.bot.execute_script("""
                Array.from(document.querySelectorAll("[role='button']")).forEach((button)=>{
                    if(button.innerText == "This Was Me"){
                        button.click();
                    }
                })
            """)

        return challenge

    def invalid_login_message_present(self, timeout=5) -> bool:
        try:
            WebDriverWait(self.bot, timeout).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//span[contains(., 'The login information you entered is incorrect')]"
                    )
                )
            )
            return True

        except TimeoutException:
            return False

    def login(self, counter=None):
        """
            Log into the IG account, detect challenge and use
            __get_followers to extract target followers.
        """
        # Get the base url
        self.bot.get(self.base_url)

        try:

            login_button = WebDriverWait(
                self.bot,
                5,
                ignored_exceptions=(StaleElementReferenceException,)
            ).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[.//span[normalize-space()='Log in']]"
                    )
                )
            )
            login_button.click()
        except:
            print(f"\n{WARNING}Login link not found, proceeding...{ENDC}\n")
    
        # Check if there is existing cookie
        stored_session = None
        if f'{self.username}.json' in os.listdir('./cookies'): 
            # Get stored session
            stored_session = open(f'cookies/{self.username}.json')

            # Add cookie
            try:
                cookie = load(stored_session)
                self.bot.add_cookie(cookie)
                stored_session.close()
            except JSONDecodeError:
                # No valid cookie for the user
                pass

        # Insert username
        enter_username = WebDriverWait(self.bot, 20).until(EC.presence_of_element_located((By.NAME, "email")))
        enter_username.send_keys(self.username)

        # Insert password
        enter_password = WebDriverWait(self.bot, 20).until(EC.presence_of_element_located((By.NAME, "pass")))
        enter_password.send_keys(self.password)

        # Hit the return key and submit login details
        enter_password.send_keys(Keys.RETURN)

        # Wait for possible page load
        if self.invalid_login_message_present():
            print(f"{FAIL}Invalid login credentials provided for: {self.username}{ENDC}")
            self.bot.close()
            return

        # Wait for page to load before checking url
        # time.sleep(5)

        # Detect challenge and Wait for user to complete challenge before continuing
        while self.challenge() and self.cookie is True: 
            print(f"{FAIL}Automated behaviour has been detected by Instagram.{ENDC}\n{WARNING}Complete login challenge for {self.username} to proceed.{ENDC}")

            operation = input("1. Press ↵ Enter when done with challenge.\n2. Press 2 to skip account\n:")
            if operation == "2":  
                self.bot.close()  
                return
            

        if self.challenge() and self.cookie is False: 
            return "Challenge"

        # Store cookie and overwrite preexisting cookie
        stored_session = open(f'cookies/{self.username}.json', 'w')
        dump(self.bot.get_cookie('sessionid'), stored_session)
        stored_session.close()

        # If it is a cookie script
        if self.cookie is True: 
            self.bot.close()
            return

        # Use get_followers if they do not exist for specified user
        target = self.target if self.target is not None else self.username
        
        # Get followers
        self.__get_followers(target, counter)

    def get_saved_session_id(self):
        with open(f"cookies/{self.username}.json", 'r', encoding='utf-8') as f:
            data = load(f)
            return data.get('value')

    def send_message(self, target, counter=None, same_target=None):
        """
            Send a direct message to an account.

            private method -> only accessible within class
        """

        if not self.is_instagrapi_request:
            # Go to messages
            self.bot.get(self.base_url + "direct/inbox")
            time.sleep(5)

            # Remove pop up if any
            self.bot.execute_script(
                """
                Array.from(document.querySelectorAll('button')).forEach(function(button){
                    // Check if 'Not Now'
                    if(button.innerText == 'Not Now'){
                        button.click();
                    }
                });
            """
            )
            time.sleep(2)

            # Clicks on pencil icon
            self.bot.execute_script(
                """
                Array.from(document.querySelectorAll("[role='button']")).forEach(function(button){
                    // Check for the pencil icon
                    if(button.querySelector("[aria-label='New message']")){
                        button.click();
                    }
                });
            """
            )
            time.sleep(7)
            
            # Get the target followers from the preexisting checks
            # get_follower_usernames = open(f'./users/{target}.txt', 'r')

            # Get all the usernames
            # usernames = get_follower_usernames.readlines()
            # usernames = [u.replace("\n", "") for u in usernames]

        user_ids = get_saved_user_ids(target)

        # Checks if previous history exists
        path = f"./cache/{target}.{NUMBER_OF_THREADS}.{counter}.json" if ONE_TARGET_THREADS else f"./cache/{target}.json"

        # Calculate history split
        if ONE_TARGET_THREADS:
            quotient, remainder = divmod(len(user_ids), NUMBER_OF_THREADS)
            split = [quotient for i in range(NUMBER_OF_THREADS - remainder)] + [quotient + 1 for j in range(remainder)]
            shared = [sum(split[:i]) for i in range(0,10)]

        if os.path.isfile(path) and os.access(path, os.R_OK):
            # Restore from previous history
            print (f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{self.username}]{ENDC} {WARNING}-{ENDC} Restoring history from last run.")
            file_json = open(path, "r")
            history = load(file_json)
            #usernames = usernames[history["line"]:shared[counter-1]] if ONE_TARGET_THREADS else usernames[history["line"]:]

        else:
            # Create new history
            # Store and save in cache
            with open(path, 'a', encoding='utf-8') as f: dump({
                "user_id": user_ids[shared[counter-1]] if ONE_TARGET_THREADS else user_ids[0],
                "line": shared[counter-1] if ONE_TARGET_THREADS else 1
            }, f, ensure_ascii=False, indent=4)

            history = None
                
        # Make sure to break if username file is empty -> messages have been sent to all users in this case
        if not user_ids:
            print(
                f"{HEADER}[Account Group {counter}]{ENDC}"
                f"{OKGREEN}[{self.username}]{ENDC} "
                f"{WARNING}-{ENDC} No usernames to process."
            )
            return 0, True

        # Number of messages sent
        message_count = 0
        completed = True
        
        # History Number
        hcount = 0


        cl = InstagrapiClient()
            
        # Use your proxy here if required
        proxy_url = (
            f"http://{PROXY_LOGIN}:"
            f"{PROXY_PASSWORD}@"
            f"{PROXY_HOST}:"
            f"{PROXY_PORT}"
        )

        cl.set_proxy(proxy_url)

        # Authenticate instagrapi using the browser sessionid
        cl.login_by_sessionid(
            self.get_saved_session_id()
        )

        for user_id in user_ids:

            hcount += 1

            if not user_id or user_id in PROCESSED_USER_IDS:
                continue

            # Thread range
            if ONE_TARGET_THREADS:
                if hcount < shared[counter - 1]:
                    continue

                if counter < NUMBER_OF_THREADS and hcount > shared[counter]:
                    break

            # Restore history
            if history and hcount < history["line"]:
                continue

            # IMPORTANT: check BEFORE marking this ID processed
            if message_count >= MAX_MESSAGE_PER_ROTATION:
                completed = False
                break

            PROCESSED_USER_IDS.append(user_id)

            try:
                cl.direct_send(
                    text=MESSAGE,
                    user_ids=[user_id]
                )

                print(
                    f"{HEADER}[Account Group {counter}]{ENDC}"
                    f"{OKGREEN}[{self.username}]{ENDC} "
                    f"{WARNING}-{ENDC} sent message to "
                    f"{WARNING}->{ENDC} {OKCYAN}{user_id}{ENDC}"
                )

            except DirectMessageRequestsDisabled:
                print(
                    f"{HEADER}[Account Group {counter}]{ENDC}"
                    f"{FAIL}The recipient {user_id} does not accept "
                    f"new Direct message requests.{ENDC}"
                )
                continue

            except Exception as e:
                print(
                    f"\n{FAIL}An error: {ENDC}\n"
                    f"{WARNING}{e}{ENDC}"
                )
                continue

            message_count += 1

            HISTORY.write(
                f"[Account Group {counter}]"
                f"[{self.username}] - sent message to -> {user_id}\n"
            )

            data = {
                "user_id": user_id,
                "line": hcount
            }

            with open(path, 'w', encoding='utf-8') as f:
                dump(
                    data,
                    f,
                    ensure_ascii=False,
                    indent=4
                )
                    

        # get_follower_usernames.close()

        return message_count, completed
    
    def sigkill(self):
        """
        Kill the current process with SIGKILL pre-emptively
        checking whether PID has been reused.
        """
        # Find and quit the instance with the PID
        capabilities = self.bot.capabilities
        pid = capabilities['moz:processID']

        for proc in psutil.process_iter():
            if proc.pid == pid: proc.kill()

    # Private method -> only accessible within class
    def __get_followers(self, target, counter=None):
        """
        Search for a .txt file with the current target.

        If found, the followers of that account has been scrapped previously.
        """
        if not f'{target}.txt' in os.listdir('./users'):
            # Remove 'Not Now' pop up if any
            time.sleep(2)
            self.bot.execute_script(
                """
                Array.from(document.querySelectorAll('button')).forEach(function(button){
                    // Check if 'Not Now'
                    if(button.innerText == 'Not Now'){
                        button.click();
                    }
                });
            """
            )
            time.sleep(2)

            # Go to profile page
            self.bot.get(f'{self.base_url}{target}')
            print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{self.username}]{ENDC} {WARNING}-{ENDC} Searching followers for {WARNING}->{ENDC} {OKCYAN}{target}{ENDC}")

            # Get toggle followers box and get count
            target_link = target.lower()
            user_followers = WebDriverWait(self.bot, 20).until(
                EC.presence_of_element_located((By.XPATH, f"//a[@href='/{target_link}/followers/']"))
            )
            user_followers.click()

            scroll_box = WebDriverWait(self.bot, 20).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'xyi19xy x1ccrb07 xtf3nb5 x1pc53ja x1lliihq x1iyjqo2 xs83m0k xz65tgg x1rife3k x1n2onr6')]"))
            )

            # Log to console
            followers_count = self.bot.execute_script(f"""return Number(document.querySelector("[href='/{target_link}/followers/'][role='link']").querySelector("span").getAttribute("title").replaceAll(",",""));""")
            if DEFAULT_NUMBER_OF_FOLLOWERS is not None: count = DEFAULT_NUMBER_OF_FOLLOWERS if int(followers_count) >= DEFAULT_NUMBER_OF_FOLLOWERS else int(followers_count)
            else: count = int(input(f"{target} has {followers_count} followers.\nHow many do you want to extract: "))
            print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{self.username}]{ENDC} {WARNING}-{ENDC} Scraping followers for {WARNING}->{ENDC} {OKCYAN}{target}{ENDC}")

            # Scroll the element
            last_count = 0
            while last_count < count:
                time.sleep(10)
                # Scroll down and return the height of scroll (JS script)
                last_count = self.bot.execute_script(f"""
                    var found = Number(document.querySelector("[role='dialog']").querySelectorAll("div[dir='auto']").length);
                    if(found < {count}) arguments[0].scrollTo(0, arguments[0].scrollHeight);
                    return Number(document.querySelector("[role='dialog']").querySelectorAll("div[dir='auto']").length);
                """, scroll_box)
            time.sleep(5)

            followers = self.bot.find_elements(By.XPATH, ".//a[contains(@href, '/') and contains(@class, 'notranslate _a6hd')]")

            # Creating new file for user's followers
            create_file_for_storing_usernames = open(f'./users/{target}.txt', 'a') 

            for i in followers:
                if i.get_attribute('href'):
                    get_follower_username = i.get_attribute('href').rstrip('/').split('/')[-1]

                    read_file_for_storing_usernames = open(f'users/{target}.txt', 'r')

                    if get_follower_username not in read_file_for_storing_usernames.read(): 
                    
                        create_file_for_storing_usernames.write(f"{get_follower_username}\n")
                        print(f"{HEADER}[Account Group {counter}]{ENDC}{OKGREEN}[{self.username}]{ENDC} {WARNING}-{ENDC} Stored follower username {WARNING}->{ENDC} {OKCYAN}{get_follower_username}{ENDC}")

                    read_file_for_storing_usernames.close()
                else:
                    continue

            create_file_for_storing_usernames.close()

# Create the cache directory (that stores cache data) if not created
if not 'cache' in os.listdir('.'): os.mkdir('./cache')

# Create the cookies directory (that stores cookies) if not created
if not 'cookies' in os.listdir('.'): os.mkdir('./cookies')

# Create the users directory (that stores usernames files) if not created
if not 'users' in os.listdir('.'): os.mkdir('./users')

# A list of processed usernames to prevent the threads from
# processing the same username more than once.
EMAIL_CREDENTIALS = {}
HISTORY = open("./cache/history.txt", "a")
LOGFILE = open("./cache/logs.txt", "a")
PROCESSED_USER_IDS = []

def account():
    """
        Extract accounts from the accounts.txt file.

        The username and password should be stored in
        this format: [username][password]
    """
    # Get the txt file
    if 'accounts_new.txt' not in os.listdir('.'): return print(f"{WARNING}ERROR: accounts.txt is not in main folder.{ENDC}")
    accounts = {}
    accounts_txt = open("accounts_new.txt", "r")

    # Saved accounts
    for details in accounts_txt.readlines(): 
        # Get the username and password [] brackets
        ordered = re.findall(r"\[(.*?)\]", details)
        accounts[f"{ordered[0]}"] = ordered[1]

        # Get email credentials
        try:
            EMAIL_CREDENTIALS[f"{ordered[0]}"] = {
                "email": ordered[2],
                "password": ordered[3]
            }
        except Exception: pass

    accounts_txt.close()

    return accounts

def get_saved_user_ids(target):
    with open(f"users/{target}.txt", "r") as f:
        return [user_id.strip() for user_id in f.readlines()]



# def send_message(username, session_id, message) -> list:

#     cl = InstagrapiClient()
    
#     # Use your proxy here if required
#     proxy_url = (
#         f"http://{PROXY_LOGIN}:"
#         f"{PROXY_PASSWORD}@"
#         f"{PROXY_HOST}:"
#         f"{PROXY_PORT}"
#     )

#     cl.set_proxy(proxy_url)

#     # Authenticate instagrapi using the browser sessionid
#     cl.login_by_sessionid(session_id)

#     user_ids = get_saved_user_ids(username)
    

def init(accounts, target, counter):

    message_counts = {
        username: 0
        for username in accounts
    }

    completed_accounts = set()

    while True:

        # Only accounts that still have work and have not hit daily limit
        active_accounts = [
            username
            for username in accounts
            if username not in completed_accounts
            and message_counts[username] < MAX_MESSAGE_PER_DAY
        ]

        # Nobody left to run
        if not active_accounts:
            break

        for username, password in accounts.items():

            # Don't run completed accounts again
            if username in completed_accounts:
                continue

            # Don't run accounts that reached daily limit
            if message_counts[username] >= MAX_MESSAGE_PER_DAY:
                continue

            try:

                bot = Bot(
                    username,
                    password,
                    target,
                    MESSAGE,
                    driver="Chrome",
                    counter=counter,
                    is_instagrapi_request=True
                )

                print(
                    f"{HEADER}[Account Group {counter}]{ENDC}"
                    f"{OKGREEN}[{username}]{ENDC} "
                    f"{WARNING}-{ENDC} "
                    f"Sending messages with {username}..."
                )

                # IMPORTANT:
                # send_message now returns TWO values
                sent_count, completed = bot.send_message(
                    target,
                    counter
                )

                # Count only messages actually sent
                message_counts[username] += sent_count

                # Account reached the end of the follower list
                if completed:

                    completed_accounts.add(username)

                    print(
                        f"{HEADER}[Account Group {counter}]{ENDC}"
                        f"{OKGREEN}[{username}]{ENDC} "
                        f"{WARNING}-{ENDC} "
                        f"Successfully sent message to all followers. "
                        f"Account marked complete."
                    )

                    continue

                # Account still has followers, but may have hit daily limit
                if message_counts[username] >= MAX_MESSAGE_PER_DAY:

                    print(
                        f"{HEADER}[Account Group {counter}]{ENDC}"
                        f"{OKGREEN}[{username}]{ENDC} "
                        f"{WARNING}-{ENDC} "
                        f"Daily limit for message sending reached "
                        f"{WARNING}->{ENDC} "
                        f"{MAX_MESSAGE_PER_DAY}"
                    )

                    continue

                time.sleep(5)

            except Exception as e:

                # Show the error instead of silently looping forever
                print(
                    f"{HEADER}[Account Group {counter}]{ENDC}"
                    f"{FAIL}[{username}] ERROR -> {e}{ENDC}"
                )

                LOGFILE.write(
                    f"[{username}][ERROR] {e}\n"
                )
                LOGFILE.flush()

    print(
        f"{HEADER}[Thread {counter}]{ENDC}"
        f"{OKGREEN}[Account Group {counter}]{ENDC} "
        f"{WARNING}-{ENDC}"
        f"{OKGREEN}Message(s) sent for today!{ENDC}"
    )

def targets():
    """
        Extract targets from txt.
    """
    # Get the targets
    target = []
    targets_txt = open("targets.txt", "r")

    # Extract targets from the file
    for t in targets_txt.readlines(): target.append(t.replace("\n",""))

    # Return targets
    targets_txt.close()
    return target

def rotation():
    """
        Implementation of account rotation between multiple
        threads.
    """
    # Get the target account(s)
    print(f"{HEADER}START\n{'='*75}{ENDC}")

    # Extract accounts
    accounts = account()

    # Account threads
    threads = []

    # Counter & Target
    counter, target = 1, None

    # Extract targets
    targetAll = None if targets() == [] else targets()

    # Ensure targets are enough for threads
    if len(targetAll) != NUMBER_OF_THREADS: 
        if ONE_TARGET_THREADS: pass
        else: return print(f"{FAIL}Your{ENDC} {WARNING}targets.txt{ENDC} {FAIL}file must have {NUMBER_OF_THREADS} targets.{ENDC}\n")

    # Distribute 10 accounts to each thread
    # number of accounts to run per thread
    accountGroups = list(zip_longest(*(iter(accounts.keys()),) * ACCOUNTS_PER_THREAD))
    for accountGroup in accountGroups:
        accountArg = {}
        for username in accountGroup:
            if username is not None: accountArg[username] = accounts[username]

        # Prompt for targets if targets.txt is empty
        try:
            if targetAll is None:
                while target is None:
                    target = input(f"Target Instagram for Group {counter}: ")
                    target = None if target == "" else target
            # Use extracted targets if any
            else:
                target = targetAll[0] if ONE_TARGET_THREADS else targetAll[counter - 1]
        except: continue

        # Create thread for running accounts
        thread = threading.Thread(target=init, name=f"Account Group {counter}", args=(accountArg, target, counter))

        # Show in terminal or console
        print(f"{HEADER}[{thread.name}]{ENDC} - {OKGREEN}{target} running with {len(thread._args[0])} accounts{ENDC}")

        # Add to threads
        threads.append(thread)

        # Increment counter
        counter += 1
        target = None

    # Start running
    print(f"\n{OKGREEN}RUNNING\n{'='*75}{ENDC}")

    # Run the threads
    try:
        for thread in threads:
            thread.start()

        for thread in threads: 
            thread.join()

    except Exception as e: 
        LOGFILE.write(f"[Runtime Error] {e}\n")

    except exceptions as e: 
        LOGFILE.write(f"[Runtime Error] {e}\n")

def clear_fetched_followers():
    users_folder = Path('/users/')

    for item in users_folder.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()  # Deletes files or symbolic links
            elif item.is_dir():
                shutil.rmtree(item)  # Deletes subfolders and their contents
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

if __name__ == "__main__":

    print(f"""{OKGREEN}
     _____          _                                        _           
    |_   _|        | |                                      | |          
      | | _ __  ___| |_ __ _   _ __ ___   __ _ ___ ___    __| |_ __ ___  
      | || '_ \/ __| __/ _` | | '_ ` _ \ / _` / __/ __|  / _` | '_ ` _ \ 
     _| || | | \__ \ || (_| | | | | | | | (_| \__ \__ \ | (_| | | | | | |
     \___/_| |_|___/\__\__,_| |_| |_| |_|\__,_|___/___/  \__,_|_| |_| |_|
                                                                         
                                                                         {ENDC}
                                                                                                                                                             
    """)

    operation = input(
        f"\n\n{HEADER}Operations:{ENDC}"
        f"\n{OKGREEN}-> 1. Fetch followers of target accounts"
        "\n-> 2. Clear fetched followers of target accounts"
        f"\n-> 3. Run mass dm"
        f"\n-> 4. Generate cookies for bot accounts"
        f"\n-> 5. Find user by username"
        f"\n-> 6. Exit{ENDC}"
        "\n: "
    )

    if operation == "3":
        
        print("\n")

        # Calling the function
        try:
            rotation()
        except KeyboardInterrupt:
            print(f"{OKGREEN}Exiting....{ENDC}")
            exit(1)
        except Exception as e: 
            LOGFILE.write(f"[ROTATION] - {e}\n")
            print(f"{FAIL}Something went wrong...{ENDC}\n{WARNING}Check your log files...{ENDC}")
        finally:
            # Close LOGFILE & HISTORY
            LOGFILE.close()
            HISTORY.close()

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
        # break
        exit()

    else:
        print(f"\n{FAIL}Invalid option entered{ENDC}\n")



# Program Flow: Login() -> get_followers() -> send_message()