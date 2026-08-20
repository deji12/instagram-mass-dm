from decouple import config

# MESSAGE
MESSAGE = ("""@vikkiyoursuperstar just released her ONLYF*NS with FREE TRIAL for all her content TODAY! You don't want to miss it 👀""")

# DO NOT MODIFY
# THREADS
ACCOUNTS_PER_THREAD = config('ACCOUNTS_PER_THREAD')
DEFAULT_NUMBER_OF_FOLLOWERS = config('DEFAULT_NUMBER_OF_FOLLOWERS', cast=int)
NUMBER_OF_THREADS = config('NUMBER_OF_THREADS', cast=int)
ONE_TARGET_THREADS = False

# SCRAPING CONFIG
NUMBER_OF_SCRAPING_THREADS = config('NUMBER_OF_SCRAPING_THREADS', cast=int)
SCRAPE_ACCOUNTS = {
    "fredtio67": "xipza333",
    "lalyathebomb": "rimxa111",
    "snwnen4": "xxpp8888",
    "yankovgrn": "diff7080"
}

# LIMITS
MAX_MESSAGE_PER_ROTATION = config('MAX_MESSAGE_PER_ROTATION', cast=int)
MAX_MESSAGE_PER_DAY = config('MAX_MESSAGE_PER_DAY', cast=int)

# DO NOT MODIFY
# COLOR FORMATS
HEADER = '\033[95m'
OKBLUE = '\033[94m'
OKCYAN = '\033[96m'
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'

HIKER_API_TOKEN = config('HIKER_API_TOKEN')
PROXY_LOGIN = config('PROXY_LOGIN')
PROXY_PASSWORD = config('PROXY_PASSWORD')
PROXY_HOST = config('PROXY_HOST')
PROXY_PORT = config('PROXY_PORT', cast=int)