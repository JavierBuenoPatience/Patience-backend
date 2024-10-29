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

# Creación de la tabla de usuarios
def create_user_table():
    conn = connect_db()
    cur = conn.cursor()
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
    conn.commit()
    cur.close()
    conn.close()

# Llama a la función para crear la tabla cuando inicie el servidor
create_user_table()

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

# Ruta protegida de ejemplo (solo accesible con token)
@app.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    current_user = get_jwt_identity()
    return jsonify({"username": current_user, "message": "Perfil del usuario"}), 200

# Ruta inicial de prueba
@app.route('/')
def home():
    return "¡Hola, mundo desde el backend!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

