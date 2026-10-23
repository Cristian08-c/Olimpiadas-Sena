# --------------------------------------------------------------------------
# app.py - Factory de la aplicación Flask
# --------------------------------------------------------------------------
import os

from flask import Flask

from .config import Config


def create_app(config_object=None):
    app = Flask(
        __name__,
        template_folder=Config.TEMPLATE_FOLDER,
        static_folder=Config.STATIC_FOLDER,
    )
    app.config.from_object(Config)
    if config_object is not None:
        app.config.from_object(config_object)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["IMAGE_UPLOAD_FOLDER"], exist_ok=True)

    from .modules.admin import bp as admin_bp
    from .modules.aprendiz import bp as aprendiz_bp
    from .modules.auth import bp as auth_bp
    from .modules.instructor import bp as instructor_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(aprendiz_bp)
    app.register_blueprint(instructor_bp)

    return app