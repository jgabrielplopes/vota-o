from flask import Flask, request, redirect, url_for, render_template_string, session
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os

app = Flask(__name__)
app.secret_key = "uma-chave-secreta-muito-segura"

# Config MySQL (troque pelos seus dados)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'seu_usuario',
    'password': 'sua_senha',
    'database': 'votacao_db',
    'auth_plugin': 'mysql_native_password'
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def criar_tabelas():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        senha VARCHAR(255) NOT NULL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS votos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        partido VARCHAR(50) NOT NULL,
        horario DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_voto_email (email)
    );
    """)
    conn.commit()
    cursor.close()
    conn.close()

criar_tabelas()

def dentro_do_horario():
    agora = datetime.now().time()
    return datetime.strptime("08:00", "%H:%M").time() <= agora <= datetime.strptime("20:00", "%H:%M").time()

def usuario_ja_votou(email):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM votos WHERE email = %s", (email,))
    ja_votou = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return ja_votou

def salvar_voto(email, partido):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO votos (email, partido) VALUES (%s, %s)", (email, partido))
        conn.commit()
    except mysql.connector.errors.IntegrityError:
        # Tentou votar duas vezes, ignore ou trate
        pass
    cursor.close()
    conn.close()

def contar_votos():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
    SELECT partido, COUNT(*) as total FROM votos
    GROUP BY partido
    """)
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    votos_contagem = {"Partido A": 0, "Partido B": 0, "Partido C": 0, "Abstenções": 0}
    for row in resultados:
        if row['partido'] in votos_contagem:
            votos_contagem[row['partido']] = row['total']
    return votos_contagem

@app.route("/")
def home():
    if session.get("email"):
        return redirect(url_for("votacao"))
    return redirect(url_for("login"))

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        if not email or not senha:
            return "Preencha email e senha", 400
        senha_hash = generate_password_hash(senha)
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO usuarios (email, senha) VALUES (%s, %s)", (email, senha_hash))
            conn.commit()
        except mysql.connector.errors.IntegrityError:
            cursor.close()
            conn.close()
            return "Email já cadastrado.", 400
        cursor.close()
        conn.close()
        return redirect(url_for("login"))
    return render_template_string("""
    <h2>Registro</h2>
    <form method="POST">
      Email: <input type="email" name="email" required><br><br>
      Senha: <input type="password" name="senha" required><br><br>
      <button type="submit">Registrar</button>
    </form>
    <a href="{{ url_for('login') }}">Já tem conta? Faça login</a>
    """)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        usuario = cursor.fetchone()
        cursor.close()
        conn.close()
        if usuario and check_password_hash(usuario["senha"], senha):
            session["email"] = email
            return redirect(url_for("votacao"))
        else:
            return "Credenciais inválidas", 401
    return render_template_string("""
    <h2>Login</h2>
    <form method="POST">
      Email: <input type="email" name="email" required><br><br>
      Senha: <input type="password" name="senha" required><br><br>
      <button type="submit">Entrar</button>
    </form>
    <a href="{{ url_for('registro') }}">Não tem conta? Registre-se</a>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/votacao", methods=["GET", "POST"])
def votacao():
    if not session.get("email"):
        return redirect(url_for("login"))

    if usuario_ja_votou(session["email"]):
        session["ja_votou"] = True
        return redirect(url_for("resultado"))

    if not dentro_do_horario():
        return render_template_string("""
        <h1>Votação</h1>
        <p style="color:red;">A votação está disponível apenas entre 08:00 e 20:00.</p>
        <p>Usuário logado: {{ email }}</p>
        <a href="{{ url_for('logout') }}">Logout</a>
        """, email=session["email"])

    if request.method == "POST":
        voto = request.form.get("voto")
        if voto in ["Partido A", "Partido B", "Partido C", "Abstenções"]:
            salvar_voto(session["email"], voto)
            session["ja_votou"] = True
            return redirect(url_for("resultado"))

    return render_template_string("""
    <h1>Votação</h1>
    <p>Usuário logado: {{ email }}</p>
    <form method="POST">
        <button type="submit" name="voto" value="Partido A">Votar Partido A</button><br><br>
        <button type="submit" name="voto" value="Partido B">Votar Partido B</button><br><br>
        <button type="submit" name="voto" value="Partido C">Votar Partido C</button><br><br>
        <button type="submit" name="voto" value="Abstenções">Abster-se</button>
    </form>
    <br>
    <a href="{{ url_for('logout') }}">Logout</a>
    """, email=session["email"])

@app.route("/resultado")
def resultado():
    if not session.get("email"):
        return redirect(url_for("login"))

    votos = contar_votos()
    max_votos = max(votos["Partido A"], votos["Partido B"], votos["Partido C"])
    vencedores = [p for p in ["Partido A", "Partido B", "Partido C"] if votos[p] == max_votos and max_votos > 0]

    return render_template_string("""
    <h1>Resultado</h1>
    <ul>
      {% for partido, total in votos.items() %}
        <li>{{ partido }}: {{ total }} voto(s)</li>
      {% endfor %}
    </ul>

    {% if vencedores|length == 0 %}
      <p>Nenhum partido recebeu votos.</p>
    {% elif vencedores|length == 1 %}
      <p><strong>Vencedor: {{ vencedores[0] }}</strong></p>
    {% else %}
      <p><strong>Empate entre: {{ vencedores | join(', ') }}</strong></p>
    {% endif %}

    <br>
    <a href="{{ url_for('votacao') }}">Voltar para votação</a><br>
    <a href="{{ url_for('logout') }}">Logout</a>
    """, votos=votos, vencedores=vencedores)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

