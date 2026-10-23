"""Endpoints JSON del examen (fetch desde prueba.html)."""
import mysql.connector
from flask import jsonify, request, session, url_for

from ...db import get_db_connection
from ..common.scoring import calcular_puntuacion, construir_respuestas_correctas
from .bp import bp


@bp.route("/api/examen/<int:id_instrumento>/preguntas")
def get_preguntas_examen(id_instrumento):
    # API: no usa @role_required (que redirige/aborta con HTML).
    # Devolvemos 401/403 JSON. Validación de asignación → Paso 6 (seguridad).
    if session.get("user_role") != "aprendiz":
        return jsonify({"error": "No autorizado"}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión"}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id_pregunta, pregunta, enunciado, archivo, puntos, "
            "'seleccion_multiple' as tipo "
            "FROM preguntas_seleccion WHERE id_instrumento = %s",
            (id_instrumento,),
        )
        preguntas_seleccion = cursor.fetchall()
        for p in preguntas_seleccion:
            p["unique_id"] = f"sel_{p['id_pregunta']}"
            cursor.execute(
                "SELECT respuesta, estado FROM respuestas_seleccion WHERE id_pregunta = %s",
                (p["id_pregunta"],),
            )
            p["opciones"] = [
                {"texto": r["respuesta"], "correcta": r["estado"] == "verdadero"}
                for r in cursor.fetchall()
            ]

        cursor.execute(
            "SELECT id_pregunta2 as id_pregunta, pregunta, tipo, enunciado, archivo, puntos "
            "FROM preguntas_otras WHERE id_instrumento = %s",
            (id_instrumento,),
        )
        preguntas_otras = cursor.fetchall()
        for p in preguntas_otras:
            p["unique_id"] = f"otr_{p['id_pregunta']}"
            cursor.execute(
                "SELECT enunciado, complemento FROM respuestas_otras WHERE id_pregunta2 = %s",
                (p["id_pregunta"],),
            )
            respuestas = cursor.fetchall()
            if p["tipo"] == "completar":
                p["opciones"] = {
                    "correct": [r["complemento"] for r in respuestas if r["enunciado"] == "correcto"],
                    "distractors": [r["complemento"] for r in respuestas if r["enunciado"] == "distractor"],
                }
            elif p["tipo"] == "relacionar":
                p["opciones"] = [{"a": r["enunciado"], "b": r["complemento"]} for r in respuestas]

        todas_preguntas = preguntas_seleccion + preguntas_otras
        for p in todas_preguntas:
            if p.get("archivo"):
                p["archivo_url"] = url_for("static", filename=f'img/{p["archivo"]}')

        return jsonify(todas_preguntas)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@bp.route("/api/examen/finalizar", methods=["POST"])
def finalizar_examen():
    if session.get("user_role") != "aprendiz":
        return jsonify({"error": "No autorizado"}), 403

    data = request.get_json(silent=True) or {}
    id_instrumento = data.get("id_instrumento")
    respuestas_usuario = data.get("respuestas")
    tiempo_tomado = data.get("tiempo_tomado")

    if not id_instrumento or respuestas_usuario is None or tiempo_tomado is None:
        return jsonify({"error": "Datos incompletos"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión"}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Respuestas correctas (misma consulta que antes)
        cursor.execute(
            "SELECT p.id_pregunta, p.puntos, r.respuesta "
            "FROM preguntas_seleccion p "
            "JOIN respuestas_seleccion r ON p.id_pregunta = r.id_pregunta "
            "WHERE p.id_instrumento = %s AND r.estado = 'verdadero'",
            (id_instrumento,),
        )
        rows_seleccion = cursor.fetchall()

        cursor.execute(
            "SELECT p.id_pregunta2, p.tipo, p.puntos, r.enunciado, r.complemento, r.id_respuesta2 "
            "FROM preguntas_otras p "
            "JOIN respuestas_otras r ON p.id_pregunta2 = r.id_pregunta2 "
            "WHERE p.id_instrumento = %s "
            "ORDER BY p.id_pregunta2, r.id_respuesta2 ASC",
            (id_instrumento,),
        )
        rows_otras = cursor.fetchall()

        # 2. Cálculo (toda la lógica vive en scoring.py)
        respuestas_correctas = construir_respuestas_correctas(rows_seleccion, rows_otras)
        puntuacion_total, desglose = calcular_puntuacion(respuestas_usuario, respuestas_correctas)

        # 3. Persistir
        cursor.execute(
            "UPDATE asignaciones a "
            "JOIN matricula m ON a.id_matricula = m.id_matricula "
            "SET a.calificacion = %s, a.tiempo_tomado = %s "
            "WHERE m.identificacion = %s AND a.id_instrumento = %s",
            (round(puntuacion_total), int(tiempo_tomado), session["user_id"], id_instrumento),
        )
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "No se pudo registrar la calificación. Asignación no encontrada."}), 404

        return jsonify({
            "success": True,
            "calificacion": round(puntuacion_total),
            "puntaje_maximo": desglose["_resumen"]["puntos_maximos"],
        })
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"error": f"Error en la base de datos: {err}"}), 500
    finally:
        cursor.close()
        conn.close()