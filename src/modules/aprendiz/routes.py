"""Rutas del panel de aprendiz (páginas HTML)."""
from datetime import timedelta

import mysql.connector
from flask import flash, redirect, render_template, session, url_for

from ...db import get_db_connection
from ..common.decorators import role_required
from .bp import bp


@bp.route("/aprendiz")
@role_required("aprendiz")
def dashboard():
    nombre_completo = f"{session.get('user_name', '')} {session.get('user_apellido', '')}".strip()
    usuario = {"nombre": session.get("user_name"), "nombre_completo": nombre_completo}

    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos", "error")
        return render_template("aprendiz/evaluations.html", usuario=usuario, examenes={})

    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT
                i.id_instrumento, i.titulo, i.tipo, i.`fase(1-2)` AS fase, i.duracion,
                a.fecha_fin, a.calificacion,
                (
                    SELECT SUM(p.puntos)
                    FROM (
                        SELECT puntos, id_instrumento FROM preguntas_seleccion
                        UNION ALL
                        SELECT puntos, id_instrumento FROM preguntas_otras
                    ) AS p
                    WHERE p.id_instrumento = i.id_instrumento
                ) AS puntaje_maximo
            FROM asignaciones a
            JOIN instrumentos i ON a.id_instrumento = i.id_instrumento
            JOIN matricula m ON a.id_matricula = m.id_matricula
            WHERE m.identificacion = %s AND i.estado = 'publico'
        """
        cursor.execute(query, (session["user_id"],))
        examenes_asignados = cursor.fetchall()

        examenes_organizados = {}
        for examen in examenes_asignados:
            examen["duracion"] = (
                int(examen["duracion"].total_seconds() / 60)
                if isinstance(examen["duracion"], timedelta) else 0
            )
            if examen["puntaje_maximo"] is None:
                examen["puntaje_maximo"] = 0
            examenes_organizados[examen["tipo"]] = examen
    except mysql.connector.Error as err:
        flash(f"Error al obtener tus exámenes: {err}", "error")
        examenes_organizados = {}
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "aprendiz/evaluations.html",
        usuario=usuario,
        examenes=examenes_organizados,
    )


@bp.route("/aprendiz/prueba/<tipo>/<int:id_instrumento>")
@role_required("aprendiz")
def prueba(tipo, id_instrumento):
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for("aprendiz.dashboard"))

    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT
                i.id_instrumento, i.titulo, i.tipo, i.`fase(1-2)` as fase, i.duracion,
                a.id_asignacion, a.fecha_inicio, a.fecha_fin, a.calificacion
            FROM instrumentos i
            JOIN asignaciones a ON i.id_instrumento = a.id_instrumento
            JOIN matricula m ON a.id_matricula = m.id_matricula
            WHERE m.identificacion = %s
              AND i.id_instrumento = %s
              AND i.estado = 'publico'
              AND NOW() BETWEEN a.fecha_inicio AND a.fecha_fin
        """
        cursor.execute(query, (session["user_id"], id_instrumento))
        examen = cursor.fetchone()

        if not examen:
            flash("Este examen no está disponible para ti en este momento.", "warning")
            return redirect(url_for("aprendiz.dashboard"))

        if examen["calificacion"] is not None and examen["calificacion"] > 0:
            flash("Ya has completado este examen.", "info")
            return redirect(url_for("aprendiz.dashboard"))

        return render_template("aprendiz/prueba.html", examen=examen)
    except mysql.connector.Error as err:
        flash(f"Error al acceder al examen: {err}", "danger")
        return redirect(url_for("aprendiz.dashboard"))
    finally:
        cursor.close()
        conn.close()