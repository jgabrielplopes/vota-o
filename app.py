from flask import Flask, request, redirect, url_for, render_template_string, session, abort
from datetime import datetime
import psycopg2
import psycopg2.errors
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
    with get_db() as conn:
        with conn.cursor() as cur:
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
                    votacao_id INTEGER REFERENCES votacoes(id),
                    nome TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS votos (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER REFERENCES usuarios(id),
                    votacao_id INTEGER REFERENCES votacoes(id),
                    opcao_id INTEGER REFERENCES opcoes(id),
                    data_hora TIMESTAMP DEFAULT NOW(),
                    UNIQUE(usuario_id, votacao_id)
                )
            """)
        conn.commit()

criar_tabelas()

# --- Rota para login ---
@app.route("/", methods=["GET", "POST"])
def index():
    if "usuario_id" in session:
        return redirect(url_for("lista_votacoes"))
    erro = None
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, is_admin FROM usuarios WHERE email = %s AND senha = %s", (email, senha))
                user = cur.fetchone()
        if user:
            session["usuario_id"] = user[0]
            session["email"] = email
            session["is_admin"] = user[1]
            if user[1]:
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("lista_votacoes"))
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

# --- Rota para cadastro ---
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    erro = None
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO usuarios (email, senha) VALUES (%s, %s)", (email, senha))
                conn.commit()
            return redirect(url_for("index"))
        except psycopg2.errors.UniqueViolation:
            erro = "Email já cadastrado."
        except Exception as e:
            erro = f"Erro no cadastro: {str(e)}"
    return render_template_string("""
        <h2>Cadastro</h2>
        <form method="POST">
            Email: <input type="email" name="email" required><br>
            Senha: <input type="password" name="senha" required><br>
            <button type="submit">Cadastrar</button>
        </form>
        <p>Já tem conta? <a href="{{ url_for('index') }}">Entrar</a></p>
        {% if erro %}<p style="color:red">{{ erro }}</p>{% endif %}
    """, erro=erro)

# --- Rota para logout ---
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# --- Rota para listar votações ativas para o usuário votar ---
@app.route("/votacoes")
def lista_votacoes():
    if "usuario_id" not in session or session.get("is_admin"):
        return redirect(url_for("index"))
    agora = datetime.now()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, tema, inicio, fim FROM votacoes
                WHERE inicio <= %s AND fim >= %s
                ORDER BY inicio
            """, (agora, agora))
            votacoes_ativas = cur.fetchall()
    return render_template_string("""
        <h2>Votações Ativas</h2>
        {% if votacoes_ativas %}
            <ul>
                {% for v in votacoes_ativas %}
                    <li>
                        <a href="{{ url_for('votar', votacao_id=v[0]) }}">{{ v[1] }}</a>
                        ({{ v[2].strftime('%d/%m/%Y %H:%M') }} - {{ v[3].strftime('%d/%m/%Y %H:%M') }})
                    </li>
                {% endfor %}
            </ul>
        {% else %}
            <p>Não há votações ativas no momento.</p>
        {% endif %}
        <br><a href="{{ url_for('logout') }}">Sair</a>
    """, votacoes_ativas=votacoes_ativas)

# --- Rota para votar numa votação específica ---
@app.route("/votacao/<int:votacao_id>", methods=["GET", "POST"])
def votar(votacao_id):
    if "usuario_id" not in session or session.get("is_admin"):
        return redirect(url_for("index"))

    usuario_id = session["usuario_id"]
    agora = datetime.now()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tema, inicio, fim FROM votacoes WHERE id = %s", (votacao_id,))
            votacao = cur.fetchone()
            if not votacao:
                return "Votação não encontrada.", 404
            tema, inicio, fim = votacao
            if agora < inicio or agora > fim:
                return render_template_string("""
                    <h2>{{ tema }}</h2>
                    <p style="color:red">Esta votação está encerrada ou ainda não começou.</p>
                    <a href="{{ url_for('lista_votacoes') }}">Voltar às votações</a>
                """, tema=tema)

            cur.execute("SELECT id FROM votos WHERE usuario_id = %s AND votacao_id = %s", (usuario_id, votacao_id))
            if cur.fetchone():
                return redirect(url_for("resultado_votacao", votacao_id=votacao_id))

            cur.execute("SELECT id, nome FROM opcoes WHERE votacao_id = %s", (votacao_id,))
            opcoes = cur.fetchall()

            if request.method == "POST":
                opcao_id = request.form.get("opcao")
                if opcao_id is None:
                    return render_template_string("""
                        <h2>{{ tema }}</h2>
                        <p style="color:red">Selecione uma opção para votar.</p>
                        <a href="{{ url_for('votar', votacao_id=votacao_id) }}">Voltar</a>
                    """, tema=tema, votacao_id=votacao_id)

                cur.execute("SELECT id FROM opcoes WHERE id = %s AND votacao_id = %s", (opcao_id, votacao_id))
                if not cur.fetchone():
                    return "Opção inválida.", 400

                try:
                    cur.execute(
                        "INSERT INTO votos (usuario_id, votacao_id, opcao_id) VALUES (%s, %s, %s)",
                        (usuario_id, votacao_id, opcao_id)
                    )
                    conn.commit()
                except psycopg2.errors.UniqueViolation:
                    conn.rollback()
                    return "Você já votou nesta votação.", 400

                return redirect(url_for("resultado_votacao", votacao_id=votacao_id))

    return render_template_string("""
        <h2>Votação: {{ tema }}</h2>
        <form method="POST">
            {% for opcao in opcoes %}
                <input type="radio" id="opt{{ opcao[0] }}" name="opcao" value="{{ opcao[0] }}" required>
                <label for="opt{{ opcao[0] }}">{{ opcao[1] }}</label><br>
            {% endfor %}
            <br><button type="submit">Votar</button>
        </form>
        <br><a href="{{ url_for('lista_votacoes') }}">Voltar</a
