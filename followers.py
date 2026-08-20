import time
from json import dumps
import threading
from hikerapi import Client as HikerClient

# Configurations
from configuration import *

def get_followers_via_hiker(target, counter):

    file_path = f'./users/{target}.txt'

    hiker_client = HikerClient(token=HIKER_API_TOKEN)

    target_user_data = hiker_client.user_by_username_v2(target)
    followers_count = target_user_data['user']['follower_count']
    user_id = target_user_data['user']['pk']

    print(
        f"{HEADER}[Scrape Group {counter}]{ENDC}"
        f"{OKGREEN}[{target}]{ENDC} {WARNING}-{ENDC} "
        f"Searching followers for {WARNING}->{ENDC} "
        f"{OKCYAN}{target}{ENDC}"
    )

    if DEFAULT_NUMBER_OF_FOLLOWERS is not None:
        count = min(DEFAULT_NUMBER_OF_FOLLOWERS, followers_count)
    else:
        count = int(
            input(
                f"{target} has {followers_count} followers.\n"
                f"How many do you want to extract: "
            )
        )

    print(
        f"{HEADER}[Scrape Group {counter}]{ENDC}"
        f"{OKGREEN}[{target}]{ENDC} {WARNING}-{ENDC} "
        f"Scraping {count} followers for {WARNING}->{ENDC} "
        f"{OKCYAN}{target}{ENDC}"
    )

    number_of_scrapped = 0
    next_page_id = None

    # Keep this OUTSIDE the while loop
    scraped_followers = set()

    while number_of_scrapped < count:

        get_followers = hiker_client.user_followers_v2(
            user_id=user_id,
            page_id=next_page_id
        )

        # print(dumps(get_followers, indent=4))

        followers = get_followers["response"]["users"]

        for follower in followers:

            # Don't go beyond requested amount
            if number_of_scrapped >= count:
                break

            follower_username = follower.get("username")
            _user_id = follower.get("id")

            if not follower_username:
                continue

            if _user_id and user_id not in scraped_followers:
                scraped_followers.add(_user_id)
                number_of_scrapped += 1

            print(
                f"{HEADER}[Scrape Group {counter}]{ENDC}"
                f"{OKGREEN}[{target}]{ENDC} {WARNING}-{ENDC} "
                f"Fetched follower {WARNING}->{ENDC} "
                f"{OKCYAN}{follower_username} ({number_of_scrapped}){ENDC}"
            )

            # Save every 50 collected usernames
            if len(scraped_followers) >= 50:
                with open(file_path, 'a', encoding='utf-8') as file:
                    for username in scraped_followers:
                        file.write(f"{username}\n")

                print(
                    f"{HEADER}[Scrape Group {counter}]{ENDC}"
                    f"{OKGREEN}[{target}]{ENDC} {WARNING}-{ENDC} "
                    f"Saved {WARNING}{number_of_scrapped}{ENDC} followers so far."
                )

                scraped_followers.clear()

        next_page_id = get_followers.get("next_page_id")

        # No more pages
        if not next_page_id:
            print(
                f"No more follower pages available. "
                f"Scraped {number_of_scrapped}/{count}."
            )
            break

        time.sleep(5)

    # IMPORTANT: save the final batch (< 50)
    if scraped_followers:
        with open(file_path, 'a', encoding='utf-8') as file:
            for username in scraped_followers:
                file.write(f"{username}\n")

        print(
            f"{HEADER}[Scrape Group {counter}]{ENDC}"
            f"{OKGREEN}[{target}]{ENDC} {WARNING}-{ENDC} "
            f"Saved final {WARNING}{len(scraped_followers)}{ENDC} followers."
        )

    print(
        f"Finished scraping {target}: "
        f"{number_of_scrapped}/{count} followers processed."
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

def run_bot(target, counter):
    # bot = Bot(target, password, target, driver, cookie)
    get_followers_via_hiker(target, counter)
 
def fetch_target_account_followers():

    target_accounts = targets()
    threads = []

    counter = 1

    if len(target_accounts) != NUMBER_OF_SCRAPING_THREADS: 
        print(f"{FAIL}Your{ENDC} {WARNING}targets.txt{ENDC} {FAIL}file must have {NUMBER_OF_SCRAPING_THREADS} targets.{ENDC}\n")
    
    else:
        for account in SCRAPE_ACCOUNTS:
            thread = threading.Thread(target=run_bot, name=f"Scrape Group {counter}", args=(target_accounts[counter - 1], counter))
            threads.append(thread)
            print(f"{HEADER}[{thread.name}]{ENDC} - {OKGREEN}{account} scraping folllowers from {target_accounts[counter - 1]}{ENDC}")

            counter += 1

        for thread in threads: 
            thread.start()
    