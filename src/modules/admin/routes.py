"""Rutas del panel de administración."""
import os
import re
from datetime import date

import mysql.connector
import pandas as pd
from flask import (
    flash, jsonify, redirect, render_template, request, session, url_for,
)
from werkzeug.utils import secure_filename

from ...config import Config
from ...db import get_db_connection
from ..common.decorators import role_required
from ..common.files import allowed_file
from .bp import bp


@bp.route("/dashboard")
@bp.route("/upload", methods=["GET", "POST"])
@role_required("admin")
def dashboard():
    nombre_completo = f"{session.get('user_name', '')} {session.get('user_apellido', '')}".strip()

    if request.method == "POST":
        files = request.files.getlist("file")
        if not files or all(f.filename == "" for f in files):
            flash("No se seleccionó ningún archivo", "warning")
            return redirect(request.url)

        resultados_exitosos = []
        resultados_fallidos = []

        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
                conn = None
                cursor = None
                try:
                    file.save(filepath)
                    conn = get_db_connection()
                    if not conn:
                        raise Exception("No se pudo conectar a la base de datos.")
                    cursor = conn.cursor()
                    engine = "openpyxl" if filepath.endswith(".xlsx") else "xlrd"

                    df_meta = pd.read_excel(filepath, nrows=1, skiprows=1, header=None, engine=engine)
                    ficha_raw = str(df_meta.iloc[0, 2])

                    numero_ficha = None
                    nombre_ficha = None

                    if " - " in ficha_raw:
                        parts = ficha_raw.split(" - ", 1)
                        num_match = re.search(r"(\d+)", parts[0])
                        if num_match:
                            numero_ficha = int(num_match.group(1))
                            nombre_ficha = parts[1].strip()

                    if numero_ficha is None:
                        ficha_match = re.search(r"(\d+)", ficha_raw)
                        if not ficha_match:
                            raise ValueError(f"No se pudo extraer el número de ficha de: {ficha_raw}")
                        numero_ficha = int(ficha_match.group(1))
                        nombre_ficha = f"Ficha {numero_ficha}"

                    df = pd.read_excel(filepath, skiprows=4, engine=engine)

                    cursor.execute(
                        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'matricula' "
                        "AND COLUMN_NAME = 'estado'",
                        (Config.DB_NAME,),
                    )
                    if cursor.fetchone()[0] == 0:
                        cursor.execute(
                            "ALTER TABLE matricula ADD COLUMN estado VARCHAR(50) "
                            "DEFAULT 'EN FORMACION'"
                        )
                        conn.commit()

                    cursor.execute("SELECT id_ficha FROM fichas WHERE id_ficha = %s", (numero_ficha,))
                    if not cursor.fetchone():
                        cursor.execute(
                            "INSERT INTO fichas (id_ficha, nombre, activo) VALUES (%s, %s, %s)",
                            (numero_ficha, nombre_ficha, True),
                        )
                    else:
                        cursor.execute(
                            "UPDATE fichas SET nombre = %s WHERE id_ficha = %s",
                            (nombre_ficha, numero_ficha),
                        )
                    conn.commit()

                    procesados = actualizados = errores = 0

                    for index, row in df.iterrows():
                        if pd.isna(row.get("Numero de Documento")) and pd.isna(row.get("Número de Documento")):
                            continue
                        try:
                            doc_value = row.get("Numero de Documento") if pd.notna(row.get("Numero de Documento")) else row.get("Número de Documento")
                            identificacion = "".join(filter(str.isdigit, str(doc_value).strip()))
                            if not identificacion:
                                continue
                            identificacion = int(identificacion)

                            nombre = str(row["Nombre"]).strip() if pd.notna(row.get("Nombre")) else ""
                            apellido = str(row["Apellidos"]).strip() if pd.notna(row.get("Apellidos")) else ""
                            celular = str(row["Celular"]).strip() if pd.notna(row.get("Celular")) else "0"

                            correo_col = row.get("Correo Electrónico") if pd.notna(row.get("Correo Electrónico")) else row.get("Correo Electronico")
                            correo = str(correo_col).strip() if pd.notna(correo_col) else ""

                            estado_matricula = str(row.get("Estado", "")).strip()
                            if estado_matricula.upper() not in Config.EXCEL_VALID_STATES:
                                continue
                            if not nombre or not apellido:
                                continue

                            try:
                                celular_num = int("".join(filter(str.isdigit, celular))) if celular and celular != "0" else 0
                            except ValueError:
                                celular_num = 0

                        except (ValueError, KeyError) as e:
                            print(f"Error en fila {index + 6} ({filename}): {e}")
                            errores += 1
                            continue

                        try:
                            pwd = str(numero_ficha)
                            cursor.execute(
                                "INSERT INTO personas "
                                "(identificacion, nombre, apellido, celular, correo, `contraseña`, rol, estado, activo) "
                                "VALUES (%s, %s, %s, %s, %s, %s, 'aprendiz', 'activo', TRUE) "
                                "ON DUPLICATE KEY UPDATE "
                                "nombre = %s, apellido = %s, celular = %s, correo = %s, `contraseña` = %s",
                                (identificacion, nombre, apellido, celular_num, correo, pwd,
                                 nombre, apellido, celular_num, correo, pwd),
                            )
                            if cursor.rowcount == 1:
                                procesados += 1
                            else:
                                actualizados += 1

                            try:
                                cursor.execute(
                                    "INSERT INTO matricula (identificacion, id_ficha, fecha_matricula, estado) "
                                    "VALUES (%s, %s, %s, %s)",
                                    (identificacion, numero_ficha, date.today(), estado_matricula),
                                )
                            except mysql.connector.IntegrityError:
                                cursor.execute(
                                    "UPDATE matricula SET estado = %s, fecha_matricula = %s "
                                    "WHERE identificacion = %s AND id_ficha = %s",
                                    (estado_matricula, date.today(), identificacion, numero_ficha),
                                )

                            if (procesados + actualizados) % 10 == 0:
                                conn.commit()

                        except mysql.connector.Error as db_err:
                            print(f"Error BD en fila {index + 6} (ID: {identificacion}, Archivo: {filename}): {db_err}")
                            errores += 1
                            conn.rollback()
                            continue

                    conn.commit()

                    mensaje = f'Archivo "{filename}" (Ficha {numero_ficha} - {nombre_ficha}): '
                    mensaje += f"Nuevos: {procesados}, Actualizados: {actualizados}"
                    if errores > 0:
                        mensaje += f", Errores: {errores}"
                    resultados_exitosos.append(mensaje)

                except Exception as e:
                    if conn and conn.is_connected():
                        conn.rollback()
                    print(f"Error detallado en {filename}: {e}")
                    resultados_fallidos.append(f'Error al procesar "{filename}": {e}')

                finally:
                    if cursor:
                        cursor.close()
                    if conn and conn.is_connected():
                        conn.close()
                    if os.path.exists(filepath):
                        os.remove(filepath)

            elif file:
                resultados_fallidos.append(
                    f'Archivo "{file.filename}" no permitido (solo .xlsx, .xls).'
                )

        for msg in resultados_exitosos:
            flash(msg, "success")
        for msg in resultados_fallidos:
            flash(msg, "danger")

        return redirect(url_for("admin.fichas"))

    return render_template("admin/upload.html", usuario={"nombre_completo": nombre_completo})


@bp.route("/subir", methods=["GET", "POST"])
@role_required("admin")
def upload_file():
    return dashboard()


@bp.route("/fichas")
@role_required("admin")
def fichas():
    nombre_completo = f"{session.get('user_name', '')} {session.get('user_apellido', '')}".strip()

    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return render_template(
            "admin/fichas.html", fichas=[], usuario={"nombre_completo": nombre_completo}
        )

    cursor = conn.cursor(dictionary=True)

    cursor.execute("SHOW COLUMNS FROM fichas")
    columns = [col["Field"] for col in cursor.fetchall()]

    tiene_activo = "activo" in columns
    tiene_estado = "estado" in columns

    select_parts = ["f.id_ficha", "f.nombre"]
    group_parts = ["f.id_ficha", "f.nombre"]

    if tiene_activo:
        select_parts.append("f.activo")
        group_parts.append("f.activo")
    if tiene_estado:
        select_parts.append("f.estado")
        group_parts.append("f.estado")

    select_parts.append("COUNT(m.id_matricula) as total_personas")

    sql = f"""
        SELECT {', '.join(select_parts)}
        FROM fichas f
        LEFT JOIN matricula m ON f.id_ficha = m.id_ficha
        GROUP BY {', '.join(group_parts)}
        ORDER BY f.id_ficha DESC
    """
    cursor.execute(sql)
    fichas = cursor.fetchall()

    for ficha in fichas:
        if "activo" not in ficha:
            ficha["activo"] = True
        if "estado" not in ficha:
            ficha["estado"] = "activa" if ficha.get("activo", True) else "inactiva"

    cursor.close()
    conn.close()

    return render_template(
        "admin/fichas.html", fichas=fichas, usuario={"nombre_completo": nombre_completo}
    )


@bp.route("/ficha/<int:ficha_num>")
@role_required("admin")
def ver_ficha(ficha_num):
    nombre_completo = f"{session.get('user_name', '')} {session.get('user_apellido', '')}".strip()

    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for("admin.fichas"))

    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM fichas WHERE id_ficha = %s", (ficha_num,))
    ficha = cursor.fetchone()

    if not ficha:
        flash(f"No se encontró la ficha {ficha_num}", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("admin.fichas"))

    sql = """
        SELECT p.identificacion, p.nombre, p.apellido, p.celular, p.correo, p.rol,
               p.estado as estado_persona, m.estado AS estado_matricula,
               m.numero_lista, p.activo
        FROM personas p
        JOIN matricula m ON p.identificacion = m.identificacion
        WHERE m.id_ficha = %s
        ORDER BY p.apellido, p.nombre
    """
    cursor.execute(sql, (ficha_num,))
    aprendices = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        "admin/aprendices.html",
        aprendices=aprendices,
        ficha=ficha,
        usuario={"nombre_completo": nombre_completo},
    )


@bp.route("/ficha/<int:ficha_id>/toggle")
@role_required("admin")
def toggle_ficha(ficha_id):
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for("admin.fichas"))

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT activo FROM fichas WHERE id_ficha = %s", (ficha_id,))
        result = cursor.fetchone()

        if result:
            nuevo_estado = not result[0]
            cursor.execute("UPDATE fichas SET activo = %s WHERE id_ficha = %s", (nuevo_estado, ficha_id))
            conn.commit()
            accion = "habilitada" if nuevo_estado else "deshabilitada"
            flash(f"La ficha {ficha_id} ha sido {accion} exitosamente.", "success")
        else:
            flash(f"No se encontró la ficha {ficha_id}.", "warning")

    except mysql.connector.Error as err:
        flash(f"Error al actualizar el estado: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("admin.fichas"))


@bp.route("/aprendiz/<int:ficha_id>/<int:aprendiz_id>/toggle")
@role_required("admin")
def toggle_aprendiz(ficha_id, aprendiz_id):
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for("admin.ver_ficha", ficha_num=ficha_id))

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT activo FROM personas WHERE identificacion = %s", (aprendiz_id,))
        result = cursor.fetchone()

        if result:
            nuevo_estado = not result[0]
            cursor.execute(
                "UPDATE personas SET activo = %s WHERE identificacion = %s",
                (nuevo_estado, aprendiz_id),
            )
            conn.commit()
            accion = "habilitado" if nuevo_estado else "deshabilitado"
            flash(f"El aprendiz {aprendiz_id} ha sido {accion} exitosamente.", "success")
        else:
            flash(f"No se encontró al aprendiz con identificación {aprendiz_id}.", "warning")

    except mysql.connector.Error as err:
        flash(f"Error al actualizar el estado: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("admin.ver_ficha", ficha_num=ficha_id))


@bp.route("/instructores", methods=["GET", "POST"])
@role_required("admin")
def instructores():
    nombre_completo = f"{session.get('user_name', '')} {session.get('user_apellido', '')}".strip()

    if request.method == "POST":
        identificacion = request.form.get("identificacion")
        nombre = request.form.get("nombre")
        apellido = request.form.get("apellido")
        celular = request.form.get("celular")
        correo = request.form.get("correo")
        contraseña = request.form.get("contraseña")
        rol = request.form.get("rol", "instructor")

        if not all([identificacion, nombre, apellido, celular, correo, contraseña]):
            flash("Todos los campos son obligatorios.", "warning")
            return redirect(request.url)
        if rol not in ("instructor", "admin"):
            flash("El rol debe ser instructor o admin.", "warning")
            return redirect(request.url)

        conn = get_db_connection()
        if not conn:
            flash("Error de conexión a la base de datos.", "danger")
            return redirect(request.url)

        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO personas "
                "(identificacion, nombre, apellido, celular, correo, contraseña, rol, estado, activo) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 'activo', TRUE)",
                (identificacion, nombre, apellido, celular, correo, contraseña, rol),
            )
            conn.commit()
            rol_texto = "Instructor" if rol == "instructor" else "Administrador"
            flash(f"{rol_texto} registrado exitosamente.", "success")
        except mysql.connector.IntegrityError:
            flash(f"Ya existe un usuario con la identificación {identificacion}.", "danger")
        except mysql.connector.Error as err:
            flash(f"Error al registrar el usuario: {err}", "danger")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("admin.instructores"))

    return render_template(
        "admin/registro_instructor.html", usuario={"nombre_completo": nombre_completo}
    )


@bp.route("/registro_instructor", methods=["GET", "POST"])
@role_required("admin")
def registro_instructor():
    return instructores()


@bp.route("/init_db")
@role_required("admin")
def init_db():
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for("admin.fichas"))

    cursor = conn.cursor()
    try:
        checks = [
            ("fichas", "activo", "ALTER TABLE fichas ADD COLUMN activo BOOLEAN DEFAULT TRUE"),
            ("fichas", "estado", "ALTER TABLE fichas ADD COLUMN estado VARCHAR(50) DEFAULT 'activa'"),
            ("personas", "activo", "ALTER TABLE personas ADD COLUMN activo BOOLEAN DEFAULT TRUE"),
            ("matricula", "numero_lista", "ALTER TABLE matricula ADD COLUMN numero_lista INT"),
            ("matricula", "fecha_matricula", "ALTER TABLE matricula ADD COLUMN fecha_matricula DATE"),
        ]
        for table, col, ddl in checks:
            cursor.execute(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                (Config.DB_NAME, table, col),
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(ddl)

        cursor.execute(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'personas' AND COLUMN_NAME = 'celular'",
            (Config.DB_NAME,),
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE personas CHANGE telefono celular BIGINT")

        conn.commit()
        flash("Base de datos actualizada exitosamente.", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Error al actualizar la base de datos: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("admin.fichas"))