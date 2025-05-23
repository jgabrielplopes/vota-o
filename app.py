from flask import Flask, request, redirect, url_for, render_template_string, session, abort
from datetime import datetime
import psycopg2
import os
from psycopg2 import errors
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "uma-chave-secreta-segura")

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
            opcao_id INTEGER REFERENCES opcoes(id) ON DELETE CASCADE,
            data_hora TIMESTAMP DEFAULT NOW(),
            UNIQUE(usuario_id, votacao_id)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

criar_tabelas()

# --- Rota para login ---
@app.route("/", methods=["GET", "POST"])
def index():
    if "usuario_id" in session:
        if session.get("is_admin"):
            return redirect(url_for("admin_dashboard"))
        else:
            return redirect(url_for("lista_votacoes"))

    erro = None
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, senha, is_admin FROM usuarios WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user[1], senha):
            session["usuario_id"] = user[0]
            session["email"] = email
            session["is_admin"] = user[2]
            if user[2]:
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
        senha_hash = generate_password_hash(senha)
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO usuarios (email, senha) VALUES (%s, %s)", (email, senha_hash))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for("index"))
        except errors.UniqueViolation:
            erro = "Email já cadastrado."
            conn.rollback()
            cur.close()
            conn.close()
        except Exception as e:
            erro = "Erro ao cadastrar usuário."
            conn.rollback()
            cur.close()
            conn.close()
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
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, tema, inicio, fim FROM votacoes
        WHERE inicio <= %s AND fim >= %s
        ORDER BY inicio
    """, (agora, agora))
    votacoes_ativas = cur.fetchall()
    cur.close()
    conn.close()
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

    conn = get_db()
    cur = conn.cursor()
    # Verifica se votação existe e está ativa
    cur.execute("SELECT tema, inicio, fim FROM votacoes WHERE id = %s", (votacao_id,))
    votacao = cur.fetchone()
    if not votacao:
        cur.close()
        conn.close()
        return "Votação não encontrada.", 404
    tema, inicio, fim = votacao
    if agora < inicio or agora > fim:
        cur.close()
        conn.close()
        return render_template_string("""
            <h2>{{ tema }}</h2>
            <p style="color:red">Esta votação está encerrada ou ainda não começou.</p>
            <a href="{{ url_for('lista_votacoes') }}">Voltar às votações</a>
        """, tema=tema)

    # Verifica se já votou nesta votação
    cur.execute("SELECT id FROM votos WHERE usuario_id = %s AND votacao_id = %s", (usuario_id, votacao_id))
    if cur.fetchone():
        cur.close()
        conn.close()
        return redirect(url_for("resultado_votacao", votacao_id=votacao_id))

    # Busca opções para votação
    cur.execute("SELECT id, nome FROM opcoes WHERE votacao_id = %s", (votacao_id,))
    opcoes = cur.fetchall()

    if request.method == "POST":
        opcao_id = request.form.get("opcao")
        if not opcao_id:
            cur.close()
            conn.close()
            return render_template_string("""
                <h2>{{ tema }}</h2>
                <p style="color:red">Selecione uma opção para votar.</p>
                <a href="{{ url_for('votar', votacao_id=votacao_id) }}">Voltar</a>
            """, tema=tema, votacao_id=votacao_id)
        # Confirma opção existe e pertence a essa votação
        cur.execute("SELECT id FROM opcoes WHERE id = %s AND votacao_id = %s", (opcao_id, votacao_id))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return "Opção inválida.", 400
        # Insere voto
        try:
            cur.execute(
                "INSERT INTO votos (usuario_id, votacao_id, opcao_id) VALUES (%s, %s, %s)",
                (usuario_id, votacao_id, opcao_id)
            )
            conn.commit()
        except errors.UniqueViolation:
            conn.rollback()
            cur.close()
            conn.close()
            return "Você já votou nesta votação.", 400
        except Exception:
            conn.rollback()
            cur.close()
            conn.close()
            return "Erro ao registrar voto.", 500
        cur.close()
        conn.close()
        return redirect(url_for("resultado_votacao", votacao_id=votacao_id))

    cur.close()
    conn.close()
    return render_template_string("""
        <h2>Votação: {{ tema }}</h2>
        <form method="POST">
            {% for opcao in opcoes %}
                <input type="radio" id="opt{{ opcao[0] }}" name="opcao" value="{{ opcao[0] }}" required>
                <label for="opt{{ opcao[0] }}">{{ opcao[1] }}</label><br>
            {% endfor %}
            <br><button type="submit">Votar</button>
        </form>
        <br><a href="{{ url_for('lista_votacoes') }}">Voltar</a>
    """, tema=tema, opcoes=opcoes)

# --- Rota para mostrar resultado de uma votação ---
@app.route("/resultado/<int:votacao_id>")
def resultado_votacao(votacao_id):
    if "usuario_id" not in session:
        return redirect(url_for("index"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT tema, inicio, fim FROM votacoes WHERE id = %s", (votacao_id,))
    votacao = cur.fetchone()
    if not votacao:
        cur.close()
        conn.close()
        return "Votação não encontrada.", 404
    tema, inicio, fim = votacao

    # Busca opções e votos
    cur.execute("""
        SELECT op.nome, COUNT(v.id)
        FROM opcoes op
        LEFT JOIN votos v ON v.opcao_id = op.id
        WHERE op.votacao_id = %s
        GROUP BY op.nome
        ORDER BY op.nome
    """, (votacao_id,))
    resultados = cur.fetchall()
    cur.close()
    conn.close()

    max_votos = max([r[1] for r in resultados]) if resultados else 0
    vencedores = [r[0] for r in resultados if r[1] == max_votos and max_votos > 0]

    return render_template_string("""
        <h2>Resultado da Votação: {{ tema }}</h2>
        <ul>
        {% for nome, total in resultados %}
            <li>{{ nome }}: {{ total }} voto(s)</li>
        {% endfor %}
        </ul>

        {% if max_votos == 0 %}
            <p>Nenhum voto registrado.</p>
        {% elif vencedores|length == 1 %}
            <p><strong>Vencedor: {{ vencedores[0] }}</strong></p>
        {% else %}
            <p><strong>Empate entre: {{ vencedores | join(', ') }}</strong></p>
        {% endif %}

        <br
