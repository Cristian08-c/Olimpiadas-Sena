"""Decoradores de autenticación y autorización.

Reemplazan las comprobaciones manuales tipo:

    if 'user_role' not in session or session['user_role'] != 'admin':
        return redirect(url_for('auth.index'))

por:

    @role_required('admin')

Aún no se usan en este paso; los aplicaremos en el paso 2 al mover las
rutas a blueprints.
"""
from functools import wraps

from flask import abort, flash, redirect, session, url_for


def login_required(fn):
    """Redirige al login si no hay sesión activa."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_role" not in session:
            flash("Debes iniciar sesión para acceder.", "warning")
            return redirect(url_for("auth.index"))
        return fn(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """Restringe el acceso a los roles indicados. Implica login_required."""
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if session.get("user_role") not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator