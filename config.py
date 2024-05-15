TOKEN = ''

MAX_USERS = 3
MAX_GPT_TOKENS = 120
COUNT_LAST_MSG = 4

IAM_TOKEN = ""
FOLDER_ID = ''
ADMIN_ID = '801460635'  # user_id автора бота чтобы получать отчеты с логами


MAX_USER_STT_BLOCKS = 10
MAX_USER_TTS_SYMBOLS = 5_000
MAX_USER_GPT_TOKENS = 2_000
MAX_TTS_SYMBOLS = 12

SYSTEM_PROMPT = [{'role': 'system', 'text': 'Ты профессиональный психолог.'
                                            'Помоги человеку разобраться в себе.'}]

HOME_DIR = '/Users/Citi/Desktop/pythonYandex/BotZinka'
LOGS = f'{HOME_DIR}/logs.txt'
DB_FILE = f'{HOME_DIR}/messages.db'

IAM_TOKEN_PATH = f'{HOME_DIR}/creds/iam_token.txt'
FOLDER_ID_PATH = f'{HOME_DIR}/creds/folder_id.txt'
BOT_TOKEN_PATH = f'{HOME_DIR}/creds/bot_token.txt'