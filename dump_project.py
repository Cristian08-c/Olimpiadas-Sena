#!/usr/bin/env python3
"""
dump_project.py — Genera un volcado de texto del proyecto para depuración.

Uso:
    python dump_project.py                        # volcado con timestamp en cwd
    python dump_project.py -o debug.txt           # nombre específico
    python dump_project.py -r /ruta/proyecto      # otra raíz
    python dump_project.py --max-depth 6          # árbol menos profundo
"""

import argparse
import fnmatch
import os
import sys
from datetime import datetime
from pathlib import Path

EXCLUDE_DIRS = {
    ".git", ".svn", ".hg",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", ".venv", "venv", "env",
    ".idea", ".vscode",
    "uploads", "dist", "build",
}

EXCLUDE_FILES = [
    "*.pyc", "*.pyo", "*.log",
    "debug_dump_*.txt", "snapshot*.txt", "*.dump.txt",
    "*.sqlite", "*.db",
    ".DS_Store", "Thumbs.db",
    ".env", "*.env",          # evita filtrar secretos reales
]

TEXT_EXTS = {
    "py", "pyi", "html", "htm", "css", "js", "jsx", "ts", "tsx",
    "json", "yaml", "yml", "toml", "ini", "cfg", "conf",
    "sql", "md", "rst", "txt", "sh", "bash", "zsh",
    "jinja", "jinja2", "j2", "tpl", "template", "j2",
    "gitignore", "dockerfile", "makefile", "dockerignore",
}

BINARY_EXTS = {
    "png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp",
    "pdf", "zip", "tar", "gz", "whl", "egg",
    "xlsx", "xls", "docx", "pptx", "mp4", "mp3", "wav",
}


def is_excluded_dir(name: str) -> bool:
    return name in EXCLUDE_DIRS


def is_excluded_file(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_FILES)


def file_kind(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    name = path.name.lower()
    if ext in TEXT_EXTS or name in TEXT_EXTS:
        return "text"
    if ext in BINARY_EXTS:
        return "binary"
    # Fallback: archivos pequeños que decodifican como utf-8 → texto
    try:
        if path.stat().st_size < 2 * 1024 * 1024:
            with open(path, "rb") as f:
                f.read(4096).decode("utf-8")
            return "text"
    except (UnicodeDecodeError, OSError):
        pass
    return "binary"


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def build_tree(root: Path, out, skip: Path, max_depth: int = 10):
    def walk(dir_path: Path, prefix: str, depth: int):
        if depth > max_depth:
            return
        try:
            entries = sorted(
                dir_path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except PermissionError:
            return
        entries = [
            e for e in entries
            if e.resolve() != skip
            and not (e.is_dir() and is_excluded_dir(e.name))
            and not (e.is_file() and is_excluded_file(e.name))
        ]
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            suffix = "/" if entry.is_dir() else ""
            out.write(f"{prefix}{connector}{entry.name}{suffix}\n")
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                walk(entry, prefix + extension, depth + 1)

    out.write(f"{root.name}/\n")
    walk(root, "", 0)


def collect_files(root: Path, skip: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if not is_excluded_dir(d)
        )
        for fname in sorted(filenames):
            if is_excluded_file(fname):
                continue
            full = (Path(dirpath) / fname).resolve()
            if full == skip:
                continue
            yield full


def dump_file(path: Path, root: Path, out):
    rel = path.relative_to(root)
    try:
        size = path.stat().st_size
    except OSError:
        return
    kind = file_kind(path)
    out.write("\n")
    out.write("=" * 78 + "\n")
    out.write(f"FILE: {rel.as_posix()}\n")
    out.write(f"SIZE: {human_size(size)} ({size} bytes)\n")
    out.write(f"KIND: {kind}\n")
    out.write("=" * 78 + "\n")
    if kind != "text":
        out.write("(binario — contenido omitido)\n")
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="latin-1")
        except Exception as e:
            out.write(f"(no se pudo leer: {e})\n")
            return
    if not text.endswith("\n"):
        text += "\n"
    out.write(text)


def main():
    ap = argparse.ArgumentParser(
        description="Volcado de proyecto para depuración",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("-r", "--root", default=".", help="Raíz del proyecto (default: .)")
    ap.add_argument("-o", "--output", help="Archivo de salida")
    ap.add_argument("--max-depth", type=int, default=10, help="Profundidad del árbol")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.exit(f"ERROR: {root} no es un directorio")

    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = root / out_path
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = root / f"debug_dump_{ts}.txt"
    out_path = out_path.resolve()

    with out_path.open("w", encoding="utf-8") as out:
        out.write("# VOLCADO DE PROYECTO PARA DEPURACIÓN\n")
        out.write(f"# Generado: {datetime.now().isoformat(timespec='seconds')}\n")
        out.write(f"# Raíz:     {root}\n")
        try:
            out.write(f"# Host:     {os.uname().nodename}\n")
        except AttributeError:
            out.write(f"# Host:     {os.environ.get('COMPUTERNAME', 'n/a')}\n")
        out.write(f"# Python:   {sys.version.split()[0]}\n")
        git_head = root / ".git" / "HEAD"
        if git_head.exists():
            try:
                out.write(f"# Git HEAD: {git_head.read_text().strip()}\n")
            except OSError:
                pass
        out.write("\n")

        # 1. Estructura
        out.write("#" * 78 + "\n")
        out.write("# 1. ESTRUCTURA DEL PROYECTO\n")
        out.write("#" * 78 + "\n")
        build_tree(root, out, out_path, args.max_depth)

        # 2. Contenido
        out.write("\n\n")
        out.write("#" * 78 + "\n")
        out.write("# 2. CONTENIDO DE ARCHIVOS\n")
        out.write("#" * 78 + "\n")
        files = list(collect_files(root, out_path))
        text_count = sum(1 for f in files if file_kind(f) == "text")
        out.write(f"\n# Total archivos: {len(files)} "
                  f"({text_count} de texto, {len(files) - text_count} binarios)\n")
        for f in files:
            dump_file(f, root, out)

    size = out_path.stat().st_size
    print(f"✓ Volcado generado: {out_path}")
    print(f"  {human_size(size)}")
    print(f"  Archivos: {len(files)} ({text_count} de texto)")


if __name__ == "__main__":
    main()