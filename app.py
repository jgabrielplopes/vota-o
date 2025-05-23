from flask import Flask, request, redirect, url_for, render_template_string, session
from datetime import datetime
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
        );
        CREATE TABLE IF NOT EXISTS votacoes (
            id SERIAL PRIMARY KEY,
            tema TEXT NOT NULL,
            inicio TIMESTAMP NOT NULL,
            fim TIMESTAMP NOT NULL
        );
        CREATE TABLE IF NOT EXISTS opcoes (
            id SERIAL PRIMARY KEY,
            votacao_id INTEGER REFERENCES votacoes(id),
            nome TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS votos (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER REFERENCES usuarios(id),
            opcao_id INTEGER REFERENCES opcoes(id),
            votacao_id INTEGER REFERENCES votacoes(id),
            data_hora TIMESTAMP DEFAULT NOW(),
            UNIQUE(usuario_id, votacao_id)
        );
    """)
    conn.commit()
    conn.close()

criar_tabelas()

# Verifica se está logado
@app.before_request
def verificar_login():
    if request.endpoint not in ("index", "cadastro", "static") and "usuario_id" not in session:
        return redirect(url_for("index"))

@app.route("/")
def index():
    return redirect(url_for("listar_votacoes"))

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO usuarios (email, senha) VALUES (%s, %s)", (email, senha))
            conn.commit()
            return redirect(url_for("login"))
        except:
            conn.rollback()
            return "Erro: email já cadastrado"
        finally:
            conn.close()
    return render_template_string("""
    <h2>Cadastro</h2>
    <form method="POST">
        Email: <input type="email" name="email"><br>
        Senha: <input type="password" name="senha"><br>
        <button type="submit">Cadastrar</button>
    </form>
    """)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, is_admin FROM usuarios WHERE email = %s AND senha = %s", (email, senha))
        user = cur.fetchone()
        conn.close()
        if user:
            session["usuario_id"] = user[0]
            session["is_admin"] = user[1]
            return redirect(url_for("listar_votacoes"))
        return "Login inválido"
    return render_template_string("""
    <h2>Login</h2>
    <form method="POST">
        Email: <input type="email" name="email"><br>
        Senha: <input type="password" name="senha"><br>
        <button type="submit">Entrar</button>
    </form>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/votacoes")
def listar_votacoes():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, tema, inicio, fim FROM votacoes ORDER BY fim DESC")
    votacoes = cur.fetchall()
    conn.close()
    return render_template_string("""
    <h2>Votações Disponíveis</h2>
    <ul>
        {% for id, tema, inicio, fim in votacoes %}
            <li>{{ tema }} - <a href="{{ url_for('votar', votacao_id=id) }}">Votar</a> | <a href="{{ url_for('resultado', votacao_id=id) }}">Resultado</a></li>
        {% endfor %}
    </ul>
    {% if session.get('is_admin') %}<a href="{{ url_for('admin') }}">Painel do Admin</a>{% endif %}
    <br><a href="{{ url_for('logout') }}">Sair</a>
    """, votacoes=votacoes)

@app.route("/votacao/<int:votacao_id>", methods=["GET", "POST"])
def votar(votacao_id):
    usuario_id = session["usuario_id"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT inicio, fim FROM votacoes WHERE id = %s", (votacao_id,))
    votacao = cur.fetchone()
    if not votacao:
        return "Votação não encontrada"

    agora = datetime.now()
    if agora < votacao[0] or agora > votacao[1]:
        return "Votação encerrada ou ainda não começou."

    cur.execute("SELECT 1 FROM votos WHERE usuario_id = %s AND votacao_id = %s", (usuario_id, votacao_id))
    if cur.fetchone():
        return redirect(url_for("resultado", votacao_id=votacao_id))

    if request.method == "POST":
        opcao_id = request.form.get("opcao")
        cur.execute("INSERT INTO votos (usuario_id, opcao_id, votacao_id) VALUES (%s, %s, %s)",
                    (usuario_id, opcao_id, votacao_id))
        conn.commit()
        conn.close()
        return redirect(url_for("resultado", votacao_id=votacao_id))

    cur.execute("SELECT id, nome FROM opcoes WHERE votacao_id = %s", (votacao_id,))
    opcoes = cur.fetchall()
    conn.close()
    return render_template_string("""
    <h2>Votação</h2>
    <form method="POST">
        {% for id, nome in opcoes %}
            <input type="radio" name="opcao" value="{{ id }}" required> {{ nome }}<br>
        {% endfor %}
        <button type="submit">Votar</button>
    </form>
    """, opcoes=opcoes)

@app.route("/resultado/<int:votacao_id>")
def resultado(votacao_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.nome, COUNT(v.id) as total
        FROM opcoes o
        LEFT JOIN votos v ON o.id = v.opcao_id
        WHERE o.votacao_id = %s
        GROUP BY o.id
        ORDER BY total DESC
    """, (votacao_id,))
    resultados = cur.fetchall()
    conn.close()
    return render_template_string("""
    <h2>Resultado</h2>
    <ul>
        {% for nome, total in resultados %}
            <li>{{ nome }}: {{ total }} voto(s)</li>
        {% endfor %}
    </ul>
    <a href="{{ url_for('listar_votacoes') }}">Voltar</a>
    """, resultados=resultados)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
