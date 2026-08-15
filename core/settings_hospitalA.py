from .settings import *

DB_NAME = 'hospitalA.sqlite3'
ORG_INSTANCE_NAME = 'hospitalA'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / DB_NAME,
    }
}