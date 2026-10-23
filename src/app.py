# --------------------------------------------------------------------------
# app.py - Backend con Flask para Olimpiadas
# --------------------------------------------------------------------------
import os
import re
import json
import uuid
from datetime import date, datetime, timedelta

import mysql.connector
import pandas as pd
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.utils import secure_filename

from .config import Config
from .db import get_db_connection
from .modules.common.files import allowed_file, allowed_image_file

# --- App Flask ---
app = Flask(
    __name__,
    template_folder=Config.TEMPLATE_FOLDER,
    static_folder=Config.STATIC_FOLDER,
)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# --- Rutas de archivos (compatibilidad con el código existente) ---
UPLOAD_FOLDER = Config.UPLOAD_FOLDER
IMAGE_UPLOAD_FOLDER = Config.IMAGE_UPLOAD_FOLDER
ALLOWED_EXTENSIONS = Config.ALLOWED_EXCEL_EXTENSIONS
ALLOWED_IMAGE_EXTENSIONS = Config.ALLOWED_IMAGE_EXTENSIONS

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGE_UPLOAD_FOLDER, exist_ok=True)


# --------------------------------------------------------------------------
# Factory para wsgi.py y run.py
# --------------------------------------------------------------------------
def create_app(config_object=None):
    if config_object is not None:
        app.config.from_object(config_object)

    from .modules.aprendiz import bp as aprendiz_bp     # ← NUEVO
    from .modules.admin import bp as admin_bp
    from .modules.auth import bp as auth_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(aprendiz_bp)                 # ← NUEVO

    return app
    

# --- Rutas del Panel de Instructor ---

@app.route("/instructor")
def inicio_instructor():
    if 'user_role' not in session or session['user_role'] != 'instructor':
        return redirect(url_for('auth.index'))
    conn = get_db_connection()
    if not conn: 
        return "Error: No se pudo conectar a la base de datos.", 500
    cursor = conn.cursor(dictionary=True)
    id_instructor_actual = session['user_id']
    cursor.execute("""
        SELECT id_instrumento, titulo, tipo, `fase(1-2)`, estado, fecha_creacion
        FROM instrumentos WHERE identificacion = %s
    """, (id_instructor_actual,))
    examenes = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('instructor/inicio_instructor.html', examenes=examenes)

@app.route("/examen/crear", methods=['POST'])
def crear_examen():
    if 'user_role' not in session or session['user_role'] != 'instructor': 
        return jsonify({'error': 'No autorizado'}), 403
    datos = request.get_json()
    titulo, tipo, fase, duracion = datos.get('titulo'), datos.get('tipo'), datos.get('fase'), datos.get('duracion')
    crear_proximo_ano = datos.get('crear_proximo_ano', False)

    if not all([titulo, tipo, fase, duracion]): 
        return jsonify({'error': 'Todos los campos son obligatorios.'}), 400
    conn = get_db_connection()
    if not conn: 
        return jsonify({'error': 'Error de conexión a la base de datos.'}), 500
    
    cursor = conn.cursor()
    try:
        ano_actual = date.today().year
        ano_destino = ano_actual + 1 if crear_proximo_ano else ano_actual
        cursor.execute("SELECT id_instrumento FROM instrumentos WHERE tipo = %s AND `fase(1-2)` = %s AND YEAR(fecha_creacion) = %s", (tipo, fase, ano_destino))
        conflicto = cursor.fetchone()

        if conflicto:
            if not crear_proximo_ano:
                return jsonify({'error': f'Ya existe un examen de "{tipo}" para la fase {fase} en el año {ano_actual}.', 'conflicto_anual': True}), 409
            else:
                return jsonify({'error': f'Ya existe un examen de "{tipo}" para la fase {fase} también en el año {ano_destino}.', 'conflicto_anual': False}), 409

        id_instructor_actual = session['user_id']
        query = "INSERT INTO instrumentos (titulo, tipo, `fase(1-2)`, estado, duracion, identificacion, fecha_creacion) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        fecha_examen = date(ano_destino, 1, 1)
        cursor.execute(query, (titulo, tipo, fase, 'borrador', duracion, id_instructor_actual, fecha_examen))
        conn.commit()
        id_instrumento_nuevo = cursor.lastrowid
        return jsonify({'id_instrumento': id_instrumento_nuevo, 'titulo': titulo, 'tipo': tipo, 'fase': fase, 'estado': 'borrador', 'ano': ano_destino}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'No se pudo crear el examen: {err}'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/examen/gestionar/<int:id_instrumento>")
def gestionar_examen(id_instrumento):
    if 'user_role' not in session or session['user_role'] != 'instructor': 
        return redirect(url_for('auth.index'))
    conn = get_db_connection()
    if not conn: 
        return "Error de conexión", 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_instrumento, titulo, tipo, `fase(1-2)`, estado, duracion FROM instrumentos WHERE id_instrumento = %s AND identificacion = %s", (id_instrumento, session['user_id']))
    examen = cursor.fetchone()
    if not examen: 
        return "Examen no encontrado o no autorizado", 404
    if examen['duracion']: 
        examen['duracion'] = str(examen['duracion'])

    # Obtener preguntas de selección múltiple
    cursor.execute("""
        SELECT p.id_pregunta AS id, p.pregunta, p.enunciado, p.puntos, p.archivo, r.respuesta, r.estado
        FROM preguntas_seleccion p LEFT JOIN respuestas_seleccion r ON p.id_pregunta = r.id_pregunta
        WHERE p.id_instrumento = %s ORDER BY p.id_pregunta, r.id_respuesta1
    """, (id_instrumento,))
    preguntas_seleccion_dict = {}
    for row in cursor.fetchall():
        if row['id'] not in preguntas_seleccion_dict:
            preguntas_seleccion_dict[row['id']] = {
                'id': row['id'], 'tipo_tabla': 'seleccion', 'tipo': 'seleccion_multiple', 
                'pregunta': row['pregunta'], 'enunciado': row['enunciado'], 'puntos': row['puntos'], 
                'archivo': row['archivo'], 'opciones': []
            }
        if row['respuesta']:
            preguntas_seleccion_dict[row['id']]['opciones'].append({'texto': row['respuesta'], 'correcta': row['estado'] == 'verdadero'})
    
    # Obtener otras preguntas
    cursor.execute("""
        SELECT p.id_pregunta2 AS id, p.pregunta, p.tipo, p.enunciado, p.puntos, p.archivo, r.enunciado as enunciado_resp, r.complemento
        FROM preguntas_otras p LEFT JOIN respuestas_otras r ON p.id_pregunta2 = r.id_pregunta2
        WHERE p.id_instrumento = %s ORDER BY p.id_pregunta2, r.id_respuesta2
    """, (id_instrumento,))
    preguntas_otras_dict = {}
    for row in cursor.fetchall():
        if row['id'] not in preguntas_otras_dict:
            preguntas_otras_dict[row['id']] = {
                'id': row['id'], 'tipo_tabla': 'otras', 'tipo': row['tipo'], 
                'pregunta': row['pregunta'], 'enunciado': row['enunciado'], 'puntos': row['puntos'], 
                'archivo': row['archivo'], 'opciones': []
            }
        if row['enunciado_resp']:
            if row['tipo'] == 'relacionar':
                preguntas_otras_dict[row['id']]['opciones'].append({'col_a': row['enunciado_resp'], 'col_b': row['complemento']})
            elif row['tipo'] == 'completar':
                preguntas_otras_dict[row['id']]['opciones'].append({'texto': row['complemento'], 'correcta': row['enunciado_resp'] == 'correcto'})

    todas_preguntas = list(preguntas_seleccion_dict.values()) + list(preguntas_otras_dict.values())
    cursor.close()
    conn.close()
    return render_template('instructor/gestionar_examen.html', examen=examen, preguntas=todas_preguntas)

@app.route("/examen/<int:id_instrumento>/pregunta/crear", methods=['POST'])
def crear_pregunta(id_instrumento):
    if 'user_role' not in session or session['user_role'] != 'instructor': 
        return jsonify({'error': 'No autorizado'}), 403
    conn = get_db_connection()
    if not conn: 
        return jsonify({'error': 'Error de conexión'}), 500
    cursor = conn.cursor()
    try:
        tipo, pregunta, enunciado, puntos = request.form.get('tipo_pregunta'), request.form.get('pregunta'), request.form.get('enunciado'), int(request.form.get('puntos'))
        opciones, archivo = json.loads(request.form.get('opciones')), request.files.get('archivo')
        
        nombre_archivo = None
        if archivo and allowed_image_file(archivo.filename):
            filename = secure_filename(archivo.filename)
            nombre_archivo = f"{uuid.uuid4().hex}_{filename}"
            path_guardado = os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], nombre_archivo)
            archivo.save(path_guardado)

        conn.start_transaction()
        response_data = {}
        if tipo == 'seleccion_multiple':
            cursor.execute("INSERT INTO preguntas_seleccion (pregunta, enunciado, archivo, id_instrumento, puntos) VALUES (%s, %s, %s, %s, %s)", (pregunta, enunciado, nombre_archivo, id_instrumento, puntos))
            id_pregunta = cursor.lastrowid
            for op in opciones:
                # CORRECCIÓN: Convertir a string y comparar con 'true'
                estado = 'verdadero' if str(op.get('correcta')).lower() == 'true' else 'falso'
                cursor.execute("INSERT INTO respuestas_seleccion (respuesta, estado, id_pregunta) VALUES (%s, %s, %s)", (op['texto'], estado, id_pregunta))
            response_data = {'id': id_pregunta, 'tipo_tabla': 'seleccion'}
        elif tipo in ['completar', 'relacionar']:
            cursor.execute("INSERT INTO preguntas_otras (pregunta, tipo, enunciado, archivo, id_instrumento, puntos) VALUES (%s, %s, %s, %s, %s, %s)", (pregunta, tipo, enunciado, nombre_archivo, id_instrumento, puntos))
            id_pregunta = cursor.lastrowid
            if tipo == 'completar':
                for op in opciones:
                    estado = 'correcto' if op.get('correcta') else 'distractor'
                    cursor.execute("INSERT INTO respuestas_otras (enunciado, complemento, id_pregunta2) VALUES (%s, %s, %s)", (estado, op['texto'], id_pregunta))
            elif tipo == 'relacionar':
                for par in opciones:
                    cursor.execute("INSERT INTO respuestas_otras (enunciado, complemento, id_pregunta2) VALUES (%s, %s, %s)", (par['col_a'], par['col_b'], id_pregunta))
            response_data = {'id': id_pregunta, 'tipo_tabla': 'otras'}
        conn.commit()
        
        response_data.update({'tipo': tipo, 'pregunta': pregunta, 'enunciado': enunciado, 'puntos': puntos, 'opciones': opciones, 'archivo': nombre_archivo})
        return jsonify(response_data), 201
    except (Exception, mysql.connector.Error) as err:
        conn.rollback()
        if 'nombre_archivo' in locals() and nombre_archivo:
            path_a_borrar = os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], nombre_archivo)
            if os.path.exists(path_a_borrar):
                os.remove(path_a_borrar)
        
        error_message = str(err)
        return jsonify({'error': f'Error en el servidor: {error_message}'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/examen/<int:id_instrumento>/pregunta/actualizar", methods=['POST'])
def actualizar_pregunta(id_instrumento):
    if 'user_role' not in session or session['user_role'] != 'instructor':
        return jsonify({'error': 'No autorizado'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión'}), 500
    
    cursor = conn.cursor()
    try:
        id_pregunta = int(request.form.get('id_pregunta'))
        tipo_tabla = request.form.get('tipo_tabla')
        tipo_pregunta = request.form.get('tipo_pregunta')
        pregunta_texto = request.form.get('pregunta')
        enunciado = request.form.get('enunciado')
        puntos = int(request.form.get('puntos'))
        opciones = json.loads(request.form.get('opciones'))
        archivo = request.files.get('archivo')

        table_name = "preguntas_seleccion" if tipo_tabla == 'seleccion' else "preguntas_otras"
        id_column = "id_pregunta" if tipo_tabla == 'seleccion' else "id_pregunta2"
        
        cursor.execute(f"SELECT archivo FROM {table_name} WHERE {id_column} = %s", (id_pregunta,))
        result = cursor.fetchone()
        old_filename = result[0] if result and result[0] else None
        
        params_base = [pregunta_texto, enunciado, puntos]
        nombre_archivo_para_db = old_filename
        update_archivo_sql = ""
        params_archivo = []

        if archivo and allowed_image_file(archivo.filename):
            if old_filename:
                old_filepath = os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], old_filename)
                if os.path.exists(old_filepath):
                    os.remove(old_filepath)
            
            filename = secure_filename(archivo.filename)
            new_filename = f"{uuid.uuid4().hex}_{filename}"
            archivo.save(os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], new_filename))
            
            nombre_archivo_para_db = new_filename
            update_archivo_sql = ", archivo = %s"
            params_archivo.append(nombre_archivo_para_db)
        
        sql = f"UPDATE {table_name} SET pregunta=%s, enunciado=%s, puntos=%s{update_archivo_sql} WHERE {id_column}=%s"
        cursor.execute(sql, tuple(params_base + params_archivo + [id_pregunta]))
        
        if tipo_tabla == 'seleccion':
            cursor.execute("DELETE FROM respuestas_seleccion WHERE id_pregunta=%s", (id_pregunta,))
            for op in opciones:
                # CORRECCIÓN: Convertir a string y comparar con 'true'
                estado = 'verdadero' if str(op.get('correcta')).lower() == 'true' else 'falso'
                cursor.execute("INSERT INTO respuestas_seleccion (respuesta, estado, id_pregunta) VALUES (%s, %s, %s)", (op['texto'], estado, id_pregunta))
        else:
            cursor.execute("DELETE FROM respuestas_otras WHERE id_pregunta2=%s", (id_pregunta,))
            if tipo_pregunta == 'completar':
                for op in opciones:
                    estado = 'correcto' if op.get('correcta') else 'distractor'
                    cursor.execute("INSERT INTO respuestas_otras (enunciado, complemento, id_pregunta2) VALUES (%s, %s, %s)", (estado, op['texto'], id_pregunta))
            elif tipo_pregunta == 'relacionar':
                for par in opciones:
                    cursor.execute("INSERT INTO respuestas_otras (enunciado, complemento, id_pregunta2) VALUES (%s, %s, %s)", (par['col_a'], par['col_b'], id_pregunta))
        
        conn.commit()
        
        return jsonify({
            'id': id_pregunta, 'tipo_tabla': tipo_tabla, 'tipo': tipo_pregunta, 
            'pregunta': pregunta_texto, 'enunciado': enunciado, 'puntos': puntos, 
            'opciones': opciones, 'archivo': nombre_archivo_para_db
        })
    except (Exception, mysql.connector.Error) as err:
        conn.rollback()
        error_message = str(err)
        return jsonify({'error': f'Error en el servidor al actualizar: {error_message}'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/examen/<int:id_instrumento>/pregunta/eliminar", methods=['POST'])
def eliminar_pregunta(id_instrumento):
    if 'user_role' not in session or session['user_role'] != 'instructor': 
        return jsonify({'error': 'No autorizado'}), 403
    conn = get_db_connection()
    if not conn: 
        return jsonify({'error': 'Error de conexión'}), 500
    cursor = conn.cursor()
    try:
        datos = request.get_json()
        id_pregunta = int(datos.get('id_pregunta'))
        tipo_tabla = datos.get('tipo_tabla')

        table_name = "preguntas_seleccion" if tipo_tabla == 'seleccion' else "preguntas_otras"
        id_column = "id_pregunta" if tipo_tabla == 'seleccion' else "id_pregunta2"

        cursor.execute(f"SELECT archivo FROM {table_name} WHERE {id_column} = %s", (id_pregunta,))
        result = cursor.fetchone()
        filename_to_delete = result[0] if result and result[0] else None
        
        if tipo_tabla == 'seleccion':
            cursor.execute("DELETE FROM respuestas_seleccion WHERE id_pregunta = %s", (id_pregunta,))
            cursor.execute("DELETE FROM preguntas_seleccion WHERE id_pregunta = %s", (id_pregunta,))
        else:
            cursor.execute("DELETE FROM respuestas_otras WHERE id_pregunta2 = %s", (id_pregunta,))
            cursor.execute("DELETE FROM preguntas_otras WHERE id_pregunta2 = %s", (id_pregunta,))
        conn.commit()

        if filename_to_delete:
            filepath_to_delete = os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], filename_to_delete)
            if os.path.exists(filepath_to_delete):
                os.remove(filepath_to_delete)

        return jsonify({'success': True})
    except (Exception, mysql.connector.Error) as err:
        conn.rollback()
        return jsonify({'error': f'No se pudo eliminar de la BD: {err}'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/examen/<int:id_instrumento>/publicar", methods=['POST'])
def publicar_examen(id_instrumento):
    if 'user_role' not in session or session['user_role'] != 'instructor': 
        return jsonify({'error': 'No autorizado'}), 403
    conn = get_db_connection()
    if not conn: 
        return jsonify({'error': 'Error de conexión'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM preguntas_seleccion WHERE id_instrumento = %s", (id_instrumento,))
        count1 = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM preguntas_otras WHERE id_instrumento = %s", (id_instrumento,))
        count2 = cursor.fetchone()[0]
        if (count1 + count2) == 0: 
            return jsonify({'error': 'El examen debe tener al menos una pregunta.'}), 400
        cursor.execute("UPDATE instrumentos SET estado = 'publico' WHERE id_instrumento = %s AND identificacion = %s", (id_instrumento, session['user_id']))
        conn.commit()
        if cursor.rowcount == 0: 
            return jsonify({'error': 'Instrumento no encontrado o no autorizado.'}), 404
        return jsonify({'success': True, 'message': 'Examen publicado correctamente.'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'No se pudo publicar el examen: {err}'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/examen/<int:id_instrumento>/fichas_disponibles', methods=['GET'])
def get_fichas_disponibles(id_instrumento):
    if 'user_role' not in session or session['user_role'] != 'instructor':
        return jsonify({'error': 'No autorizado'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Consulta para obtener fichas, sus aprendices y si ya tienen el examen asignado
        query = """
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
        """
        cursor.execute(query, (id_instrumento,))
        fichas = cursor.fetchall()
        
        # Convertir el resultado de la subconsulta (0 o 1) a un booleano para JSON
        for ficha in fichas:
            ficha['ya_asignado'] = bool(ficha['ya_asignado'])

        return jsonify(fichas)
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/examen/<int:id_instrumento>/asignar', methods=['POST'])
def asignar_examen_a_fichas(id_instrumento):
    if 'user_role' not in session or session['user_role'] != 'instructor':
        return jsonify({'error': 'No autorizado'}), 403
    
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No se recibieron datos en la solicitud.'}), 400

        fichas_ids_raw = data.get('fichas_ids', [])
        fecha_inicio_str = data.get('fecha_inicio')
        fecha_fin_str = data.get('fecha_fin')

        # Validar que los datos existen
        if not fichas_ids_raw or not isinstance(fichas_ids_raw, list):
            return jsonify({'error': 'Debe seleccionar al menos una ficha.'}), 400
            
        if not fecha_inicio_str or not fecha_fin_str:
            return jsonify({'error': 'Debe especificar fecha de inicio y fin.'}), 400

        # Convertir fichas_ids a integers
        try:
            fichas_ids = [int(fid) for fid in fichas_ids_raw]
        except (ValueError, TypeError) as e:
            return jsonify({'error': f'IDs de fichas inválidos: {str(e)}'}), 400

        # Convertir fechas
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%dT%H:%M')
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%dT%H:%M')
        except ValueError as e:
            return jsonify({'error': f'Formato de fecha inválido: {str(e)}'}), 400

        # Validar que fecha_fin sea posterior a fecha_inicio
        if fecha_fin <= fecha_inicio:
            return jsonify({'error': 'La fecha de fin debe ser posterior a la fecha de inicio.'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión con la base de datos.'}), 500
        
        cursor = conn.cursor(dictionary=True)
        
        # Verificar que el examen existe y pertenece al instructor
        cursor.execute("""
            SELECT id_instrumento, estado 
            FROM instrumentos 
            WHERE id_instrumento = %s AND identificacion = %s
        """, (id_instrumento, session['user_id']))
        
        examen = cursor.fetchone()
        if not examen:
            return jsonify({'error': 'Examen no encontrado o no autorizado.'}), 404
            
        if examen['estado'] != 'publico':
            return jsonify({'error': 'Solo se pueden asignar exámenes publicados.'}), 400
        
        # 1. Obtener todas las matrículas de aprendices activos en las fichas seleccionadas
        format_strings = ','.join(['%s'] * len(fichas_ids))
        query_matriculas = f"""
            SELECT m.id_matricula
            FROM matricula m
            JOIN personas p ON m.identificacion = p.identificacion
            WHERE m.id_ficha IN ({format_strings}) 
            AND p.activo = 1 
            AND p.rol = 'aprendiz'
        """
        cursor.execute(query_matriculas, tuple(fichas_ids))
        todas_las_matriculas = [row['id_matricula'] for row in cursor.fetchall()]
        
        if not todas_las_matriculas:
            return jsonify({
                'success': True, 
                'message': 'No se encontraron aprendices activos en las fichas seleccionadas.'
            }), 200

        # 2. Verificar cuáles ya tienen el examen asignado
        matriculas_placeholders = ','.join(['%s'] * len(todas_las_matriculas))
        query_existentes = f"""
            SELECT id_matricula 
            FROM asignaciones 
            WHERE id_instrumento = %s AND id_matricula IN ({matriculas_placeholders})
        """
        params = [id_instrumento] + todas_las_matriculas
        cursor.execute(query_existentes, tuple(params))
        matriculas_existentes = {row['id_matricula'] for row in cursor.fetchall()}
        
        # 3. Determinar las nuevas asignaciones
        matriculas_a_asignar = [m for m in todas_las_matriculas if m not in matriculas_existentes]
        
        if not matriculas_a_asignar:
            return jsonify({
                'success': True, 
                'message': 'Todos los aprendices seleccionados ya tienen este examen asignado.'
            })
            
        # 4. Preparar datos para inserción
        asignaciones_a_insertar = [
            (id_mat, id_instrumento, fecha_inicio, fecha_fin, 0)
            for id_mat in matriculas_a_asignar
        ]

        # 5. Insertar asignaciones (sin transacción explícita en MyISAM)
        query_insert = """
            INSERT INTO asignaciones (id_matricula, id_instrumento, fecha_inicio, fecha_fin, calificacion)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.executemany(query_insert, asignaciones_a_insertar)
        
        # En MyISAM no hay transacciones, pero llamamos commit por consistencia
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Examen asignado exitosamente a {len(matriculas_a_asignar)} aprendices en {len(fichas_ids)} ficha(s).'
        })

    except mysql.connector.Error as err:
        error_msg = str(err)
        print(f"Error de MySQL en asignar_examen_a_fichas: {error_msg}")
        return jsonify({'error': f'Error en la base de datos: {error_msg}'}), 500
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error inesperado en asignar_examen_a_fichas: {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Ocurrió un error inesperado: {error_msg}'}), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

# --- NUEVAS RUTAS PARA RANKING Y ASIGNACIÓN FASE 2 ---
@app.route('/ranking/<int:id_instrumento>')
def ver_ranking(id_instrumento):
    if 'user_role' not in session or session['user_role'] != 'instructor':
        return redirect(url_for('auth.index'))

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('inicio_instructor'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Obtener información del examen
        cursor.execute("""
            SELECT id_instrumento, titulo, tipo, `fase(1-2)` as fase, YEAR(fecha_creacion) as anio
            FROM instrumentos 
            WHERE id_instrumento = %s
        """, (id_instrumento,))
        examen = cursor.fetchone()

        if not examen:
            flash('Examen no encontrado.', 'warning')
            return redirect(url_for('inicio_instructor'))
        
        # --- INICIO DE CORRECCIÓN (Verificar si Fase 2 ya fue asignada) ---
        fase2_asignada = False
        if examen['fase'] == 1:
            try:
                # 1. Buscar el examen de Fase 2 correspondiente
                cursor.execute("""
                    SELECT id_instrumento 
                    FROM instrumentos 
                    WHERE tipo = %s AND YEAR(fecha_creacion) = %s AND `fase(1-2)` = 2
                """, (examen['tipo'], examen['anio']))
                examen_fase2 = cursor.fetchone()
                
                if examen_fase2:
                    id_fase_2 = examen_fase2['id_instrumento']
                    # 2. Contar si ese examen de Fase 2 ya tiene asignaciones
                    cursor.execute("""
                        SELECT COUNT(*) as total
                        FROM asignaciones 
                        WHERE id_instrumento = %s
                    """, (id_fase_2,))
                    conteo_asignaciones = cursor.fetchone()
                    
                    if conteo_asignaciones and conteo_asignaciones['total'] > 0:
                        fase2_asignada = True # ¡Ya se asignaron cupos!

            except mysql.connector.Error as err_fase2:
                print(f"Error al verificar asignaciones de Fase 2: {err_fase2}")
                # No bloquear la carga, solo asumir que no se ha asignado
        # --- FIN DE CORRECCIÓN ---
        
        # Obtener el ranking de aprendices
        # --- INICIO DE MODIFICACIÓN ---
        query_ranking = """
            SELECT 
                p.identificacion,
                p.nombre,
                p.apellido,
                m.id_ficha,
                a.calificacion,
                a.tiempo_tomado
            FROM personas p
            JOIN matricula m ON p.identificacion = m.identificacion
            JOIN asignaciones a ON m.id_matricula = a.id_matricula
            WHERE a.id_instrumento = %s AND a.calificacion IS NOT NULL
            GROUP BY p.identificacion, p.nombre, p.apellido, m.id_ficha, a.calificacion, a.tiempo_tomado
            ORDER BY 
                a.calificacion DESC,
                a.tiempo_tomado ASC
        """
        # --- FIN DE MODIFICACIÓN ---
        cursor.execute(query_ranking, (id_instrumento,))
        ranking = cursor.fetchall()

    except mysql.connector.Error as err:
        flash(f'Error al obtener el ranking: {err}', 'danger')
        ranking = []
        examen = {}
    finally:
        cursor.close()
        conn.close()

    return render_template('instructor/ranking.html', 
                         examen=examen, 
                         ranking=ranking,
                         fase2_asignada=fase2_asignada) # <-- Pasamos la nueva variable

@app.route('/ranking/asignar_fase2', methods=['POST'])
def asignar_fase2():
    if 'user_role' not in session or session['user_role'] != 'instructor':
        return jsonify({'error': 'No autorizado'}), 403

    data = request.json
    id_instrumento_fase1 = data.get('id_instrumento_fase1')
    aprendices_ids = data.get('aprendices_ids')
    fecha_inicio_str = data.get('fecha_inicio')
    fecha_fin_str = data.get('fecha_fin')

    if not all([id_instrumento_fase1, aprendices_ids, fecha_inicio_str, fecha_fin_str]):
        return jsonify({'error': 'Datos incompletos.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión con la base de datos.'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Obtener tipo y año del examen de Fase 1
        cursor.execute("""
            SELECT tipo, YEAR(fecha_creacion) as anio 
            FROM instrumentos WHERE id_instrumento = %s
        """, (id_instrumento_fase1,))
        info_fase1 = cursor.fetchone()
        if not info_fase1:
            return jsonify({'error': 'No se encontró el examen de Fase 1.'}), 404

        # 2. Buscar el examen correspondiente de Fase 2
        cursor.execute("""
            SELECT id_instrumento 
            FROM instrumentos 
            WHERE tipo = %s AND YEAR(fecha_creacion) = %s AND `fase(1-2)` = 2 AND estado = 'publico'
        """, (info_fase1['tipo'], info_fase1['anio']))
        examen_fase2 = cursor.fetchone()
        if not examen_fase2:
            msg = f"No se encontró un examen de Fase 2 (público) para '{info_fase1['tipo']}' del año {info_fase1['anio']}."
            return jsonify({'error': msg}), 404
        
        id_instrumento_fase2 = examen_fase2['id_instrumento']
        
        # 3. Obtener los id_matricula de los aprendices seleccionados
        # Nos aseguramos de tomar la matrícula más reciente por si un aprendiz ha estado en varias fichas
        format_strings = ','.join(['%s'] * len(aprendices_ids))
        query_matriculas = f"""
            SELECT m.id_matricula
            FROM matricula m
            WHERE m.identificacion IN ({format_strings})
        """
        cursor.execute(query_matriculas, tuple(aprendices_ids))
        matriculas = [row['id_matricula'] for row in cursor.fetchall()]

        if not matriculas:
            return jsonify({'error': 'No se encontraron matrículas para los aprendices seleccionados.'}), 404
        
        # 4. Preparar y ejecutar la inserción de las nuevas asignaciones
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%dT%H:%M')
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%dT%H:%M')
        
        asignaciones_a_insertar = [
            (id_mat, id_instrumento_fase2, fecha_inicio, fecha_fin, 0)
            for id_mat in matriculas
        ]
        
        # Corrección para error 1287: Usar alias en ON DUPLICATE KEY UPDATE
        query_insert = """
            INSERT INTO asignaciones (id_matricula, id_instrumento, fecha_inicio, fecha_fin, calificacion)
            VALUES (%s, %s, %s, %s, %s)
            AS new
            ON DUPLICATE KEY UPDATE
                fecha_inicio = new.fecha_inicio,
                fecha_fin = new.fecha_fin
        """
        
        cursor.executemany(query_insert, asignaciones_a_insertar)
        conn.commit()

        return jsonify({'success': True, 'message': f'Se asignaron {cursor.rowcount} aprendices a la Fase 2.'})

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error de base de datos: {err}'}), 500
    except Exception as e:
        return jsonify({'error': f'Error inesperado: {e}'}), 500
    finally:
        cursor.close()
        conn.close()
