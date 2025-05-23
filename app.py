from flask import Flask, request, redirect, url_for, render_template_string, session, abort
from datetime import datetime
import psycopg2
import os

app = Flask(__name__)
app.secret_key = "uma-chave-secreta-segura"

# Configuração do PostgreSQL via variáveis de ambiente
# Configuração do PostgreSQL com credenciais fixas
DB_CONFIG = {
    "host": "dpg-d0n5rvmmcj7s73dl446g-a",
    "database": "votacao_yh36",
    "user": "votacao_yh36_user",
    "password": "wTvdT9dkt02d3o6AriJb27V9Aen6DAVs",
    "port": "5432"
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
    conn.close()

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
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, is_admin FROM usuarios WHERE email = %s AND senha = %s", (email, senha))
        user = cur.fetchone()
        conn.close()
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
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO usuarios (email, senha) VALUES (%s, %s)", (email, senha))
            conn.commit()
            conn.close()
            return redirect(url_for("index"))
        except psycopg2.errors.UniqueViolation:
            erro = "Email já cadastrado."
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
    cur.execute("SELECT tema, inicio, fim FROM votacoes WHERE id = %s", (votacao_id,))
    votacao = cur.fetchone()
    if not votacao:
        conn.close()
        return "Votação não encontrada.", 404
    tema, inicio, fim = votacao
    if agora < inicio or agora > fim:
        conn.close()
        return render_template_string("""
            <h2>{{ tema }}</h2>
            <p style="color:red">Esta votação está encerrada ou ainda não começou.</p>
            <a href="{{ url_for('lista_votacoes') }}">Voltar às votações</a>
        """, tema=tema)

    cur.execute("SELECT id FROM votos WHERE usuario_id = %s AND votacao_id = %s", (usuario_id, votacao_id))
    if cur.fetchone():
        conn.close()
        return redirect(url_for("resultado_votacao", votacao_id=votacao_id))

    cur.execute("SELECT id, nome FROM opcoes WHERE votacao_id = %s", (votacao_id,))
    opcoes = cur.fetchall()

    if request.method == "POST":
        opcao_id = request.form.get("opcao")
        if opcao_id is None:
            conn.close()
            return render_template_string("""
                <h2>{{ tema }}</h2>
                <p style="color:red">Selecione uma opção para votar.</p>
                <a href="{{ url_for('votar', votacao_id=votacao_id) }}">Voltar</a>
            """, tema=tema, votacao_id=votacao_id)
        cur.execute("SELECT id FROM opcoes WHERE id = %s AND votacao_id = %s", (opcao_id, votacao_id))
        if not cur.fetchone():
            conn.close()
            return "Opção inválida.", 400
        try:
            cur.execute(
                "INSERT INTO votos (usuario_id, votacao_id, opcao_id) VALUES (%s, %s, %s)",
                (usuario_id, votacao_id, opcao_id)
            )
            conn.commit()
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            conn.close()
            return "Você já votou nesta votação.", 400
        conn.close()
        return redirect(url_for("resultado_votacao", votacao_id=votacao_id))

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
        conn.close()
        return "Votação não encontrada.", 404
    tema, inicio, fim = votacao

    cur.execute("""
        SELECT op.nome, COUNT(v.id)
        FROM opcoes op
        LEFT JOIN votos v ON v.opcao_id = op.id
        WHERE op.votacao_id = %s
        GROUP BY op.nome
        ORDER BY op.nome
    """, (votacao_id,))
    resultados = cur.fetchall()
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
        {% else %}
            <p><strong>Vencedor(es):</strong> {{ vencedores | join(", ") }}</p>
        {% endif %}
        <br><a href="{{ url_for('lista_votacoes') }}">Voltar às votações</a>
    """, tema=tema, resultados=resultados, max_votos=max_votos, vencedores=vencedores)

# --- Rota do dashboard do administrador ---
@app.route("/admin")
def admin_dashboard():
    if "usuario_id" not in session or not session.get("is_admin"):
        abort(403)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, tema, inicio, fim FROM votacoes ORDER BY inicio DESC")
    votacoes = cur.fetchall()
    conn.close()
    return render_template_string("""
        <h2>Administração</h2>
        <a href="{{ url_for('criar_votacao') }}">Criar nova votação</a><br><br>
        <h3>Votações Existentes</h3>
        <ul>
        {% for v in votacoes %}
            <li>
                {{ v[1] }} ({{ v[2].strftime('%d/%m/%Y %H:%M') }} - {{ v[3].strftime('%d/%m/%Y %H:%M') }})
                - <a href="{{ url_for('resultado_votacao', votacao_id=v[0]) }}">Ver Resultado</a>
            </li>
        {% endfor %}
        </ul>
        <br><a href="{{ url_for('logout') }}">Sair</a>
    """, votacoes=votacoes)

# --- Rota para criar votação ---
@app.route("/admin/criar", methods=["GET", "POST"])
def criar_votacao():
    if "usuario_id" not in session or not session.get("is_admin"):
        abort(403)

    erro = None
    if request.method == "POST":
        tema = request.form.get("tema")
        inicio_str = request.form.get("inicio")
        fim_str = request.form.get("fim")
        opcoes_str = request.form.get("opcoes")

        if not tema or not inicio_str or not fim_str or not opcoes_str:
            erro = "Todos os campos são obrigatórios."
        else:
            try:
                inicio = datetime.strptime(inicio_str, "%Y-%m-%dT%H:%M")
                fim = datetime.strptime(fim_str, "%Y-%m-%dT%H:%M")
                if fim <= inicio:
                    erro = "Data fim deve ser maior que data início."
                else:
                    opcoes = [o.strip() for o in opcoes_str.split(",") if o.strip()]
                    if len(opcoes) < 2:
                        erro = "Informe pelo menos duas opções separadas por vírgula."
                    else:
                        conn = get_db()
                        cur = conn.cursor()
                        cur.execute(
                            "INSERT INTO votacoes (tema, inicio, fim) VALUES (%s, %s, %s) RETURNING id",
                            (tema, inicio, fim)
                        )
                        votacao_id = cur.fetchone()[0]
                        for opcao in opcoes:
                            cur.execute(
                                "INSERT INTO opcoes (votacao_id, nome) VALUES (%s, %s)",
                                (votacao_id, opcao)
                            )
                        conn.commit()
                        conn.close()
                        return redirect(url_for("admin_dashboard"))
            except ValueError:
                erro = "Formato de data/hora inválido. Use o seletor correto."
    return render_template_string("""
        <h2>Criar Nova Votação</h2>
        <form method="POST">
            Tema: <input type="text" name="tema" required><br>
            Início: <input type="datetime-local" name="inicio" required><br>
            Fim: <input type="datetime-local" name="fim" required><br>
            Opções (separadas por vírgula): <input type="text" name="opcoes" required><br><br>
            <button type="submit">Criar</button>
        </form>
        {% if erro %}<p style="color:red">{{ erro }}</p>{% endif %}
        <br><a href="{{ url_for('admin_dashboard') }}">Voltar</a>
    """, erro=erro)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5432))
    app.run(host="0.0.0.0", port=port)
