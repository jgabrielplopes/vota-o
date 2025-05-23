from flask import Flask, request, redirect, url_for, render_template_string, session
from datetime import datetime, timedelta
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votacao_status (
            id SERIAL PRIMARY KEY,
            fim_votacao TIMESTAMP NOT NULL,
            ativa BOOLEAN DEFAULT TRUE
        )
    """)
    cur.execute("SELECT COUNT(*) FROM votacao_status")
    if cur.fetchone()[0] == 0:
        fim = datetime.combine(datetime.now().date(), datetime.strptime("20:00", "%H:%M").time())
        cur.execute("INSERT INTO votacao_status (fim_votacao, ativa) VALUES (%s, %s)", (fim, True))
    conn.commit()
    conn.close()

criar_tabelas()

def votacao_ativa():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT fim_votacao, ativa FROM votacao_status ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        fim_votacao, ativa = row
        return ativa and datetime.now() <= fim_votacao
    return False

@app.route("/", methods=["GET", "POST"])
def index():
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

@app.route("/votacao", methods=["GET", "POST"])
def votacao():
    if "usuario_id" not in session:
        return redirect(url_for("index"))

    usuario_id = session["usuario_id"]
    ativa = votacao_ativa()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM votos WHERE usuario_id = %s", (usuario_id,))
    ja_votou = cur.fetchone()

    if ja_votou:
        conn.close()
        return redirect(url_for("resultado"))

    if request.method == "POST":
        if not ativa:
            conn.close()
            return render_template_string("<p style='color:red'>A votação foi encerrada.</p><a href='{{ url_for('resultado') }}'>Ver resultado</a>")
        partido = request.form.get("voto")
        if not partido:
            conn.close()
            return render_template_string("<p style='color:red'>Selecione um partido.</p><a href='{{ url_for('votacao') }}'>Voltar</a>")
        cur.execute("INSERT INTO votos (usuario_id, partido) VALUES (%s, %s)", (usuario_id, partido))
        conn.commit()
        conn.close()
        return redirect(url_for("resultado"))

    conn.close()
    return render_template_string("""
    <h2>Votação</h2>
    {% if not ativa %}<p style="color:red">A votação foi encerrada.</p>{% else %}
    <form method="POST">
        <input type="radio" name="voto" value="Partido A" required> Partido A<br>
        <input type="radio" name="voto" value="Partido B"> Partido B<br>
        <input type="radio" name="voto" value="Partido C"> Partido C<br>
        <input type="radio" name="voto" value="Abstenções"> Abstenções<br><br>
        <button type="submit">Confirmar Voto</button>
    </form>
    {% endif %}
    <br><a href="{{ url_for('resultado') }}">Ver resultado</a>
    """, ativa=ativa)

@app.route("/resultado")
def resultado():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT partido, COUNT(*) FROM votos GROUP BY partido")
    resultados = cur.fetchall()
    conn.close()

    contagem = {p: 0 for p in ["Partido A", "Partido B", "Partido C", "Abstenções"]}
    for partido, total in resultados:
        contagem[partido] = total

    max_votos = max([contagem[p] for p in ["Partido A", "Partido B", "Partido C"]])
    vencedores = [p for p in ["Partido A", "Partido B", "Partido C"] if contagem[p] == max_votos and max_votos > 0]

    return render_template_string("""
    <h2>Resultado da Votação</h2>
    <ul>
    {% for partido, total in contagem.items() %}
        <li>{{ partido }}: {{ total }} voto(s)</li>
    {% endfor %}
    </ul>
    {% if vencedores|length == 0 %}<p>Nenhum partido recebeu votos.</p>
    {% elif vencedores|length == 1 %}<p><strong>Vencedor: {{ vencedores[0] }}</strong></p>
    {% else %}<p><strong>Empate entre: {{ vencedores|join(', ') }}</strong></p>
    {% endif %}
    <br><a href="{{ url_for('votacao') }}">Voltar</a> | <a href="{{ url_for('logout') }}">Sair</a>
    """, contagem=contagem, vencedores=vencedores)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/admin/resetar", methods=["GET", "POST"])
def resetar_votacao():
    senha_admin = "senha123"  # Altere para uma senha forte
    if request.method == "POST":
        senha = request.form.get("senha")
        if senha != senha_admin:
            return "Senha inválida", 403
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM votos")
        novo_fim = datetime.now() + timedelta(hours=1)
        cur.execute("UPDATE votacao_status SET ativa = FALSE")
        cur.execute("INSERT INTO votacao_status (fim_votacao, ativa) VALUES (%s, %s)", (novo_fim, True))
        conn.commit()
        conn.close()
        return f"Votação resetada! Nova votação vai até: {novo_fim.strftime('%Y-%m-%d %H:%M')}"
    return """
    <form method='POST'>
        Senha Admin: <input type='password' name='senha' required>
        <button type='submit'>Resetar Votação</button>
    </form>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
