from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import psycopg2
import openai
import os

app = Flask(__name__)
CORS(app)  # Habilita CORS para todas las rutas

# Configuración de la clave secreta para JWT y la clave de API de OpenAI
app.config['JWT_SECRET_KEY'] = 'supersecreto'  # Cambia esta clave secreta en un entorno de producción
openai.api_key = os.getenv("OPENAI_API_KEY")  # Obtiene la clave API de OpenAI desde una variable de entorno
jwt = JWTManager(app)

# URL de la base de datos en Render
DATABASE_URL = "postgresql://patience_db_user:MG6yUiJuOHYyKXN8xYJx4TqQGY8n6uxl@dpg-csf68i3tq21c738k77sg-a/patience_db"

# Conexión a la base de datos
def connect_db():
    return psycopg2.connect(DATABASE_URL)

# Creación de tablas
def create_tables():
    conn = connect_db()
    cur = conn.cursor()

    # Tabla de usuarios
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(50) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name VARCHAR(100),
            phone VARCHAR(20),
            study_hours VARCHAR(50),
            specialty VARCHAR(100),
            hobbies TEXT,
            location VARCHAR(100),
            is_admin BOOLEAN DEFAULT FALSE
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
    password = generate_password_hash(data['password'])
    email = data['email']

    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO users (email, password_hash)
            VALUES (%s, %s);
        ''', (email, password))
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "Usuario registrado exitosamente"}), 201

# Ruta de inicio de sesión
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data['email']
    password = data['password']

    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user and check_password_hash(user[0], password):
        # Crear token JWT para el usuario autenticado
        access_token = create_access_token(identity=email)
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

# Ruta para obtener el perfil del usuario
@app.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    current_user = get_jwt_identity()

    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT email, full_name, phone, study_hours, specialty, hobbies, location
        FROM users WHERE email = %s;
    ''', (current_user,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        user_data = {
            "email": user[0],
            "full_name": user[1],
            "phone": user[2],
            "study_hours": user[3],
            "specialty": user[4],
            "hobbies": user[5],
            "location": user[6]
        }
        return jsonify(user_data), 200
    else:
        return jsonify({"error": "Usuario no encontrado"}), 404

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
            current_user
        ))
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "Perfil actualizado exitosamente"}), 200

# Ruta para interactuar con ChatGPT
@app.route('/chatgpt', methods=['POST'])
@jwt_required()
def chatgpt():
    current_user = get_jwt_identity()
    data = request.json
    user_message = data['message']

    try:
        # Realizar la solicitud a ChatGPT
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=user_message,
            max_tokens=150
        )
        chatgpt_response = response.choices[0].text.strip()

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"response": chatgpt_response})

# Ruta inicial de prueba
@app.route('/')
def home():
    return "¡Hola, mundo desde el backend!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
