# wsgi.py — entry point para Apache + mod_wsgi
import sys
import os
from pathlib import Path

# 1. Agregar la raíz del proyecto al sys.path para que `import src.app` funcione
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# 2. Cargar .env si existe (mismo mecanismo que en app.py)
_env = BASE_DIR / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

# 3. Crear la app con el factory
from src.app import create_app

application = create_app()   # ← mod_wsgi busca esta variable por nombre