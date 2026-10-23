# wsgi.py — entry point para Apache + mod_wsgi
import sys
from pathlib import Path

# Agregar la raíz del proyecto al sys.path para que `import src.app` funcione
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# `config.py` se encarga de cargar `.env` al importarse.
from src.app import create_app

application = create_app()   # ← mod_wsgi busca esta variable por nombre