from .settings import *

DB_NAME = 'hospitalB.sqlite3'
ORG_INSTANCE_NAME = 'hospitalB'
SERVER_URL = 'http://127.0.0.1:8001'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / DB_NAME,
    }
}