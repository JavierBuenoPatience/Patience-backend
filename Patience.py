from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "¡Hola, mundo desde el backend!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
import psycopg2
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = "postgresql://patience_db_user:MG6yUiJuOHYyKXN8xYJx4TqQGY8n6uxl@dpg-csf68i3tq21c738k77sg-a.oregon-postgres.render.com/patience_db"  # Reemplaza con la URL de tu base de datos de Render

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

