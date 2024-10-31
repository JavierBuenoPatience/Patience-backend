import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import psycopg2
import openai
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Crear instancia de Flask
app = Flask(__name__)

# Configuración de CORS para permitir solicitudes desde tu frontend en GitHub Pages y Render
CORS(app, resources={r"/*": {"origins": ["https://patience-frontend.onrender.com", "https://javierbuenopatience.github.io"], "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}})

# Configuración de la clave secreta para JWT y la clave de API de OpenAI
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')  # Configura esta variable de entorno en Render
openai.api_key = os.getenv("OPENAI_API_KEY")  # Clave API de OpenAI desde la variable de entorno
jwt = JWTManager(app)

# Configuración para la subida de archivos
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'txt'}

# URL de la base de datos en Render, obtenida de una variable de entorno
DATABASE_URL = os.getenv('DATABASE_URL')  # Configura esta variable de entorno en Render

# Conexión a la base de datos
def connect_db():
    return psycopg2.connect(DATABASE_URL)

# Función para verificar extensiones de archivo permitidas
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Creación de tablas
def create_tables():
    conn = connect_db()
    cur = conn.cursor()

    # Tabla de usuarios
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) NOT NULL,
            email VARCHAR(50) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            profile_image VARCHAR(200),
            full_name VARCHAR(100),
            phone VARCHAR(20),
            study_hours VARCHAR(50),
            specialty VARCHAR(100),
            hobbies TEXT,
            location VARCHAR(100)
        );
    ''')

    # Tabla de documentos
    cur.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            filename VARCHAR(200),
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    conn.commit()
    cur.close()
    conn.close()

# Llama a la función para crear las tablas cuando inicie el servidor
create_tables()

# Ruta de registro de usuarios
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"error": "Todos los campos son obligatorios."}), 400

    password_hash = generate_password_hash(password)

    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO users (username, email, password_hash)
            VALUES (%s, %s, %s);
        ''', (username, email, password_hash))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logging.error(f"Error al registrar usuario: {e}")
        return jsonify({"error": "Error al registrar usuario."}), 400
    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "Usuario registrado exitosamente"}), 201

# Ruta de inicio de sesión
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    logging.info(f"Intento de inicio de sesión para el correo electrónico: {email}")

    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, password_hash FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
    except Exception as e:
        logging.error(f"Error en la ruta /login: {e}")
        return jsonify({"error": "Error interno en el servidor"}), 500
    finally:
        cur.close()
        conn.close()

    if user and check_password_hash(user[2], password):
        access_token = create_access_token(identity={'id': user[0], 'email': email, 'username': user[1]})
        return jsonify(access_token=access_token, username=user[1]), 200
    else:
        return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

# Ruta para obtener el perfil del usuario
@app.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    current_user = get_jwt_identity()

    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT email, full_name, phone, study_hours, specialty, hobbies, location, profile_image
            FROM users WHERE email = %s;
        ''', (current_user['email'],))
        user = cur.fetchone()

        if user:
            user_data = {
                "email": user[0],
                "full_name": user[1],
                "phone": user[2],
                "study_hours": user[3],
                "specialty": user[4],
                "hobbies": user[5],
                "location": user[6],
                "profile_image": user[7]
            }
            return jsonify(user_data), 200
        else:
            return jsonify({"error": "Usuario no encontrado"}), 404
    except Exception as e:
        logging.error(f"Error en la ruta /profile: {e}")
        return jsonify({"error": "Error al cargar perfil"}), 500
    finally:
        cur.close()
        conn.close()

# Ruta para actualizar el perfil del usuario
@app.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    current_user = get_jwt_identity()
    data = request.json

    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE users
            SET full_name = %s, phone = %s, study_hours = %s, specialty = %s, hobbies = %s, location = %s
            WHERE email = %s;
        ''', (
            data.get('full_name'),
            data.get('phone'),
            data.get('study_hours'),
            data.get('specialty'),
            data.get('hobbies'),
            data.get('location'),
            current_user['email']
        ))
        conn.commit()
        return jsonify({"message": "Perfil actualizado exitosamente"}), 200
    except Exception as e:
        conn.rollback()
        logging.error(f"Error en la ruta /profile: {e}")
        return jsonify({"error": "Error al actualizar perfil"}), 400
    finally:
        cur.close()
        conn.close()

# Ruta para subir imagen de perfil
@app.route('/upload_profile_image', methods=['POST'])
@jwt_required()
def upload_profile_image():
    if 'profile_image' not in request.files:
        return jsonify({"error": "No se encontró el archivo"}), 400

    file = request.files['profile_image']

    if file.filename == '':
        return jsonify({"error": "Nombre de archivo no válido"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Actualizar la ruta de la imagen en la base de datos
        current_user = get_jwt_identity()
        conn = connect_db()
        cur = conn.cursor()
        try:
            cur.execute('''
                UPDATE users
                SET profile_image = %s
                WHERE email = %s;
            ''', (filename, current_user['email']))
            conn.commit()
            return jsonify({"message": "Imagen de perfil actualizada exitosamente"}), 200
        except Exception as e:
            conn.rollback()
            logging.error(f"Error en la ruta /upload_profile_image: {e}")
            return jsonify({"error": "Error al actualizar la imagen de perfil"}), 400
        finally:
            cur.close()
            conn.close()
    else:
        return jsonify({"error": "Tipo de archivo no permitido"}), 400

# Ruta para servir archivos subidos
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Ruta para interactuar con ChatGPT
@app.route('/chatgpt', methods=['POST'])
@jwt_required()
def chatgpt():
    data = request.json
    messages = data.get('messages')
    specialty = data.get('specialty')

    if not openai.api_key:
        return jsonify({"error": "La clave API de OpenAI no está configurada"}), 500

    if not messages:
        return jsonify({"error": "No se proporcionaron mensajes"}), 400

    # Agregar el contexto de la especialidad al inicio de la conversación
    system_message = {
        "role": "system",
        "content": f"Eres un asistente especializado en {specialty}. Proporciona respuestas detalladas y precisas."
    }
    conversation = [system_message] + messages

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=conversation
        )
        assistant_message = response['choices'][0]['message']['content'].strip()
    except Exception as e:
        logging.error(f"Error en la ruta /chatgpt: {e}")
        return jsonify({"error": "Error al comunicarse con OpenAI"}), 500

    return jsonify({"assistant_message": assistant_message})

# Ruta para subir documentos
@app.route('/upload_document', methods=['POST'])
@jwt_required()
def upload_document():
    if 'document' not in request.files:
        return jsonify({"error": "No se encontró el archivo"}), 400

    file = request.files['document']

    if file.filename == '':
        return jsonify({"error": "Nombre de archivo no válido"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Guardar información del documento en la base de datos
        current_user = get_jwt_identity()
        conn = connect_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM users WHERE email = %s", (current_user['email'],))
            user_id = cur.fetchone()[0]

            cur.execute('''
                INSERT INTO documents (user_id, filename)
                VALUES (%s, %s);
            ''', (user_id, filename))
            conn.commit()
            return jsonify({"message": "Documento subido exitosamente"}), 200
        except Exception as e:
            conn.rollback()
            logging.error(f"Error en la ruta /upload_document: {e}")
            return jsonify({"error": "Error al subir el documento"}), 400
        finally:
            cur.close()
            conn.close()
    else:
        return jsonify({"error": "Tipo de archivo no permitido"}), 400

# Ruta para obtener los documentos del usuario
@app.route('/documents', methods=['GET'])
@jwt_required()
def get_documents():
    current_user = get_jwt_identity()
    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE email = %s", (current_user['email'],))
        user_id = cur.fetchone()[0]

        cur.execute('''
            SELECT id, filename, upload_date
            FROM documents WHERE user_id = %s;
        ''', (user_id,))
        documents = cur.fetchall()
        documents_list = [{"id": doc[0], "filename": doc[1], "upload_date": doc[2].strftime("%Y-%m-%d %H:%M:%S")} for doc in documents]
        return jsonify({"documents": documents_list}), 200
    except Exception as e:
        logging.error(f"Error en la ruta /documents: {e}")
        return jsonify({"error": "Error al obtener documentos"}), 400
    finally:
        cur.close()
        conn.close()

# Ruta inicial de prueba
@app.route('/')
def home():
    return "¡Hola, mundo desde el backend!"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host="0.0.0.0", port=port)
