from .settings import *

DB_NAME = 'hospitalA.sqlite3'
ORG_INSTANCE_NAME = 'hospitalA'
SERVER_URL = 'http://127.0.0.1:8000'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / DB_NAME,
    }
}