from flask import Flask, request, redirect, url_for, render_template_string, session
from datetime import datetime
import psycopg2
import os

app = Flask(__name__)
app.secret_key = "uma-chave-secreta-segura"

# Configuração do PostgreSQL com variáveis de ambiente
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

# Criação das tabelas
def criar_tabelas():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votos (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER REFERENCES usuarios(id),
            partido TEXT NOT NULL,
            data_hora TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    conn.close()

criar_tabelas()

# Página inicial
@app.route("/")
def home():
    return render_template_string("""
    <h2>Bem-vindo ao Sistema de Votação</h2>
    <a href="{{ url_for('login') }}">Fazer login</a> |
    <a href="{{ url_for('cadastro') }}">Cadastrar-se</a>
    """)

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if "usuario_id" in session:
        return redirect(url_for("votacao"))

    erro = None
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE email = %s AND senha = %s", (email, senha))
        user = cur.fetchone()
        conn.close()

        if user:
            session["usuario_id"] = user[0]
            session["email"] = email
            return redirect(url_for("votacao"))
        else:
            erro = "Email ou senha incorretos."

    return render_template_string("""
    <h2>Login</h2>
    <form method="POST">
        Email: <input type="email" name="email" required><br>
        Senha: <input type="password" name="senha" required><br>
        <button type="submit">Entrar</button>
    </form>
    <p>Não tem conta? <a href="{{ url_for('cadastro') }}">Cadastrar-se</a></p>
    {% if erro %}<p style="color:red">{{ erro }}</p>{% endif %}
    """, erro=erro)

# Cadastro
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    erro = None
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO usuarios (email, senha) VALUES (%s, %s)", (email, senha))
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except psycopg2.errors.UniqueViolation:
            erro = "Email já cadastrado."

    return render_template_string("""
    <h2>Cadastro</h2>
    <form method="POST">
        Email: <input type="email" name="email" required><br>
        Senha: <input type="password" name="senha" required><br>
        <button type="submit">Cadastrar</button>
    </form>
    <p>Já tem conta? <a href="{{ url_for('login') }}">Entrar</a></p>
    {% if erro %}<p style="color:red">{{ erro }}</p>{% endif %}
    """, erro=erro)

# Verifica horário da votação
def dentro_do_horario():
    agora = datetime.now().time()
    return datetime.strptime("08:00", "%H:%M").time() <= agora <= datetime.strptime("20:00", "%H:%M").time()

# Votação
@app.route("/votacao", methods=["GET", "POST"])
def votacao():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    usuario_id = session["usuario_id"]
    fora_do_horario = not dentro_do_horario()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM votos WHERE usuario_id = %s", (usuario_id,))
    ja_votou = cur.fetchone()
    conn.close()

    if ja_votou:
        return redirect(url_for("resultado"))

    if request.method == "POST" and not fora_do_horario:
        partido = request.form.get("voto")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO votos (usuario_id, partido) VALUES (%s, %s)", (usuario_id, partido))
        conn.commit()
        conn.close()
        return redirect(url_for("resultado"))

    return render_template_string("""
    <h2>Votação</h2>
    {% if fora_do_horario %}
        <p style="color:red">Votação permitida apenas entre 08:00 e 20:00.</p>
    {% else %}
        <form method="POST">
            <button type="submit" name="voto" value="Partido A">Votar no Partido A</button><br>
            <button type="submit" name="voto" value="Partido B">Votar no Partido B</button><br>
            <button type="submit" name="voto" value="Partido C">Votar no Partido C</button><br>
            <button type="submit" name="voto" value="Abstenções">Abster-se</button>
        </form>
    {% endif %}
    <br><a href="{{ url_for('resultado') }}">Ver resultado</a>
    """, fora_do_horario=fora_do_horario)

# Resultado
@app.route("/resultado")
def resultado():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT partido, COUNT(*) FROM votos GROUP BY partido")
    resultados = cur.fetchall()
    conn.close()

    contagem = {partido: 0 for partido in ["Partido A", "Partido B", "Partido C", "Abstenções"]}
    for partido, total in resultados:
        contagem[partido] = total

    max_votos = max(contagem["Partido A"], contagem["Partido B"], contagem["Partido C"])
    vencedores = [p for p in ["Partido A", "Partido B", "Partido C"] if contagem[p] == max_votos and max_votos > 0]

    return render_template_string("""
    <h2>Resultado da Votação</h2>
    <ul>
        {% for partido, total in contagem.items() %}
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

    <br><a href="{{ url_for('votacao') }}">Voltar</a>
    """, contagem=contagem, vencedores=vencedores)

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Iniciar app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
