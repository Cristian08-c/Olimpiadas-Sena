"""Rutas de exámenes: listado, creación, publicación."""
from datetime import date

import mysql.connector
from flask import jsonify, redirect, render_template, request, session, url_for

from ...db import get_db_connection
from ..common.decorators import role_required
from .bp import bp


@bp.route("/instructor")
@role_required("instructor")
def inicio():
    conn = get_db_connection()
    if not conn:
        return "Error: No se pudo conectar a la base de datos.", 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id_instrumento, titulo, tipo, `fase(1-2)`, estado, fecha_creacion "
            "FROM instrumentos WHERE identificacion = %s",
            (session["user_id"],),
        )
        examenes = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return render_template("instructor/inicio_instructor.html", examenes=examenes)


@bp.route("/examen/crear", methods=["POST"])
def crear_examen():
    if session.get("user_role") != "instructor":
        return jsonify({"error": "No autorizado"}), 403

    datos = request.get_json(silent=True) or {}
    titulo = datos.get("titulo")
    tipo = datos.get("tipo")
    fase = datos.get("fase")
    duracion = datos.get("duracion")
    crear_proximo_ano = datos.get("crear_proximo_ano", False)

    if not all([titulo, tipo, fase, duracion]):
        return jsonify({"error": "Todos los campos son obligatorios."}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión a la base de datos."}), 500

    cursor = conn.cursor()
    try:
        ano_actual = date.today().year
        ano_destino = ano_actual + 1 if crear_proximo_ano else ano_actual
        cursor.execute(
            "SELECT id_instrumento FROM instrumentos "
            "WHERE tipo = %s AND `fase(1-2)` = %s AND YEAR(fecha_creacion) = %s",
            (tipo, fase, ano_destino),
        )
        conflicto = cursor.fetchone()

        if conflicto:
            if not crear_proximo_ano:
                return jsonify({
                    "error": f'Ya existe un examen de "{tipo}" para la fase {fase} en el año {ano_actual}.',
                    "conflicto_anual": True,
                }), 409
            return jsonify({
                "error": f'Ya existe un examen de "{tipo}" para la fase {fase} también en el año {ano_destino}.',
                "conflicto_anual": False,
            }), 409

        fecha_examen = date(ano_destino, 1, 1)
        cursor.execute(
            "INSERT INTO instrumentos "
            "(titulo, tipo, `fase(1-2)`, estado, duracion, identificacion, fecha_creacion) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (titulo, tipo, fase, "borrador", duracion, session["user_id"], fecha_examen),
        )
        conn.commit()
        id_instrumento_nuevo = cursor.lastrowid
        return jsonify({
            "id_instrumento": id_instrumento_nuevo,
            "titulo": titulo, "tipo": tipo, "fase": fase,
            "estado": "borrador", "ano": ano_destino,
        }), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"error": f"No se pudo crear el examen: {err}"}), 500
    finally:
        cursor.close()
        conn.close()


@bp.route("/examen/<int:id_instrumento>/publicar", methods=["POST"])
def publicar_examen(id_instrumento):
    if session.get("user_role") != "instructor":
        return jsonify({"error": "No autorizado"}), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión"}), 500

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM preguntas_seleccion WHERE id_instrumento = %s",
            (id_instrumento,),
        )
        count1 = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM preguntas_otras WHERE id_instrumento = %s",
            (id_instrumento,),
        )
        count2 = cursor.fetchone()[0]
        if (count1 + count2) == 0:
            return jsonify({"error": "El examen debe tener al menos una pregunta."}), 400

        cursor.execute(
            "UPDATE instrumentos SET estado = 'publico' "
            "WHERE id_instrumento = %s AND identificacion = %s",
            (id_instrumento, session["user_id"]),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Instrumento no encontrado o no autorizado."}), 404
        return jsonify({"success": True, "message": "Examen publicado correctamente."})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"error": f"No se pudo publicar el examen: {err}"}), 500
    finally:
        cursor.close()
        conn.close()