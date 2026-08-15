from .settings import *

DB_NAME = 'hospitalB.sqlite3'
ORG_INSTANCE_NAME = 'hospitalB'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / DB_NAME,
    }
}