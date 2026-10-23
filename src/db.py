"""Gestión de conexiones a la base de datos con pool.

Reemplaza la función `get_db_connection()` que estaba en app.py. La firma
es la misma para no romper el código existente: devuelve una conexión o
None si falla.
"""
import mysql.connector
from mysql.connector import pooling, Error

from .config import Config


_pool = None


def _get_pool():
    """Crea el pool una sola vez (lazy)."""
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name=Config.DB_POOL_NAME,
            pool_size=Config.DB_POOL_SIZE,
            pool_reset_session=True,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            host=Config.DB_HOST,
            database=Config.DB_NAME,
            charset="utf8mb4",
            use_unicode=True,
            raise_on_warnings=True,
            use_pure=True,
        )
    return _pool


def get_db_connection():
    """Devuelve una conexión del pool.

    IMPORTANTE: llama siempre a `conn.close()` al terminar; con pooling eso
    devuelve la conexión al pool en vez de cerrarla de verdad.
    """
    try:
        return _get_pool().get_connection()
    except Error as err:
        print(f"Error de base de datos: {err}")
        return None