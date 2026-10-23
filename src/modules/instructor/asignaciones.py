"""Rutas de asignación de exámenes a fichas."""
from datetime import datetime

import mysql.connector
from flask import jsonify, request, session

from ...db import get_db_connection
from .bp import bp


@bp.route("/examen/<int:id_instrumento>/fichas_disponibles", methods=["GET"])
def fichas_disponibles(id_instrumento):
    if session.get("user_role") != "instructor":
        return jsonify({"error": "No autorizado"}), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión"}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                f.id_ficha,
                f.nombre,
                f.estado,
                (SELECT COUNT(DISTINCT m.identificacion)
                 FROM matricula m
                 JOIN personas p ON m.identificacion = p.identificacion
                 WHERE m.id_ficha = f.id_ficha AND p.activo = 1) AS aprendices_activos,
                (
                    SELECT COUNT(*) > 0
                    FROM asignaciones a
                    JOIN matricula m ON a.id_matricula = m.id_matricula
                    WHERE m.id_ficha = f.id_ficha AND a.id_instrumento = %s
                ) AS ya_asignado
            FROM fichas f
            WHERE f.activo = 1
            ORDER BY ya_asignado ASC, f.id_ficha;
            """,
            (id_instrumento,),
        )
        fichas = cursor.fetchall()
        for ficha in fichas:
            ficha["ya_asignado"] = bool(ficha["ya_asignado"])
        return jsonify(fichas)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@bp.route("/examen/<int:id_instrumento>/asignar", methods=["POST"])
def asignar(id_instrumento):
    if session.get("user_role") != "instructor":
        return jsonify({"error": "No autorizado"}), 403

    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No se recibieron datos en la solicitud."}), 400

        fichas_ids_raw = data.get("fichas_ids", [])
        fecha_inicio_str = data.get("fecha_inicio")
        fecha_fin_str = data.get("fecha_fin")

        if not fichas_ids_raw or not isinstance(fichas_ids_raw, list):
            return jsonify({"error": "Debe seleccionar al menos una ficha."}), 400
        if not fecha_inicio_str or not fecha_fin_str:
            return jsonify({"error": "Debe especificar fecha de inicio y fin."}), 400

        try:
            fichas_ids = [int(fid) for fid in fichas_ids_raw]
        except (ValueError, TypeError) as e:
            return jsonify({"error": f"IDs de fichas inválidos: {e}"}), 400

        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%dT%H:%M")
            fecha_fin = datetime.strptime(fecha_fin_str, "%Y-%m-%dT%H:%M")
        except ValueError as e:
            return jsonify({"error": f"Formato de fecha inválido: {e}"}), 400

        if fecha_fin <= fecha_inicio:
            return jsonify({"error": "La fecha de fin debe ser posterior a la fecha de inicio."}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Error de conexión con la base de datos."}), 500

        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id_instrumento, estado FROM instrumentos "
            "WHERE id_instrumento = %s AND identificacion = %s",
            (id_instrumento, session["user_id"]),
        )
        examen = cursor.fetchone()
        if not examen:
            return jsonify({"error": "Examen no encontrado o no autorizado."}), 404
        if examen["estado"] != "publico":
            return jsonify({"error": "Solo se pueden asignar exámenes publicados."}), 400

        format_strings = ",".join(["%s"] * len(fichas_ids))
        cursor.execute(
            f"""
            SELECT m.id_matricula
            FROM matricula m
            JOIN personas p ON m.identificacion = p.identificacion
            WHERE m.id_ficha IN ({format_strings})
            AND p.activo = 1
            AND p.rol = 'aprendiz'
            """,
            tuple(fichas_ids),
        )
        todas_las_matriculas = [row["id_matricula"] for row in cursor.fetchall()]

        if not todas_las_matriculas:
            return jsonify({
                "success": True,
                "message": "No se encontraron aprendices activos en las fichas seleccionadas.",
            }), 200

        matriculas_placeholders = ",".join(["%s"] * len(todas_las_matriculas))
        cursor.execute(
            f"SELECT id_matricula FROM asignaciones "
            f"WHERE id_instrumento = %s AND id_matricula IN ({matriculas_placeholders})",
            tuple([id_instrumento] + todas_las_matriculas),
        )
        matriculas_existentes = {row["id_matricula"] for row in cursor.fetchall()}
        matriculas_a_asignar = [m for m in todas_las_matriculas if m not in matriculas_existentes]

        if not matriculas_a_asignar:
            return jsonify({
                "success": True,
                "message": "Todos los aprendices seleccionados ya tienen este examen asignado.",
            })

        asignaciones_a_insertar = [
            (id_mat, id_instrumento, fecha_inicio, fecha_fin, 0)
            for id_mat in matriculas_a_asignar
        ]
        cursor.executemany(
            "INSERT INTO asignaciones "
            "(id_matricula, id_instrumento, fecha_inicio, fecha_fin, calificacion) "
            "VALUES (%s, %s, %s, %s, %s)",
            asignaciones_a_insertar,
        )
        conn.commit()

        return jsonify({
            "success": True,
            "message": f"Examen asignado exitosamente a {len(matriculas_a_asignar)} aprendices en {len(fichas_ids)} ficha(s).",
        })
    except mysql.connector.Error as err:
        print(f"Error de MySQL en asignar: {err}")
        return jsonify({"error": f"Error en la base de datos: {err}"}), 500
    except Exception as e:
        print(f"Error inesperado en asignar: {e}")
        return jsonify({"error": f"Ocurrió un error inesperado: {e}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()