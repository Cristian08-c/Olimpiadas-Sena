# --------------------------------------------------------------------------
# app.py - Backend con Flask para Olimpiadas (Versión con Admin - COMPLETO)
# --------------------------------------------------------------------------

import os
import re
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import mysql.connector
from mysql.connector import errorcode
import json
from datetime import date, datetime, timedelta
import pandas as pd
from werkzeug.utils import secure_filename
import uuid

# --- CONFIGURACIÓN DE RUTAS A PRUEBA DE ERRORES ---
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__,
            template_folder=os.path.join(basedir, 'templates'),
            static_folder=os.path.join(basedir, 'static'))
app.secret_key = 'olimpiadas_sena_secret_key'

# --- Configuración para Carga de Archivos ---
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
IMAGE_UPLOAD_FOLDER = os.path.join(basedir, 'static', 'img') # Carpeta para imágenes de preguntas
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['IMAGE_UPLOAD_FOLDER'] = IMAGE_UPLOAD_FOLDER

# Crear carpetas si no existen
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(IMAGE_UPLOAD_FOLDER):
    os.makedirs(IMAGE_UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

# --- Configuración de Base de Datos ---
DB_CONFIG = {
    'user': 'root',
    'password': '0323',
    'host': 'localhost',
    'database': 'olimpiadas',
    'raise_on_warnings': True,
    'use_pure': True,
    'charset': 'utf8mb4',
    'use_unicode': True
}

def get_db_connection():
    """Crea y retorna una conexión a la base de datos."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        # Establecer el charset después de la conexión
        cursor = conn.cursor()
        cursor.execute("SET NAMES utf8mb4")
        cursor.execute("SET CHARACTER SET utf8mb4")
        cursor.execute("SET character_set_connection=utf8mb4")
        cursor.close()
        return conn
    except mysql.connector.Error as err:
        print(f"Error de base de datos: {err}")
        return None

# --- Rutas de Autenticación y Vistas Generales ---

@app.route("/")
def index():
    if 'user_role' in session:
        if session['user_role'] == 'instructor':
            return redirect(url_for('inicio_instructor'))
        elif session['user_role'] == 'aprendiz':
            return redirect(url_for('aprendiz_dashboard'))
        elif session['user_role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
    
    return render_template('index.html')


@app.route("/login", methods=['POST'])
def login():
    document = request.form.get('document')
    password = request.form.get('password')
    if not document or not password:
        return jsonify({'success': False, 'message': 'Documento y contraseña son requeridos.'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Error de conexión con la base de datos.'})
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT identificacion, nombre, apellido, rol FROM personas WHERE identificacion = %s AND contraseña = %s AND estado = 'activo'", (document, password))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user['identificacion']
            session['user_name'] = user['nombre']
            session['user_apellido'] = user['apellido']
            session['user_role'] = user['rol']
            
            if user['rol'] == 'instructor': 
                redirect_url = url_for('inicio_instructor')
            elif user['rol'] == 'aprendiz': 
                redirect_url = url_for('aprendiz_dashboard')
            elif user['rol'] == 'admin': 
                redirect_url = url_for('admin_dashboard')
            else: 
                redirect_url = url_for('index')

            return jsonify({'success': True, 'message': 'Inicio de sesión exitoso.', 'redirect': redirect_url})
        else:
            return jsonify({'success': False, 'message': 'Credenciales incorrectas o usuario inactivo.'})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Error en la consulta: {err}'})
    finally:
        cursor.close()
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- Rutas de Panel de Administrador ---

@app.route('/admin/dashboard')
@app.route('/admin/upload', methods=['GET', 'POST'])
def admin_dashboard():
    if 'user_role' not in session or session['user_role'] != 'admin': 
        return redirect(url_for('index'))

    nombre_completo = f"{session.get('user_name', '')} {session.get('user_apellido', '')}".strip()
    
    if request.method == 'POST':
        # --- INICIO DE MODIFICACIÓN: Procesar múltiples archivos ---
        
        # 1. Obtener la lista de archivos
        files = request.files.getlist('file')

        if not files or all(f.filename == '' for f in files):
            flash('No se seleccionó ningún archivo', 'warning')
            return redirect(request.url)
        
        # 2. Preparar listas para acumular resultados
        resultados_exitosos = []
        resultados_fallidos = []

        # 3. Iterar sobre cada archivo subido
        for file in files:
            
            # 4. Verificar si el archivo es válido y está permitido
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Definir conn y cursor aquí para el bloque finally
                conn = None
                cursor = None

                # 5. Mover CADA procesamiento de archivo dentro de su propio try/except
                try:
                    file.save(filepath)
                    
                    conn = get_db_connection()
                    if not conn:
                        raise Exception("No se pudo conectar a la base de datos.")
                        
                    cursor = conn.cursor()
                    engine = 'openpyxl' if filepath.endswith('.xlsx') else 'xlrd'

                    # Leer número y nombre de ficha
                    df_meta = pd.read_excel(filepath, nrows=1, skiprows=1, header=None, engine=engine)
                    ficha_raw = str(df_meta.iloc[0, 2])

                    numero_ficha = None
                    nombre_ficha = None

                    if ' - ' in ficha_raw:
                        parts = ficha_raw.split(' - ', 1)
                        num_match = re.search(r'(\d+)', parts[0])
                        if num_match:
                            numero_ficha = int(num_match.group(1))
                            nombre_ficha = parts[1].strip()
                    
                    if numero_ficha is None:
                        ficha_match = re.search(r'(\d+)', ficha_raw)
                        if not ficha_match:
                            raise ValueError(f"No se pudo extraer el número de ficha de: {ficha_raw}")
                        numero_ficha = int(ficha_match.group(1))
                        nombre_ficha = f"Ficha {numero_ficha}"

                    # Leer datos de aprendices
                    df = pd.read_excel(filepath, skiprows=4, engine=engine)

                    # Verificar columna 'estado' en matricula
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = 'olimpiadas' 
                        AND TABLE_NAME = 'matricula' 
                        AND COLUMN_NAME = 'estado'
                    """)
                    if cursor.fetchone()[0] == 0:
                        cursor.execute("ALTER TABLE matricula ADD COLUMN estado VARCHAR(50) DEFAULT 'EN FORMACION'")
                        conn.commit()
                    
                    # Insertar/actualizar ficha
                    cursor.execute("SELECT id_ficha FROM fichas WHERE id_ficha = %s", (numero_ficha,))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO fichas (id_ficha, nombre, activo) VALUES (%s, %s, %s)", 
                                     (numero_ficha, nombre_ficha, True))
                    else:
                        cursor.execute("UPDATE fichas SET nombre = %s WHERE id_ficha = %s", (nombre_ficha, numero_ficha))
                    conn.commit()
                    
                    registros_procesados = 0
                    registros_actualizados = 0
                    registros_error = 0
                    
                    # Iterar sobre las filas del Excel
                    for index, row in df.iterrows():
                        if pd.isna(row.get('Numero de Documento')) and pd.isna(row.get('Número de Documento')):
                            continue
                        
                        try:
                            doc_value = row.get('Numero de Documento') if pd.notna(row.get('Numero de Documento')) else row.get('Número de Documento')
                            identificacion = str(doc_value).strip()
                            identificacion = ''.join(filter(str.isdigit, identificacion))
                            if not identificacion:
                                continue
                            identificacion = int(identificacion)
                            
                            nombre = str(row['Nombre']).strip() if pd.notna(row.get('Nombre')) else ''
                            apellido = str(row['Apellidos']).strip() if pd.notna(row.get('Apellidos')) else ''
                            celular = str(row['Celular']).strip() if pd.notna(row.get('Celular')) else '0'
                            
                            correo_col = row.get('Correo Electrónico') if pd.notna(row.get('Correo Electrónico')) else row.get('Correo Electronico')
                            correo = str(correo_col).strip() if pd.notna(correo_col) else ''
                            
                            estado_matricula = str(row.get('Estado', '')).strip()
                            
                            # --- INICIO DE CORRECCIÓN: Aceptar 'INDUCCIÓN' y 'EN FORMACION' ---
                            estado_valido = estado_matricula.upper()
                            if estado_valido not in ['EN FORMACION', 'INDUCCION']:
                                continue
                            # --- FIN DE CORRECCIÓN ---
                            
                            if not nombre or not apellido:
                                continue
                            
                            try:
                                celular_num = int(''.join(filter(str.isdigit, celular))) if celular and celular != '0' else 0
                            except:
                                celular_num = 0
                                
                        except (ValueError, KeyError) as e:
                            print(f"Error en fila {index + 6} ({filename}): {e}")
                            registros_error += 1
                            continue

                        try:
                            # Insertar o actualizar persona
                            sql_persona = """
                                INSERT INTO personas (identificacion, nombre, apellido, celular, correo, `contraseña`, rol, estado, activo)
                                VALUES (%s, %s, %s, %s, %s, %s, 'aprendiz', 'activo', TRUE)
                                ON DUPLICATE KEY UPDATE
                                    nombre = %s,
                                    apellido = %s,
                                    celular = %s,
                                    correo = %s,
                                    `contraseña` = %s
                            """
                            cursor.execute(sql_persona, (
                                identificacion, nombre, apellido, celular_num, correo, str(numero_ficha),
                                nombre, apellido, celular_num, correo, str(numero_ficha)
                            ))
                            
                            if cursor.rowcount == 1:
                                registros_procesados += 1
                            else:
                                registros_actualizados += 1

                            # Insertar o actualizar matrícula
                            try:
                                sql_insert_matricula = """
                                    INSERT INTO matricula (identificacion, id_ficha, fecha_matricula, estado)
                                    VALUES (%s, %s, %s, %s)
                                """
                                # Usamos el estado original del Excel (Ej: 'Inducción')
                                cursor.execute(sql_insert_matricula, (identificacion, numero_ficha, date.today(), estado_matricula))
                            except mysql.connector.IntegrityError:
                                sql_update_matricula = """
                                    UPDATE matricula 
                                    SET estado = %s, fecha_matricula = %s
                                    WHERE identificacion = %s AND id_ficha = %s
                                """
                                cursor.execute(sql_update_matricula, (estado_matricula, date.today(), identificacion, numero_ficha))
                            
                            if (registros_procesados + registros_actualizados) % 10 == 0:
                                conn.commit()
                        
                        except mysql.connector.Error as db_err:
                            print(f"Error BD en fila {index + 6} (ID: {identificacion}, Archivo: {filename}): {db_err}")
                            registros_error += 1
                            conn.rollback()
                            continue

                    # Commit final para este archivo
                    conn.commit()
                    
                    # 6. Guardar mensaje de éxito
                    mensaje = f'Archivo "{filename}" (Ficha {numero_ficha} - {nombre_ficha}): '
                    mensaje += f'Nuevos: {registros_procesados}, Actualizados: {registros_actualizados}'
                    if registros_error > 0:
                        mensaje += f', Errores: {registros_error}'
                    resultados_exitosos.append(mensaje)

                except Exception as e:
                    # 7. Guardar mensaje de error
                    if 'conn' in locals() and conn and conn.is_connected():
                        conn.rollback()
                    error_msg = str(e)
                    print(f"Error detallado en {filename}: {error_msg}")
                    resultados_fallidos.append(f'Error al procesar "{filename}": {error_msg}')
                
                finally:
                    # 8. Cerrar conexión y borrar archivo
                    if 'cursor' in locals() and cursor:
                        cursor.close()
                    if 'conn' in locals() and conn and conn.is_connected():
                        conn.close()
                    if os.path.exists(filepath):
                        os.remove(filepath)
                
            elif file:
                # Archivo no permitido (ej. .txt)
                resultados_fallidos.append(f'Archivo "{file.filename}" no permitido (solo .xlsx, .xls).')
        
        # 9. Después de procesar todos los archivos, mostrar los mensajes
        for msg in resultados_exitosos:
            flash(msg, 'success')
        for msg in resultados_fallidos:
            flash(msg, 'danger')
        
        # 10. Redirigir UNA SOLA VEZ al final
        return redirect(url_for('admin_fichas'))
    
    # --- FIN DE MODIFICACIÓN ---

    return render_template('admin/upload.html', usuario={'nombre_completo': nombre_completo})

# Alias para compatibilidad
@app.route('/admin/subir', methods=['GET', 'POST'])
def upload_file():
    return admin_dashboard()

@app.route('/admin/fichas')
def admin_fichas():
    if 'user_role' not in session or session['user_role'] != 'admin': 
        return redirect(url_for('index'))
    
    nombre_completo = f"{session.get('user_name', '')} {session.get('user_apellido', '')}".strip()
    
    conn = get_db_connection()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return render_template('admin/fichas.html', fichas=[], usuario={'nombre_completo': nombre_completo})
    
    cursor = conn.cursor(dictionary=True)
    
    # Primero verificamos qué columnas existen
    cursor.execute("SHOW COLUMNS FROM fichas")
    columns = [col['Field'] for col in cursor.fetchall()]
    
    # Construir consulta según columnas disponibles
    tiene_activo = 'activo' in columns
    tiene_estado = 'estado' in columns
    
    select_parts = ['f.id_ficha', 'f.nombre']
    group_parts = ['f.id_ficha', 'f.nombre']
    
    if tiene_activo:
        select_parts.append('f.activo')
        group_parts.append('f.activo')
    
    if tiene_estado:
        select_parts.append('f.estado')
        group_parts.append('f.estado')
    
    select_parts.append('COUNT(m.id_matricula) as total_personas')
    
    sql = f"""
        SELECT 
            {', '.join(select_parts)}
        FROM fichas f
        LEFT JOIN matricula m ON f.id_ficha = m.id_ficha
        GROUP BY {', '.join(group_parts)}
        ORDER BY f.id_ficha DESC
    """
    
    cursor.execute(sql)
    fichas = cursor.fetchall()
    
    # Asegurar que todas las fichas tengan las propiedades necesarias
    for ficha in fichas:
        if 'activo' not in ficha:
            ficha['activo'] = True
        if 'estado' not in ficha:
            ficha['estado'] = 'activa' if ficha.get('activo', True) else 'inactiva'
    
    cursor.close()
    conn.close()
    
    return render_template('admin/fichas.html', fichas=fichas, usuario={'nombre_completo': nombre_completo})

@app.route('/admin/ficha/<int:ficha_num>')
def ver_ficha(ficha_num):
    if 'user_role' not in session or session['user_role'] != 'admin': 
        return redirect(url_for('index'))

    nombre_completo = f"{session.get('user_name', '')} {session.get('user_apellido', '')}".strip()

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('admin_fichas'))

    cursor = conn.cursor(dictionary=True)
    
    # Obtener información de la ficha
    cursor.execute("SELECT * FROM fichas WHERE id_ficha = %s", (ficha_num,))
    ficha = cursor.fetchone()
    
    if not ficha:
        flash(f'No se encontró la ficha {ficha_num}', 'warning')
        cursor.close()
        conn.close()
        return redirect(url_for('admin_fichas'))
    
    # Obtener aprendices de la ficha
    sql = """
        SELECT 
            p.identificacion, 
            p.nombre, 
            p.apellido, 
            p.celular,
            p.correo,
            p.rol,
            p.estado as estado_persona, 
            m.estado AS estado_matricula,
            m.numero_lista,
            p.activo
        FROM personas p
        JOIN matricula m ON p.identificacion = m.identificacion
        WHERE m.id_ficha = %s
        ORDER BY p.apellido, p.nombre
    """
    cursor.execute(sql, (ficha_num,))
    aprendices = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('admin/aprendices.html', 
                         aprendices=aprendices, 
                         ficha=ficha, 
                         usuario={'nombre_completo': nombre_completo})

@app.route('/admin/ficha/<int:ficha_id>/toggle', methods=['GET'])
def toggle_ficha(ficha_id):
    if 'user_role' not in session or session['user_role'] != 'admin': 
        return redirect(url_for('index'))

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('admin_fichas'))
        
    cursor = conn.cursor()
    try:
        # Obtener estado actual
        cursor.execute("SELECT activo FROM fichas WHERE id_ficha = %s", (ficha_id,))
        result = cursor.fetchone()
        
        if result:
            estado_actual = result[0]
            nuevo_estado = not estado_actual
            
            cursor.execute("UPDATE fichas SET activo = %s WHERE id_ficha = %s", (nuevo_estado, ficha_id))
            conn.commit()
            
            accion = "habilitada" if nuevo_estado else "deshabilitada"
            flash(f'La ficha {ficha_id} ha sido {accion} exitosamente.', 'success')
        else:
            flash(f'No se encontró la ficha {ficha_id}.', 'warning')

    except mysql.connector.Error as err:
        flash(f'Error al actualizar el estado: {err}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_fichas'))

@app.route('/admin/aprendiz/<int:ficha_id>/<int:aprendiz_id>/toggle', methods=['GET'])
def toggle_aprendiz(ficha_id, aprendiz_id):
    if 'user_role' not in session or session['user_role'] != 'admin': 
        return redirect(url_for('index'))

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('ver_ficha', ficha_num=ficha_id))
        
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT activo FROM personas WHERE identificacion = %s", (aprendiz_id,))
        result = cursor.fetchone()
        
        if result:
            estado_actual = result[0]
            nuevo_estado = not estado_actual
            
            cursor.execute("UPDATE personas SET activo = %s WHERE identificacion = %s", (nuevo_estado, aprendiz_id))
            conn.commit()
            
            accion = "habilitado" if nuevo_estado else "deshabilitado"
            flash(f'El aprendiz {aprendiz_id} ha sido {accion} exitosamente.', 'success')
        else:
            flash(f'No se encontró al aprendiz con identificación {aprendiz_id}.', 'warning')

    except mysql.connector.Error as err:
        flash(f'Error al actualizar el estado: {err}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('ver_ficha', ficha_num=ficha_id))

@app.route('/admin/instructores', methods=['GET', 'POST'])
def admin_instructores():
    if 'user_role' not in session or session['user_role'] != 'admin': 
        return redirect(url_for('index'))

    nombre_completo = f"{session.get('user_name', '')} {session.get('user_apellido', '')}".strip()

    if request.method == 'POST':
        identificacion = request.form.get('identificacion')
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        celular = request.form.get('celular')
        correo = request.form.get('correo')
        contraseña = request.form.get('contraseña')
        rol = request.form.get('rol', 'instructor')

        if not all([identificacion, nombre, apellido, celular, correo, contraseña]):
            flash('Todos los campos son obligatorios.', 'warning')
            return redirect(request.url)
        
        if rol not in ['instructor', 'admin']:
            flash('El rol debe ser instructor o admin.', 'warning')
            return redirect(request.url)
        
        conn = get_db_connection()
        if not conn:
            flash('Error de conexión a la base de datos.', 'danger')
            return redirect(request.url)
            
        cursor = conn.cursor()
        try:
            sql = """
                INSERT INTO personas (identificacion, nombre, apellido, celular, correo, contraseña, rol, estado, activo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'activo', TRUE)
            """
            cursor.execute(sql, (identificacion, nombre, apellido, celular, correo, contraseña, rol))
            conn.commit()
            
            rol_texto = 'Instructor' if rol == 'instructor' else 'Administrador'
            flash(f'{rol_texto} registrado exitosamente.', 'success')
        except mysql.connector.IntegrityError:
            flash(f'Ya existe un usuario con la identificación {identificacion}.', 'danger')
        except mysql.connector.Error as err:
            flash(f'Error al registrar el usuario: {err}', 'danger')
        finally:
            cursor.close()
            conn.close()
        
        return redirect(url_for('admin_instructores'))

    return render_template('admin/registro_instructor.html', usuario={'nombre_completo': nombre_completo})

# Alias para compatibilidad
@app.route('/admin/registro_instructor', methods=['GET', 'POST'])
def registro_instructor():
    return admin_instructores()

@app.route('/admin/init_db')
def init_db():
    """Inicializa/actualiza la estructura de la base de datos"""
    if 'user_role' not in session or session['user_role'] != 'admin': 
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('admin_fichas'))
    
    cursor = conn.cursor()
    try:
        # Agregar columna 'activo' a fichas si no existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'olimpiadas' 
            AND TABLE_NAME = 'fichas' 
            AND COLUMN_NAME = 'activo'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE fichas ADD COLUMN activo BOOLEAN DEFAULT TRUE")
        
        # Agregar columna 'estado' a fichas si no existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'olimpiadas' 
            AND TABLE_NAME = 'fichas' 
            AND COLUMN_NAME = 'estado'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE fichas ADD COLUMN estado VARCHAR(50) DEFAULT 'activa'")
        
        # Agregar columna 'activo' a personas si no existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'olimpiadas' 
            AND TABLE_NAME = 'personas' 
            AND COLUMN_NAME = 'activo'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE personas ADD COLUMN activo BOOLEAN DEFAULT TRUE")
        
        # Agregar columna 'numero_lista' a matricula si no existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'olimpiadas' 
            AND TABLE_NAME = 'matricula' 
            AND COLUMN_NAME = 'numero_lista'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE matricula ADD COLUMN numero_lista INT")
        
        # Agregar columna 'fecha_matricula' a matricula si no existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'olimpiadas' 
            AND TABLE_NAME = 'matricula' 
            AND COLUMN_NAME = 'fecha_matricula'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE matricula ADD COLUMN fecha_matricula DATE")
        
        # Cambiar 'telefono' por 'celular' en personas si es necesario
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'olimpiadas' 
            AND TABLE_NAME = 'personas' 
            AND COLUMN_NAME = 'celular'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE personas CHANGE telefono celular BIGINT")
        
        # Cambiar id_ficha en matricula para que coincida
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'olimpiadas' 
            AND TABLE_NAME = 'matricula' 
            AND COLUMN_NAME = 'id_ficha'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE matricula ADD COLUMN id_ficha INT")
        
        # Cambiar 'contraseña' para asegurar que existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'olimpiadas' 
            AND TABLE_NAME = 'personas' 
            AND COLUMN_NAME = 'contraseña'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE personas ADD COLUMN contraseña VARCHAR(20) NOT NULL")
        
        conn.commit()
        flash('Base de datos actualizada exitosamente.', 'success')
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f'Error al actualizar la base de datos: {err}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_fichas'))

# --- Rutas del Panel de Aprendiz (MODIFICADAS Y NUEVAS) ---

@app.route("/aprendiz")
def aprendiz_dashboard():
    if 'user_role' not in session or session['user_role'] != 'aprendiz':
        return redirect(url_for('index'))
    
    nombre_completo = f"{session.get('user_name', '')} {session.get('user_apellido', '')}".strip()
    
    conn = get_db_connection()
    if not conn:
        flash('Error de conexión a la base de datos', 'error')
        return render_template('aprendiz/evaluations.html', usuario={'nombre': session.get('user_name'), 'nombre_completo': nombre_completo}, examenes={})
    
    cursor = conn.cursor(dictionary=True)
    try:
        # MODIFICADO: Se añade un subquery para calcular el puntaje máximo del instrumento
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
        cursor.execute(query, (session['user_id'],))
        examenes_asignados = cursor.fetchall()
        
        examenes_organizados = {}
        for examen in examenes_asignados:
            examen['duracion'] = int(examen['duracion'].total_seconds() / 60) if isinstance(examen['duracion'], timedelta) else 0
            # Asegurarse que el puntaje máximo no sea nulo si un examen no tiene preguntas
            if examen['puntaje_maximo'] is None:
                examen['puntaje_maximo'] = 0
            examenes_organizados[examen['tipo']] = examen

    except mysql.connector.Error as err:
        flash(f'Error al obtener tus exámenes: {err}', 'error')
        examenes_organizados = {}
    finally:
        cursor.close()
        conn.close()
    
    return render_template('aprendiz/evaluations.html', 
                         usuario={'nombre': session.get('user_name'), 'nombre_completo': nombre_completo},
                         examenes=examenes_organizados)


@app.route("/aprendiz/prueba/<tipo>/<int:id_instrumento>")
def prueba(tipo, id_instrumento):
    if 'user_role' not in session or session['user_role'] != 'aprendiz':
        flash('Debes iniciar sesión como aprendiz para acceder a los exámenes.', 'warning')
        return redirect(url_for('index'))

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('aprendiz_dashboard'))
    
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
        cursor.execute(query, (session['user_id'], id_instrumento))
        examen = cursor.fetchone()

        if not examen:
            flash('Este examen no está disponible para ti en este momento.', 'warning')
            return redirect(url_for('aprendiz_dashboard'))

        if examen['calificacion'] is not None and examen['calificacion'] > 0:
            flash('Ya has completado este examen.', 'info')
            return redirect(url_for('aprendiz_dashboard'))
            
        return render_template('aprendiz/prueba.html', examen=examen)
    except mysql.connector.Error as err:
        flash(f'Error al acceder al examen: {err}', 'danger')
        return redirect(url_for('aprendiz_dashboard'))
    finally:
        cursor.close()
        conn.close()

# --- API para el Examen ---

@app.route("/api/examen/<int:id_instrumento>/preguntas")
def get_preguntas_examen(id_instrumento):
    if 'user_role' not in session or session['user_role'] != 'aprendiz':
        return jsonify({'error': 'No autorizado'}), 401
    
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Error de conexión'}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_pregunta, pregunta, enunciado, archivo, puntos, 'seleccion_multiple' as tipo FROM preguntas_seleccion WHERE id_instrumento = %s", (id_instrumento,))
        preguntas_seleccion = cursor.fetchall()
        for p in preguntas_seleccion:
            p['unique_id'] = f"sel_{p['id_pregunta']}"
            cursor.execute("SELECT respuesta, estado FROM respuestas_seleccion WHERE id_pregunta = %s", (p['id_pregunta'],))
            p['opciones'] = [{'texto': r['respuesta'], 'correcta': r['estado'] == 'verdadero'} for r in cursor.fetchall()]
        
        cursor.execute("SELECT id_pregunta2 as id_pregunta, pregunta, tipo, enunciado, archivo, puntos FROM preguntas_otras WHERE id_instrumento = %s", (id_instrumento,))
        preguntas_otras = cursor.fetchall()
        for p in preguntas_otras:
            p['unique_id'] = f"otr_{p['id_pregunta']}"
            cursor.execute("SELECT enunciado, complemento FROM respuestas_otras WHERE id_pregunta2 = %s", (p['id_pregunta'],))
            respuestas = cursor.fetchall()
            if p['tipo'] == 'completar':
                p['opciones'] = {'correct': [r['complemento'] for r in respuestas if r['enunciado'] == 'correcto'], 'distractors': [r['complemento'] for r in respuestas if r['enunciado'] == 'distractor']}
            elif p['tipo'] == 'relacionar':
                p['opciones'] = [{'a': r['enunciado'], 'b': r['complemento']} for r in respuestas]

        todas_preguntas = preguntas_seleccion + preguntas_otras
        for p in todas_preguntas:
            if p.get('archivo'):
                p['archivo_url'] = url_for('static', filename=f'img/{p["archivo"]}')
        
        return jsonify(todas_preguntas)
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/examen/finalizar', methods=['POST'])
def finalizar_examen():
    if 'user_role' not in session or session['user_role'] != 'aprendiz':
        return jsonify({'error': 'No autorizado'}), 403

    data = request.json
    id_instrumento = data.get('id_instrumento')
    respuestas_usuario = data.get('respuestas')
    tiempo_tomado = data.get('tiempo_tomado') # <-- NUEVO: Recibir el tiempo

    if not id_instrumento or respuestas_usuario is None or tiempo_tomado is None: # <-- NUEVO: Validar el tiempo
        return jsonify({'error': 'Datos incompletos'}), 400

    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Error de conexión'}), 500
    cursor = conn.cursor(dictionary=True)
    
    try:
        # --- INICIO DE CORRECCIÓN: Lógica de Puntuación Completa ---
        
        # 1. Obtener todas las respuestas correctas para el examen
        todas_las_respuestas_correctas = {}

        # Preguntas de selección múltiple
        cursor.execute("""
            SELECT p.id_pregunta, p.puntos, r.respuesta 
            FROM preguntas_seleccion p 
            JOIN respuestas_seleccion r ON p.id_pregunta = r.id_pregunta 
            WHERE p.id_instrumento = %s AND r.estado = 'verdadero'
        """, (id_instrumento,))
        for row in cursor.fetchall():
            unique_id = f"sel_{row['id_pregunta']}"
            todas_las_respuestas_correctas[unique_id] = {
                'tipo': 'seleccion_multiple',
                'puntos': row['puntos'],
                'respuesta_correcta': row['respuesta']
            }

        # Preguntas de completar y relacionar
        # MODIFICADO: Se añade r.id_respuesta2 y se ordena por él para mantener el orden de los espacios en blanco
        cursor.execute("""
            SELECT p.id_pregunta2, p.tipo, p.puntos, r.enunciado, r.complemento, r.id_respuesta2 
            FROM preguntas_otras p 
            JOIN respuestas_otras r ON p.id_pregunta2 = r.id_pregunta2 
            WHERE p.id_instrumento = %s
            ORDER BY p.id_pregunta2, r.id_respuesta2 ASC
        """, (id_instrumento,))
        
        preguntas_otras_temp = {}
        for row in cursor.fetchall():
            unique_id = f"otr_{row['id_pregunta2']}"
            if unique_id not in preguntas_otras_temp:
                preguntas_otras_temp[unique_id] = {'tipo': row['tipo'], 'puntos': row['puntos'], 'respuestas': []}
            preguntas_otras_temp[unique_id]['respuestas'].append(row)

        for unique_id, data_pregunta in preguntas_otras_temp.items():
            if data_pregunta['tipo'] == 'completar':
                # MODIFICADO: Obtiene una lista de respuestas correctas en orden
                correctas_list = [r['complemento'] for r in data_pregunta['respuestas'] if r['enunciado'] == 'correcto']
                # Convierte la lista ['a', 'b'] en un dict {'0': 'a', '1': 'b'}
                correctas_dict = {str(i): v for i, v in enumerate(correctas_list)}
                todas_las_respuestas_correctas[unique_id] = {
                    'tipo': 'completar', 
                    'puntos': data_pregunta['puntos'], 
                    'respuesta_correcta': correctas_dict,
                    'num_items': len(correctas_dict) # Guardamos cuántos items son
                }
            elif data_pregunta['tipo'] == 'relacionar':
                # MODIFICADO: El mapa correcto es {'0': '0', '1': '1', ...}
                num_pares = len(data_pregunta['respuestas'])
                mapa_correcto = {str(i): str(i) for i in range(num_pares)}
                todas_las_respuestas_correctas[unique_id] = {
                    'tipo': 'relacionar', 
                    'puntos': data_pregunta['puntos'], 
                    'respuesta_correcta': mapa_correcto,
                    'num_items': num_pares # Guardamos cuántos items son
                }

        # 2. Calcular puntuación
        puntuacion_total = 0.0 # MODIFICADO: Usar float para puntos parciales
        
        for unique_id, resp_usuario in respuestas_usuario.items():
            if unique_id in todas_las_respuestas_correctas:
                info_pregunta = todas_las_respuestas_correctas[unique_id]
                
                # MODIFICADO: Lógica de calificación separada por tipo
                
                if info_pregunta['tipo'] == 'seleccion_multiple':
                    if info_pregunta['respuesta_correcta'] == resp_usuario:
                        puntuacion_total += info_pregunta['puntos']
                
                elif info_pregunta['tipo'] == 'completar':
                    # Lógica de crédito parcial para 'completar'
                    if not isinstance(resp_usuario, dict) or info_pregunta['num_items'] == 0:
                        continue # Saltar si la respuesta no es un objeto o si la pregunta no tiene items
                        
                    puntos_por_item = info_pregunta['puntos'] / info_pregunta['num_items']
                    resp_correcta_dict = info_pregunta['respuesta_correcta']
                    
                    aciertos = 0
                    for index, palabra_usuario in resp_usuario.items():
                        # Comprueba si el índice existe y si la palabra del usuario coincide
                        if index in resp_correcta_dict and resp_correcta_dict[index] == palabra_usuario:
                            aciertos += 1
                            
                    puntuacion_total += (aciertos * puntos_por_item)

                elif info_pregunta['tipo'] == 'relacionar':
                    # Lógica de crédito parcial para 'relacionar'
                    if not isinstance(resp_usuario, dict) or info_pregunta['num_items'] == 0:
                        continue # Saltar
                    
                    puntos_por_item = info_pregunta['puntos'] / info_pregunta['num_items']
                    resp_correcta_dict = info_pregunta['respuesta_correcta'] # Esto es {'0':'0', '1':'1', ...}

                    aciertos = 0
                    for index_a, index_b_usuario in resp_usuario.items():
                        # Comprueba si el par del usuario (index_a: index_b_usuario) es correcto
                        if index_a in resp_correcta_dict and resp_correcta_dict[index_a] == index_b_usuario:
                            aciertos += 1
                    
                    puntuacion_total += (aciertos * puntos_por_item)
        
        # 3. Actualizar la calificación en la base de datos
        # --- FIN DE CORRECCIÓN ---

        query_update = """
            UPDATE asignaciones a
            JOIN matricula m ON a.id_matricula = m.id_matricula
            SET a.calificacion = %s, a.tiempo_tomado = %s
            WHERE m.identificacion = %s AND a.id_instrumento = %s
        """
        # MODIFICADO: Redondear la puntuación final al entero más cercano y guardar el tiempo
        cursor.execute(query_update, (round(puntuacion_total), int(tiempo_tomado), session['user_id'], id_instrumento))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({'error': 'No se pudo registrar la calificación. Asignación no encontrada.'}), 404

        puntaje_maximo = sum(info['puntos'] for info in todas_las_respuestas_correctas.values())
        return jsonify({
            'success': True,
            'calificacion': round(puntuacion_total), # MODIFICADO: Devolver el valor redondeado
            'puntaje_maximo': puntaje_maximo
        })

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error en la base de datos: {err}'}), 500
    finally:
        cursor.close()
        conn.close()

# --- Rutas del Panel de Instructor ---

@app.route("/instructor")
def inicio_instructor():
    if 'user_role' not in session or session['user_role'] != 'instructor':
        return redirect(url_for('index'))
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
        return redirect(url_for('index'))
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
        return redirect(url_for('index'))

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

if __name__ == "__main__":
    # Al usar host='0.0.0.0', Flask será accesible desde otras máquinas en la misma red.
    app.run(host='0.0.0.0', debug=True, port=5000)

