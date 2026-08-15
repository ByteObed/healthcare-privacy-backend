from .settings import *

DB_NAME = 'hospitalC.sqlite3'
ORG_INSTANCE_NAME = 'hospitalC'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / DB_NAME,
    }
}