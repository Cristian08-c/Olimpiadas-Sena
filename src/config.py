"""Configuración centralizada del proyecto.

Todos los valores mágicos (rutas, límites, duraciones, branding) viven aquí.
Los módulos y los templates leen de esta clase en vez de tener valores
hardcodeados en distintos sitios.

La carga de `.env` vive aquí (no en wsgi.py) para que `run.py` (dev server)
y `wsgi.py` (Apache) lean la MISMA SECRET_KEY. Sin esto, las cookies firmadas
por uno no se validan en el otro y aparece un 401 fantasma en las APIs.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Carga de .env — un solo lugar para todos los entry points (run.py, wsgi.py)
# ---------------------------------------------------------------------------
_env_file = BASE_DIR.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        # setdefault: no sobrescribe variables de entorno del SO (ej. Docker)
        os.environ.setdefault(_k.strip(), _v.strip())


class Config:
    """Configuración base (dev + fallback)."""

    # === Identidad ===
    APP_NAME = "Olimpiadas SENA CIDT"
    APP_VERSION = "1.0.0"

    # === Flask ===
    SECRET_KEY = os.getenv("SECRET_KEY", "olimpiadas_sena_secret_key")
    DEBUG = False
    TESTING = False
    HOST = "0.0.0.0"
    PORT = 5000

    # === Rutas de Flask ===
    TEMPLATE_FOLDER = str(BASE_DIR / "templates")
    STATIC_FOLDER = str(BASE_DIR / "static")
    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    IMAGE_UPLOAD_FOLDER = str(BASE_DIR / "static" / "img")

    # === Base de datos ===
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "0323")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "olimpiadas")
    DB_POOL_NAME = "olimpiadas_pool"
    DB_POOL_SIZE = 5

    # === Uploads ===
    ALLOWED_EXCEL_EXTENSIONS = {"xlsx", "xls"}
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    MAX_EXCEL_SIZE_MB = 10
    MAX_IMAGE_SIZE_MB = 5
    MAX_CONTENT_LENGTH_MB = 50

    # === Excel: parseo ===
    EXCEL_META_SKIPROWS = 1
    EXCEL_META_FICHA_COL = 2
    EXCEL_DATA_SKIPROWS = 4
    EXCEL_FICHA_SEPARATOR = " - "
    EXCEL_DOC_COLUMNS = ("Numero de Documento", "Número de Documento")
    EXCEL_NAME_COLUMN = "Nombre"
    EXCEL_LASTNAME_COLUMN = "Apellidos"
    EXCEL_PHONE_COLUMN = "Celular"
    EXCEL_EMAIL_COLUMNS = ("Correo Electrónico", "Correo Electronico")
    EXCEL_STATE_COLUMN = "Estado"
    EXCEL_VALID_STATES = ("EN FORMACION", "INDUCCION")

    # === Exámenes ===
    EXAM_DEFAULT_DURATION_MIN = 60
    EXAM_MIN_DURATION_MIN = 1
    EXAM_MAX_DURATION_MIN = 480
    EXAM_DEFAULT_POINTS = 10
    EXAM_MIN_POINTS = 1
    EXAM_MAX_POINTS = 100
    EXAM_TYPES = ("matematicas", "ortografia", "ingles")
    EXAM_PHASES = (1, 2)
    EXAM_STATES = ("borrador", "publico")

    # === Ranking / Fase 2 ===
    RANKING_TOP_N = 40
    RANKING_PAGE_SIZE = 40

    # === Sesión ===
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME_SEC = 60 * 60 * 8

    # === Roles ===
    ROLE_ADMIN = "admin"
    ROLE_INSTRUCTOR = "instructor"
    ROLE_APRENDIZ = "aprendiz"
    ROLES = (ROLE_ADMIN, ROLE_INSTRUCTOR, ROLE_APRENDIZ)

    # === Matrícula ===
    MATRICULA_DEFAULT_STATE = "EN FORMACION"
    MATRICULA_CANCELLED_STATES = ("CANCELADO", "RETIRO VOLUNTARIO")

    # === Branding ===
    BRANDING = {
        "name": "SENA Olimpiadas",
        "institution": "Centro Industrial y del Desarrollo Tecnológico",
        "regional": "Regional Santander",
        "primary_color": "#39A900",
    }

    # === Claves que se inyectan al JS (via {{ js_config | tojson }}) ===
    JS_CONFIG_KEYS = (
        "RANKING_PAGE_SIZE",
        "RANKING_TOP_N",
        "EXAM_MIN_POINTS",
        "EXAM_MAX_POINTS",
        "EXAM_DEFAULT_POINTS",
        "EXAM_DEFAULT_DURATION_MIN",
        "EXAM_MIN_DURATION_MIN",
        "EXAM_MAX_DURATION_MIN",
        "MAX_IMAGE_SIZE_MB",
    )


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    DB_NAME = "olimpiadas_test"