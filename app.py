from flask import Flask, request, redirect, url_for, render_template_string, session, abort
from datetime import datetime, time
import psycopg2
import os

app = Flask(__name__)
app.secret_key = "uma-chave-secreta-segura"

# Configuração do PostgreSQL via variáveis de ambiente
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def criar_tabelas():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votacoes (
            id SERIAL PRIMARY KEY,
            tema TEXT NOT NULL,
            inicio TIMESTAMP NOT NULL,
            fim TIMESTAMP NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS opcoes (
            id SERIAL PRIMARY KEY,
            votacao_id INTEGER REFERENCES votacoes(id) ON DELETE CASCADE,
            nome TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votos (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
            votacao_id INTEGER REFERENCES votacoes(id) ON DELETE CASCADE,
            opcao_id INTEGER REFERENCES opcoes(id),
            data_hora TIMESTAMP DEFAULT NOW(),
            UNIQUE(usuario_id, votacao_id)
        )
    """)
    conn.commit()
    conn.close()

criar_tabelas()

# Rota inicial - links para login/cadastro/admin
@app.route("/")
def home():
    return render_template_string("""
        <h2>Sistema de Votação</h2>
        <p><a href="{{ url_for('login') }}">Login de Usuário</a></p>
        <p><a href="{{ url_for('cadastro') }}">Cadastro de Usuário</a></p>
        <p><a href="{{ url_for('admin_login') }}">Login de Administrador</a></p>
    """)

# Login usuário
@app.route("/login", methods=["GET", "POST"])
def login():
    if "usuario_id" in session:
        return redirect(url_for("lista_votacoes"))
    erro = None
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE email = %s AND senha = %s AND is_admin = FALSE", (email, senha))
        user = cur.fetchone()
        conn.close()
        if user:
            session["usuario_id"] = user[0]
            session["email"] = email
            session["is_admin"] = False
            return redirect(url_for("lista_votacoes"))
        else:
            erro = "Email ou senha incorretos."
    return render_template_string("""
        <h2>Login Usuário</h2>
        <form method="POST">
            Email: <input type="email" name="email" required><br>
            Senha: <input type="password" name="senha" required><br>
            <button type="submit">Entrar</button>
        </form>
        <p>Não tem conta? <a href="{{ url_for('cadastro') }}">Cadastrar-se</a></p>
        {% if erro %}<p style="color:red">{{ erro }}</p>{% endif %}
        <p><a href="{{ url_for('home') }}">Voltar</a></p>
    """, erro=erro)

# Cadastro usuário
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
        <h2>Cadastro Usuário</h2>
        <form method="POST">
            Email: <input type="email" name="email" required><br>
            Senha: <input type="password" name="senha" required><br>
            <button type="submit">Cadastrar</button>
        </form>
        <p>Já tem conta? <a href="{{ url_for('login') }}">Entrar</a></p>
        {% if erro %}<p style="color:red">{{ erro }}</p>{% endif %}
        <p><a href="{{ url_for('home') }}">Voltar</a></p>
    """, erro=erro)

# Login admin
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if "usuario_id" in session and session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    erro = None
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE email = %s AND senha = %s AND is_admin = TRUE", (email, senha))
        admin = cur.fetchone()
        conn.close()
        if admin:
            session["usuario_id"] = admin[0]
            session["email"] = email
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            erro = "Email ou senha incorretos."
    return render_template_string("""
        <h2>Login Administrador</h2>
        <form method="POST">
            Email: <input type="email" name="email" required><br>
            Senha: <input type="password" name="senha" required><br>
            <button type="submit">Entrar</button>
        </form>
        {% if erro %}<p style="color:red">{{ erro }}</p>{% endif %}
        <p><a href="{{ url_for('home') }}">Voltar</a></p>
    """, erro=erro)

# Dashboard admin
@app.route("/admin")
def admin_dashboard():
    if not session.get("is_admin"):
        abort(403)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, tema, inicio, fim FROM votacoes ORDER BY inicio DESC")
    votacoes = cur.fetchall()
    conn.close()
    return render_template_string("""
        <h2>Administração - Votações</h2>
        <p><a href="{{ url_for('criar_votacao') }}">Criar nova votação</a></p>
        <ul>
            {% for id, tema, inicio, fim in votacoes %}
                <li>
                    <strong>{{ tema }}</strong> ({{ inicio }} até {{ fim }})
                    - <a href="{{ url_for('ver_votacao_admin', votacao_id=id) }}">Detalhes</a>
                </li>
            {% else %}
                <li>Nenhuma votação cadastrada.</li>
            {% endfor %}
        </ul>
        <p><a href="{{ url_for('logout') }}">Sair</a></p>
    """, votacoes=votacoes)

# Criar votação (admin)
@app.route("/admin/criar", methods=["GET", "POST"])
def criar_votacao():
    if not session.get("is_admin"):
        abort(403)
    erro = None
    if request.method == "POST":
        tema = request.form.get("tema")
        inicio_str = request.form.get("inicio")
        fim_str = request.form.get("fim")
        opcoes = request.form.get("opcoes")  # Texto, uma opção por linha
        try:
            inicio = datetime.strptime(inicio_str, "%Y-%m-%dT%H:%M")
            fim = datetime.strptime(fim_str, "%Y-%m-%dT%H:%M")
            if inicio >= fim:
                erro = "Data/hora de início deve ser anterior à de fim."
            elif not opcoes or len(opcoes.strip()) == 0:
                erro = "Informe ao menos uma opção."
            else:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("INSERT INTO votacoes (tema, inicio, fim) VALUES (%s, %s, %s) RETURNING id", (tema, inicio, fim))
                votacao_id = cur.fetchone()[0]
                for opcao in opcoes.strip().split("\n"):
                    opcao = opcao.strip()
                    if opcao:
                        cur.execute("INSERT INTO opcoes (votacao_id, nome) VALUES (%s, %s)", (votacao_id, opcao))
                conn.commit()
                conn.close()
                return redirect(url_for("admin_dashboard"))
        except ValueError:
            erro = "Formato de data/hora inválido. Use YYYY-MM-DDTHH:MM"
    return render_template_string("""
        <h2>Criar Nova Votação</h2>
        {% if erro %}<p style="color:red">{{ erro }}</p>{% endif %}
        <form method="POST">
            Tema: <input type="text" name="tema" required><br>
            Início: <input type
