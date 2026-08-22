from .settings import *

DB_NAME = 'hospitalC.sqlite3'
ORG_INSTANCE_NAME = 'hospitalC'
SERVER_URL = 'http://127.0.0.1:8002'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / DB_NAME,
    }
}