"""Rutas de ranking y asignación de Fase 2."""
from datetime import datetime

import mysql.connector
from flask import flash, jsonify, redirect, render_template, request, session, url_for

from ...db import get_db_connection
from ..common.decorators import role_required
from .bp import bp


@bp.route("/ranking/<int:id_instrumento>")
@role_required("instructor")
def ver_ranking(id_instrumento):
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for("instructor.inicio"))

    cursor = conn.cursor(dictionary=True)
    fase2_asignada = False
    examen = {}
    ranking = []
    try:
        cursor.execute(
            "SELECT id_instrumento, titulo, tipo, `fase(1-2)` as fase, "
            "YEAR(fecha_creacion) as anio "
            "FROM instrumentos WHERE id_instrumento = %s",
            (id_instrumento,),
        )
        examen = cursor.fetchone()
        if not examen:
            flash("Examen no encontrado.", "warning")
            return redirect(url_for("instructor.inicio"))

        if examen["fase"] == 1:
            try:
                cursor.execute(
                    "SELECT id_instrumento FROM instrumentos "
                    "WHERE tipo = %s AND YEAR(fecha_creacion) = %s AND `fase(1-2)` = 2",
                    (examen["tipo"], examen["anio"]),
                )
                examen_fase2 = cursor.fetchone()
                if examen_fase2:
                    cursor.execute(
                        "SELECT COUNT(*) as total FROM asignaciones WHERE id_instrumento = %s",
                        (examen_fase2["id_instrumento"],),
                    )
                    conteo = cursor.fetchone()
                    if conteo and conteo["total"] > 0:
                        fase2_asignada = True
            except mysql.connector.Error as err_fase2:
                print(f"Error al verificar asignaciones de Fase 2: {err_fase2}")

        cursor.execute(
            """
            SELECT
                p.identificacion, p.nombre, p.apellido,
                m.id_ficha, a.calificacion, a.tiempo_tomado
            FROM personas p
            JOIN matricula m ON p.identificacion = m.identificacion
            JOIN asignaciones a ON m.id_matricula = a.id_matricula
            WHERE a.id_instrumento = %s AND a.calificacion IS NOT NULL
            GROUP BY p.identificacion, p.nombre, p.apellido,
                     m.id_ficha, a.calificacion, a.tiempo_tomado
            ORDER BY a.calificacion DESC, a.tiempo_tomado ASC
            """,
            (id_instrumento,),
        )
        ranking = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f"Error al obtener el ranking: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "instructor/ranking.html",
        examen=examen,
        ranking=ranking,
        fase2_asignada=fase2_asignada,
    )


@bp.route("/ranking/asignar_fase2", methods=["POST"])
def asignar_fase2():
    if session.get("user_role") != "instructor":
        return jsonify({"error": "No autorizado"}), 403

    data = request.json
    id_instrumento_fase1 = data.get("id_instrumento_fase1")
    aprendices_ids = data.get("aprendices_ids")
    fecha_inicio_str = data.get("fecha_inicio")
    fecha_fin_str = data.get("fecha_fin")

    if not all([id_instrumento_fase1, aprendices_ids, fecha_inicio_str, fecha_fin_str]):
        return jsonify({"error": "Datos incompletos."}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión con la base de datos."}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT tipo, YEAR(fecha_creacion) as anio FROM instrumentos "
            "WHERE id_instrumento = %s",
            (id_instrumento_fase1,),
        )
        info_fase1 = cursor.fetchone()
        if not info_fase1:
            return jsonify({"error": "No se encontró el examen de Fase 1."}), 404

        cursor.execute(
            "SELECT id_instrumento FROM instrumentos "
            "WHERE tipo = %s AND YEAR(fecha_creacion) = %s "
            "AND `fase(1-2)` = 2 AND estado = 'publico'",
            (info_fase1["tipo"], info_fase1["anio"]),
        )
        examen_fase2 = cursor.fetchone()
        if not examen_fase2:
            return jsonify({
                "error": f"No se encontró un examen de Fase 2 (público) para "
                         f"'{info_fase1['tipo']}' del año {info_fase1['anio']}."
            }), 404

        id_instrumento_fase2 = examen_fase2["id_instrumento"]

        format_strings = ",".join(["%s"] * len(aprendices_ids))
        cursor.execute(
            f"SELECT m.id_matricula FROM matricula m "
            f"WHERE m.identificacion IN ({format_strings})",
            tuple(aprendices_ids),
        )
        matriculas = [row["id_matricula"] for row in cursor.fetchall()]
        if not matriculas:
            return jsonify({"error": "No se encontraron matrículas para los aprendices seleccionados."}), 404

        fecha_inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%dT%H:%M")
        fecha_fin = datetime.strptime(fecha_fin_str, "%Y-%m-%dT%H:%M")

        asignaciones_a_insertar = [
            (id_mat, id_instrumento_fase2, fecha_inicio, fecha_fin, 0)
            for id_mat in matriculas
        ]

        cursor.executemany(
            """
            INSERT INTO asignaciones
            (id_matricula, id_instrumento, fecha_inicio, fecha_fin, calificacion)
            VALUES (%s, %s, %s, %s, %s)
            AS new
            ON DUPLICATE KEY UPDATE
                fecha_inicio = new.fecha_inicio,
                fecha_fin = new.fecha_fin
            """,
            asignaciones_a_insertar,
        )
        conn.commit()
        return jsonify({"success": True, "message": f"Se asignaron {cursor.rowcount} aprendices a la Fase 2."})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"error": f"Error de base de datos: {err}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error inesperado: {e}"}), 500
    finally:
        cursor.close()
        conn.close()