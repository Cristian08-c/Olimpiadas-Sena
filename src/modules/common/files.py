"""Helpers de validación de archivos subidos."""
from ...config import Config


def allowed_file(filename: str) -> bool:
    """True si el archivo tiene extensión de Excel permitida."""
    return "." in filename and (
        filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXCEL_EXTENSIONS
    )


def allowed_image_file(filename: str) -> bool:
    """True si el archivo tiene extensión de imagen permitida."""
    return "." in filename and (
        filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_IMAGE_EXTENSIONS
    )