from decouple import config

# MESSAGE
MESSAGE = ("""
FRAUD WARNING!!!
Reports allege that Sabrina Stängle, CEO of Lai-ive GmbH, sells low-quality hair extensions imported from China at premium prices, with some customers reporting scalp irritation and worsening scalp conditions.

She and business partner Kasun Suess are also accused of running an investment fraud scheme targeting vulnerable and inexperienced individuals, particularly elderly and chronically ill people.

Do your research before buying hair extensions or investing your money, and never invest more than you can afford to lose. Full report: https://www.sabrina-staengle.com?utm_source=chatgpt.com

""")

# DO NOT MODIFY
# THREADS
ACCOUNTS_PER_THREAD = config('ACCOUNTS_PER_THREAD', cast=int)
DEFAULT_NUMBER_OF_FOLLOWERS = config('DEFAULT_NUMBER_OF_FOLLOWERS', cast=int)
NUMBER_OF_THREADS_ = config('NUMBER_OF_THREADS_', cast=int)
ONE_TARGET_THREADS = False

DEDICATED_ACCOUNT_FOR_USERNAME_TO_USER_ID_CONVERSION = "lalyathebomb"

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