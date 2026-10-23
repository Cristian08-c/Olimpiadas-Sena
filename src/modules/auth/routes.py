"""Rutas de autenticación."""
from flask import (
    flash, jsonify, redirect, render_template, request, session, url_for,
)

import mysql.connector

from ...db import get_db_connection
from .bp import bp


@bp.route("/")
def index():
    if "user_role" in session:
        if session["user_role"] == "instructor":
            return redirect(url_for("inicio_instructor"))
        elif session["user_role"] == "aprendiz":
            return redirect(url_for("aprendiz_dashboard"))
        elif session["user_role"] == "admin":
            return redirect(url_for("admin_dashboard"))

    return render_template("index.html")


@bp.route("/login", methods=["POST"])
def login():
    document = request.form.get("document")
    password = request.form.get("password")
    if not document or not password:
        return jsonify(
            {"success": False, "message": "Documento y contraseña son requeridos."}
        )

    conn = get_db_connection()
    if not conn:
        return jsonify(
            {"success": False, "message": "Error de conexión con la base de datos."}
        )

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT identificacion, nombre, apellido, rol "
            "FROM personas "
            "WHERE identificacion = %s AND contraseña = %s AND estado = 'activo'",
            (document, password),
        )
        user = cursor.fetchone()

        if user:
            session["user_id"] = user["identificacion"]
            session["user_name"] = user["nombre"]
            session["user_apellido"] = user["apellido"]
            session["user_role"] = user["rol"]

            if user["rol"] == "instructor":
                redirect_url = url_for("inicio_instructor")
            elif user["rol"] == "aprendiz":
                redirect_url = url_for("aprendiz_dashboard")
            elif user["rol"] == "admin":
                redirect_url = url_for("admin_dashboard")
            else:
                redirect_url = url_for("auth.index")

            return jsonify(
                {
                    "success": True,
                    "message": "Inicio de sesión exitoso.",
                    "redirect": redirect_url,
                }
            )
        else:
            return jsonify(
                {"success": False, "message": "Credenciales incorrectas o usuario inactivo."}
            )
    except mysql.connector.Error as err:
        return jsonify({"success": False, "message": f"Error en la consulta: {err}"})
    finally:
        cursor.close()
        conn.close()


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.index"))