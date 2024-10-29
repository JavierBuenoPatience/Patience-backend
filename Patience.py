from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import psycopg2

app = Flask(__name__)

# Configuración de la clave secreta para JWT
app.config['JWT_SECRET_KEY'] = 'supersecreto'  # Cambia esta clave secreta en un entorno de producción
jwt = JWTManager(app)

# URL de la base de datos en Render (asegúrate de que sea correcta)
DATABASE_URL = "postgresql://patience_db_user:MG6yUiJuOHYyKXN8xYJx4TqQGY8n6uxl@dpg-csf68i3tq21c738k77sg-a.oregon-postgres.render.com/patience_db"

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
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email VARCHAR(50) UNIQUE NOT NULL,
            hobbies TEXT,
            study_hours INT
        );
    ''')

    # Tabla de grupos
    cur.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            description TEXT
        );
    ''')

    # Tabla de mensajes
    cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id),
            group_id INT REFERENCES groups(id),
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    username = data['username']
    password = generate_password_hash(data['password'])
    email = data['email']
    hobbies = data.get('hobbies', '')
    study_hours = data.get('study_hours', 0)

    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO users (username, password_hash, email, hobbies, study_hours)
            VALUES (%s, %s, %s, %s, %s);
        ''', (username, password, email, hobbies, study_hours))
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
    username = data['username']
    password = data['password']

    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user and check_password_hash(user[0], password):
        # Crear token JWT para el usuario autenticado
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

# Ruta para crear un grupo
@app.route('/create_group', methods=['POST'])
@jwt_required()
def create_group():
    data = request.json
    group_name = data['name']
    description = data.get('description', '')

    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO groups (name, description)
            VALUES (%s, %s);
        ''', (group_name, description))
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "Grupo creado exitosamente"}), 201

# Ruta para enviar un mensaje en un grupo
@app.route('/send_message', methods=['POST'])
@jwt_required()
def send_message():
    current_user = get_jwt_identity()
    data = request.json
    group_id = data['group_id']
    message = data['message']

    # Obtener el ID del usuario
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = %s", (current_user,))
    user_id = cur.fetchone()[0]

    try:
        cur.execute('''
            INSERT INTO messages (user_id, group_id, message)
            VALUES (%s, %s, %s);
        ''', (user_id, group_id, message))
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "Mensaje enviado exitosamente"}), 201

# Ruta para obtener mensajes de un grupo
@app.route('/get_messages/<int:group_id>', methods=['GET'])
@jwt_required()
def get_messages(group_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT users.username, messages.message, messages.timestamp
        FROM messages
        JOIN users ON messages.user_id = users.id
        WHERE messages.group_id = %s
        ORDER BY messages.timestamp ASC;
    ''', (group_id,))
    messages = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([{"username": msg[0], "message": msg[1], "timestamp": msg[2]} for msg in messages])

# Ruta inicial de prueba
@app.route('/')
def home():
    return "¡Hola, mundo desde el backend!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
