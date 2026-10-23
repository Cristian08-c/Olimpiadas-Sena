"""Blueprint del panel de aprendiz (sin url_prefix: conserva /aprendiz y /api/examen/*)."""
from flask import Blueprint

bp = Blueprint("aprendiz", __name__)