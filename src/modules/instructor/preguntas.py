"""Rutas de gestión de preguntas de un examen."""
import json
import os
import uuid

import mysql.connector
from flask import jsonify, render_template, request, session
from werkzeug.utils import secure_filename

from ...config import Config
from ...db import get_db_connection
from ..common.decorators import role_required
from ..common.files import allowed_image_file
from .bp import bp


@bp.route("/examen/gestionar/<int:id_instrumento>")
@role_required("instructor")
def gestionar_examen(id_instrumento):
    conn = get_db_connection()
    if not conn:
        return "Error de conexión", 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id_instrumento, titulo, tipo, `fase(1-2)`, estado, duracion "
            "FROM instrumentos WHERE id_instrumento = %s AND identificacion = %s",
            (id_instrumento, session["user_id"]),
        )
        examen = cursor.fetchone()
        if not examen:
            return "Examen no encontrado o no autorizado", 404
        if examen["duracion"]:
            examen["duracion"] = str(examen["duracion"])

        cursor.execute(
            "SELECT p.id_pregunta AS id, p.pregunta, p.enunciado, p.puntos, p.archivo, "
            "r.respuesta, r.estado "
            "FROM preguntas_seleccion p "
            "LEFT JOIN respuestas_seleccion r ON p.id_pregunta = r.id_pregunta "
            "WHERE p.id_instrumento = %s "
            "ORDER BY p.id_pregunta, r.id_respuesta1",
            (id_instrumento,),
        )
        preguntas_seleccion_dict = {}
        for row in cursor.fetchall():
            if row["id"] not in preguntas_seleccion_dict:
                preguntas_seleccion_dict[row["id"]] = {
                    "id": row["id"], "tipo_tabla": "seleccion",
                    "tipo": "seleccion_multiple",
                    "pregunta": row["pregunta"], "enunciado": row["enunciado"],
                    "puntos": row["puntos"], "archivo": row["archivo"], "opciones": [],
                }
            if row["respuesta"]:
                preguntas_seleccion_dict[row["id"]]["opciones"].append({
                    "texto": row["respuesta"],
                    "correcta": row["estado"] == "verdadero",
                })

        cursor.execute(
            "SELECT p.id_pregunta2 AS id, p.pregunta, p.tipo, p.enunciado, p.puntos, p.archivo, "
            "r.enunciado as enunciado_resp, r.complemento "
            "FROM preguntas_otras p "
            "LEFT JOIN respuestas_otras r ON p.id_pregunta2 = r.id_pregunta2 "
            "WHERE p.id_instrumento = %s "
            "ORDER BY p.id_pregunta2, r.id_respuesta2",
            (id_instrumento,),
        )
        preguntas_otras_dict = {}
        for row in cursor.fetchall():
            if row["id"] not in preguntas_otras_dict:
                preguntas_otras_dict[row["id"]] = {
                    "id": row["id"], "tipo_tabla": "otras", "tipo": row["tipo"],
                    "pregunta": row["pregunta"], "enunciado": row["enunciado"],
                    "puntos": row["puntos"], "archivo": row["archivo"], "opciones": [],
                }
            if row["enunciado_resp"]:
                if row["tipo"] == "relacionar":
                    preguntas_otras_dict[row["id"]]["opciones"].append({
                        "col_a": row["enunciado_resp"], "col_b": row["complemento"],
                    })
                elif row["tipo"] == "completar":
                    preguntas_otras_dict[row["id"]]["opciones"].append({
                        "texto": row["complemento"],
                        "correcta": row["enunciado_resp"] == "correcto",
                    })

        todas_preguntas = (
            list(preguntas_seleccion_dict.values())
            + list(preguntas_otras_dict.values())
        )
    finally:
        cursor.close()
        conn.close()
    return render_template(
        "instructor/gestionar_examen.html",
        examen=examen,
        preguntas=todas_preguntas,
    )


@bp.route("/examen/<int:id_instrumento>/pregunta/crear", methods=["POST"])
def crear_pregunta(id_instrumento):
    if session.get("user_role") != "instructor":
        return jsonify({"error": "No autorizado"}), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión"}), 500

    cursor = conn.cursor()
    nombre_archivo = None
    try:
        tipo = request.form.get("tipo_pregunta")
        pregunta = request.form.get("pregunta")
        enunciado = request.form.get("enunciado")
        puntos = int(request.form.get("puntos"))
        opciones = json.loads(request.form.get("opciones"))
        archivo = request.files.get("archivo")

        if archivo and allowed_image_file(archivo.filename):
            filename = secure_filename(archivo.filename)
            nombre_archivo = f"{uuid.uuid4().hex}_{filename}"
            archivo.save(os.path.join(Config.IMAGE_UPLOAD_FOLDER, nombre_archivo))

        conn.start_transaction()
        response_data = {}
        if tipo == "seleccion_multiple":
            cursor.execute(
                "INSERT INTO preguntas_seleccion "
                "(pregunta, enunciado, archivo, id_instrumento, puntos) "
                "VALUES (%s, %s, %s, %s, %s)",
                (pregunta, enunciado, nombre_archivo, id_instrumento, puntos),
            )
            id_pregunta = cursor.lastrowid
            for op in opciones:
                estado = "verdadero" if str(op.get("correcta")).lower() == "true" else "falso"
                cursor.execute(
                    "INSERT INTO respuestas_seleccion (respuesta, estado, id_pregunta) "
                    "VALUES (%s, %s, %s)",
                    (op["texto"], estado, id_pregunta),
                )
            response_data = {"id": id_pregunta, "tipo_tabla": "seleccion"}
        elif tipo in ("completar", "relacionar"):
            cursor.execute(
                "INSERT INTO preguntas_otras "
                "(pregunta, tipo, enunciado, archivo, id_instrumento, puntos) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (pregunta, tipo, enunciado, nombre_archivo, id_instrumento, puntos),
            )
            id_pregunta = cursor.lastrowid
            if tipo == "completar":
                for op in opciones:
                    estado = "correcto" if op.get("correcta") else "distractor"
                    cursor.execute(
                        "INSERT INTO respuestas_otras (enunciado, complemento, id_pregunta2) "
                        "VALUES (%s, %s, %s)",
                        (estado, op["texto"], id_pregunta),
                    )
            elif tipo == "relacionar":
                for par in opciones:
                    cursor.execute(
                        "INSERT INTO respuestas_otras (enunciado, complemento, id_pregunta2) "
                        "VALUES (%s, %s, %s)",
                        (par["col_a"], par["col_b"], id_pregunta),
                    )
            response_data = {"id": id_pregunta, "tipo_tabla": "otras"}
        conn.commit()

        response_data.update({
            "tipo": tipo, "pregunta": pregunta, "enunciado": enunciado,
            "puntos": puntos, "opciones": opciones, "archivo": nombre_archivo,
        })
        return jsonify(response_data), 201
    except (Exception, mysql.connector.Error) as err:
        conn.rollback()
        if nombre_archivo:
            path_a_borrar = os.path.join(Config.IMAGE_UPLOAD_FOLDER, nombre_archivo)
            if os.path.exists(path_a_borrar):
                os.remove(path_a_borrar)
        return jsonify({"error": f"Error en el servidor: {err}"}), 500
    finally:
        cursor.close()
        conn.close()


@bp.route("/examen/<int:id_instrumento>/pregunta/actualizar", methods=["POST"])
def actualizar_pregunta(id_instrumento):
    if session.get("user_role") != "instructor":
        return jsonify({"error": "No autorizado"}), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión"}), 500

    cursor = conn.cursor()
    try:
        id_pregunta = int(request.form.get("id_pregunta"))
        tipo_tabla = request.form.get("tipo_tabla")
        tipo_pregunta = request.form.get("tipo_pregunta")
        pregunta_texto = request.form.get("pregunta")
        enunciado = request.form.get("enunciado")
        puntos = int(request.form.get("puntos"))
        opciones = json.loads(request.form.get("opciones"))
        archivo = request.files.get("archivo")

        table_name = "preguntas_seleccion" if tipo_tabla == "seleccion" else "preguntas_otras"
        id_column = "id_pregunta" if tipo_tabla == "seleccion" else "id_pregunta2"

        cursor.execute(f"SELECT archivo FROM {table_name} WHERE {id_column} = %s", (id_pregunta,))
        result = cursor.fetchone()
        old_filename = result[0] if result and result[0] else None

        params_base = [pregunta_texto, enunciado, puntos]
        nombre_archivo_para_db = old_filename
        update_archivo_sql = ""
        params_archivo = []

        if archivo and allowed_image_file(archivo.filename):
            if old_filename:
                old_filepath = os.path.join(Config.IMAGE_UPLOAD_FOLDER, old_filename)
                if os.path.exists(old_filepath):
                    os.remove(old_filepath)
            filename = secure_filename(archivo.filename)
            new_filename = f"{uuid.uuid4().hex}_{filename}"
            archivo.save(os.path.join(Config.IMAGE_UPLOAD_FOLDER, new_filename))
            nombre_archivo_para_db = new_filename
            update_archivo_sql = ", archivo = %s"
            params_archivo.append(nombre_archivo_para_db)

        sql = (
            f"UPDATE {table_name} SET pregunta=%s, enunciado=%s, puntos=%s"
            f"{update_archivo_sql} WHERE {id_column}=%s"
        )
        cursor.execute(sql, tuple(params_base + params_archivo + [id_pregunta]))

        if tipo_tabla == "seleccion":
            cursor.execute("DELETE FROM respuestas_seleccion WHERE id_pregunta=%s", (id_pregunta,))
            for op in opciones:
                estado = "verdadero" if str(op.get("correcta")).lower() == "true" else "falso"
                cursor.execute(
                    "INSERT INTO respuestas_seleccion (respuesta, estado, id_pregunta) "
                    "VALUES (%s, %s, %s)",
                    (op["texto"], estado, id_pregunta),
                )
        else:
            cursor.execute("DELETE FROM respuestas_otras WHERE id_pregunta2=%s", (id_pregunta,))
            if tipo_pregunta == "completar":
                for op in opciones:
                    estado = "correcto" if op.get("correcta") else "distractor"
                    cursor.execute(
                        "INSERT INTO respuestas_otras (enunciado, complemento, id_pregunta2) "
                        "VALUES (%s, %s, %s)",
                        (estado, op["texto"], id_pregunta),
                    )
            elif tipo_pregunta == "relacionar":
                for par in opciones:
                    cursor.execute(
                        "INSERT INTO respuestas_otras (enunciado, complemento, id_pregunta2) "
                        "VALUES (%s, %s, %s)",
                        (par["col_a"], par["col_b"], id_pregunta),
                    )
        conn.commit()

        return jsonify({
            "id": id_pregunta, "tipo_tabla": tipo_tabla, "tipo": tipo_pregunta,
            "pregunta": pregunta_texto, "enunciado": enunciado, "puntos": puntos,
            "opciones": opciones, "archivo": nombre_archivo_para_db,
        })
    except (Exception, mysql.connector.Error) as err:
        conn.rollback()
        return jsonify({"error": f"Error en el servidor al actualizar: {err}"}), 500
    finally:
        cursor.close()
        conn.close()


@bp.route("/examen/<int:id_instrumento>/pregunta/eliminar", methods=["POST"])
def eliminar_pregunta(id_instrumento):
    if session.get("user_role") != "instructor":
        return jsonify({"error": "No autorizado"}), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión"}), 500

    cursor = conn.cursor()
    try:
        datos = request.get_json()
        id_pregunta = int(datos.get("id_pregunta"))
        tipo_tabla = datos.get("tipo_tabla")

        table_name = "preguntas_seleccion" if tipo_tabla == "seleccion" else "preguntas_otras"
        id_column = "id_pregunta" if tipo_tabla == "seleccion" else "id_pregunta2"

        cursor.execute(f"SELECT archivo FROM {table_name} WHERE {id_column} = %s", (id_pregunta,))
        result = cursor.fetchone()
        filename_to_delete = result[0] if result and result[0] else None

        if tipo_tabla == "seleccion":
            cursor.execute("DELETE FROM respuestas_seleccion WHERE id_pregunta = %s", (id_pregunta,))
            cursor.execute("DELETE FROM preguntas_seleccion WHERE id_pregunta = %s", (id_pregunta,))
        else:
            cursor.execute("DELETE FROM respuestas_otras WHERE id_pregunta2 = %s", (id_pregunta,))
            cursor.execute("DELETE FROM preguntas_otras WHERE id_pregunta2 = %s", (id_pregunta,))
        conn.commit()

        if filename_to_delete:
            filepath_to_delete = os.path.join(Config.IMAGE_UPLOAD_FOLDER, filename_to_delete)
            if os.path.exists(filepath_to_delete):
                os.remove(filepath_to_delete)

        return jsonify({"success": True})
    except (Exception, mysql.connector.Error) as err:
        conn.rollback()
        return jsonify({"error": f"No se pudo eliminar de la BD: {err}"}), 500
    finally:
        cursor.close()
        conn.close()