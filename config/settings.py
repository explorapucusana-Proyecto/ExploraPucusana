"""
Django settings for config project.
Configuración optimizada para Explora Pucusana (Local + Render Ready).
"""
import os
from pathlib import Path
from dotenv import load_dotenv  # Carga variables de entorno desde el archivo .env
import dj_database_url

# Cargar variables de entorno
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key')

# Control del modo Debug desde el archivo .env
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# Hosts permitidos para desarrollo local y Render
ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = [
    'https://explorapucusana.munipucusana.gob.pe',
    'https://explorapucusana.onrender.com',
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'allauth': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}


# ==========================================
# DEFINICIÓN DE APLICACIONES
# ==========================================

INSTALLED_APPS = [
    'turismo',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Requerido por allauth

    # Django Allauth Core
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    
    # Proveedores Sociales
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    'allauth.socialaccount.providers.microsoft',

    # App principal del proyecto
    
]

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]


# ==========================================
# MIDDLEWARE
# ==========================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    
    # WhiteNoise sirve los archivos estáticos en producción
    'whitenoise.middleware.WhiteNoiseMiddleware', 
    
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # Requerido para i18n
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',  # Middleware de allauth
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'turismo.context_processors.alerta_perfil',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ==========================================
# BASE DE DATOS (Híbrida: Supabase / SQLite)
# ==========================================

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

if DATABASE_URL.startswith(('postgres://', 'postgresql://')):
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# ==========================================
# VALIDACIÓN DE CONTRASEÑAS
# ==========================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ==========================================
# INTERNACIONALIZACIÓN Y ZONA HORARIA
# ==========================================

LANGUAGE_CODE = 'es-pe'

TIME_ZONE = 'America/Lima'

USE_I18N = True

USE_TZ = True

# Idiomas disponibles en Explora Pucusana
LANGUAGES = [
    ('es', 'Español'),
    ('en', 'English'),
]

# Directorio de archivos de traducción
LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]


# ==========================================
# ARCHIVOS ESTÁTICOS Y MULTIMEDIA
# ==========================================

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'turismo/static'),
]

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR

if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ==========================================
# GESTIÓN DE SESIONES Y ACCESOS
# ==========================================

# Cierra la sesión al cerrar el navegador
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Tiempo de vida de la cookie de sesión (1 hora de inactividad)
SESSION_COOKIE_AGE = 3600 

# Renueva la expiración de la sesión con cada interacción
SESSION_SAVE_EVERY_REQUEST = True

# Redirecciones de acceso
ACCOUNT_SIGNUP_REDIRECT_URL = 'perfil'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'index' 
LOGOUT_REDIRECT_URL = 'login'


# ==========================================
# CONFIGURACIÓN DJANGO-ALLAUTH (ACTUALIZADA)
# ==========================================

# Permite iniciar sesión con correo electrónico o nombre de usuario
ACCOUNT_LOGIN_METHODS = {'email', 'username'}

# Campos solicitados y obligatorios en el registro manual directo
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']

# Sin confirmación por correo para no frenar la experiencia del turista
ACCOUNT_EMAIL_VERIFICATION = 'none'

# Login social automático: vincula la cuenta y extrae los datos del proveedor
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_QUERY_EMAIL = True
# Configuración HTTPS detrás del proxy de Render para django-allauth
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'

# Configuración de registro y enlace automático con Google
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
    }
}