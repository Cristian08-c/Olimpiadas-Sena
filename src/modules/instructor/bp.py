"""Blueprint del panel de instructor.

Sin url_prefix: las rutas actuales (/instructor, /examen/*, /ranking/*) se
mantienen para no tocar los paths hardcodeados en el JS embebido.
"""
from flask import Blueprint

bp = Blueprint("instructor", __name__)