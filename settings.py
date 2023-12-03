import os

GUILDS = []
DISCORD_TOKEN = ''
BOT_COLOUR = 0xFF6E00
DATABASE_FILE = 'main.db'
DMOJ_API_KEY = ''
DMOJ_REQUEST_DELAY = {
    'default': 0.5,
    'long': 5,
}
DMOJ_BASE_URL = 'https://dmoj.ca'
DMOJ_API_URL = 'api/v2'

ROLE_IDS = {}

SECRET_KEY = ''

try:
    with open(os.path.join(os.path.dirname(__file__), 'local_settings.py')) as f:
        exec(f.read(), globals())
except IOError:
    pass
