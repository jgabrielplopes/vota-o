from flask import Flask, request, redirect, url_for, render_template_string, session
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "uma-chave-secreta"

DATABASE = "votacao.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def criar_tabelas():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS votos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            voto TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    ''')
    conn.commit()
    conn.close()

def dentro_do_horario():
    agora = datetime.now().time()
    return datetime.strptime("08:00", "%H:%M").time() <= agora <= datetime.strptime("20:00", "%H:%M").time()

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE email=? AND senha=?", (email, senha))
        user = cur.fetchone()
        if user:
            session["usuario_id"] = user["id"]
            session["email"] = user["email"]
            return redirect(url_for("votacao"))
        else:
            cur.execute("INSERT INTO usuarios (email, senha) VALUES (?, ?)", (email, senha))
            conn.commit()
            session["usuario_id"] = cur.lastrowid
            session["email"] = email
            return redirect(url_for("votacao"))
    return render_template_string('''
        <h2>Login / Cadastro</h2>
        <form method="POST">
            Email: <input type="email" name="email" required><br>
            Senha: <input type="password" name="senha" required><br>
            <button type="submit">Entrar</button>
        </form>
    ''')

@app.route("/votacao", methods=["GET", "POST"])
def votacao():
    if not session.get("usuario_id"):
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM votos WHERE usuario_id=?", (session["usuario_id"],))
    if cur.fetchone():
        return redirect(url_for("resultado"))

    fora_do_horario = not dentro_do_horario()

    if request.method == "POST" and not fora_do_horario:
        voto = request.form.get("voto")
        cur.execute("INSERT INTO votos (usuario_id, voto) VALUES (?, ?)", (session["usuario_id"], voto))
        conn.commit()
        return redirect(url_for("resultado"))

    return render_template_string("""
        <h1>Votação</h1>
        {% if fora_do_horario %}
            <p style="color: red;">Fora do horário de votação (08h às 20h).</p>
        {% else %}
            <form method="POST">
                <button name="voto" value="Partido A">Partido A</button><br>
                <button name="voto" value="Partido B">Partido B</button><br>
                <button name="voto" value="Partido C">Partido C</button><br>
                <button name="voto" value="Abstenção">Abster-se</button>
            </form>
        {% endif %}
        <br><a href="{{ url_for('resultado') }}">Ver resultado</a>
    """, fora_do_horario=fora_do_horario)

@app.route("/resultado")
def resultado():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT voto, COUNT(*) as total FROM votos GROUP BY voto")
    resultados = cur.fetchall()

    votos_dict = {linha["voto"]: linha["total"] for linha in resultados}
    todos = ["Partido A", "Partido B", "Partido C"]
    max_voto = max([votos_dict.get(p, 0) for p in todos], default=0)
    vencedores = [p for p in todos if votos_dict.get(p, 0) == max_voto and max_voto > 0]

    return render_template_string("""
        <h2>Resultado da Votação</h2>
        <ul>
        {% for voto, total in votos.items() %}
            <li>{{ voto }}: {{ total }} voto(s)</li>
        {% endfor %}
        </ul>
        {% if vencedores|length == 0 %}
            <p>Nenhum voto registrado.</p>
        {% elif vencedores|length == 1 %}
            <p>Vencedor: <strong>{{ vencedores[0] }}</strong></p>
        {% else %}
            <p>Empate entre: <strong>{{ vencedores | join(', ') }}</strong></p>
        {% endif %}
        <br><a href="{{ url_for('votacao') }}">Voltar</a>
    """, votos=votos_dict, vencedores=vencedores)

if __name__ == "__main__":
    criar_tabelas()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
