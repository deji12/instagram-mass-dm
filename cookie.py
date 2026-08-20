"""
    USE TO MAKE ACCOUNT COOKIES

    For making consistent sessions across multiple devices.
"""
# Dependencies
from dm import account, Bot
from configuration import *

def generate_cookies():

    # Create cookies
    accounts = account()

    print("Generating cookies for accounts in accounts_new.txt:")
    for username, password in accounts.items(): 
        print(f"{OKGREEN}-> Getting cookie for {ENDC} -> {WARNING}{username}{ENDC}")
        Bot(username, password, "inn0web", "Gotten cookie!", driver="Chrome", cookie=True)