from flask import Flask, request, redirect, url_for, render_template_string, session, flash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "uma-chave-secreta-muito-segura"

# Dicionário de votos
votos = {
    "Partido A": 0,
    "Partido B": 0,
    "Partido C": 0,
    "Abstenções": 0
}

# Usuários cadastrados: email -> senha (para simplificar, em memória)
# Você pode carregar de arquivo se quiser, mas aqui só o cadastro novo salva email em arquivo.
usuarios = {}

USUARIOS_TXT = "usuarios.txt"

# Função para carregar usuários do arquivo usuarios.txt (se quiser carregar ao iniciar)
def carregar_usuarios():
    if os.path.exists(USUARIOS_TXT):
        with open(USUARIOS_TXT, "r") as f:
            for linha in f:
                email = linha.strip()
                if email:
                    usuarios[email] = "senha123"  # Coloque senha padrão ou mude conforme seu uso

carregar_usuarios()

def salvar_email(email):
    with open(USUARIOS_TXT, "a") as f:
        f.write(email + "\n")

def dentro_do_horario():
    agora = datetime.now().time()
    return datetime.strptime("08:00", "%H:%M").time() <= agora <= datetime.strptime("20:00", "%H:%M").time()

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        senha = request.form.get("senha")
        senha_conf = request.form.get("senha_conf")

        if not email or not senha or not senha_conf:
            flash("Preencha todos os campos.")
        elif senha != senha_conf:
            flash("As senhas não coincidem.")
        elif email in usuarios:
            flash("Email já cadastrado.")
        else:
            usuarios[email] = senha
            salvar_email(email)
            flash("Cadastro realizado! Faça login.")
            return redirect(url_for("login"))
    return render_template_string("""
    <!DOCTYPE html>
    <html><head><title>Cadastro</title></head><body>
    <h1>Cadastro</h1>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <ul style="color:red;">
          {% for msg in messages %}
            <li>{{ msg }}</li>
          {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}
    <form method="POST">
      Email: <input type="email" name="email" required><br><br>
      Senha: <input type="password" name="senha" required><br><br>
      Confirme a senha: <input type="password" name="senha_conf" required><br><br>
      <button type="submit">Cadastrar</button>
    </form>
    <p>Já tem cadastro? <a href="{{ url_for('login') }}">Login aqui</a></p>
    </body></html>
    """)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        senha = request.form.get("senha")

        if email in usuarios and usuarios[email] == senha:
            session["usuario"] = email
            session["ja_votou"] = False  # reseta votação ao logar
            return redirect(url_for("index"))
        else:
            flash("Email ou senha incorretos.")

    return render_template_string("""
    <!DOCTYPE html>
    <html><head><title>Login</title></head><body>
    <h1>Login</h1>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <ul style="color:red;">
          {% for msg in messages %}
            <li>{{ msg }}</li>
          {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}
    <form method="POST">
      Email: <input type="email" name="email" required><br><br>
      Senha: <input type="password" name="senha" required><br><br>
      <button type="submit">Entrar</button>
    </form>
    <p>Não tem cadastro? <a href="{{ url_for('cadastro') }}">Cadastre-se aqui</a></p>
    </body></html>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
def index():
    if "usuario" not in session:
        return redirect(url_for("login"))

    if session.get("ja_votou"):
        return redirect(url_for("resultado"))

    fora_do_horario = not dentro_do_horario()

    if request.method == "POST":
        voto = request.form.get("voto")
        if voto in votos:
            votos[voto] += 1
            session["ja_votou"] = True
            return redirect(url_for("resultado"))

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>Votação</title></head>
    <body>
        <h1>Sistema de Votação</h1>
        <p>Usuário logado: <strong>{{ usuario }}</strong> | <a href="{{ url_for('logout') }}">Sair</a></p>

        {% if fora_do_horario %}
            <p style="color: red;">Votação disponível apenas entre 08:00 e 20:00.</p>
        {% else %}
            <form method="POST">
                <button type="submit" name="voto" value="Partido A">Votar no Partido A</button><br><br>
                <button type="submit" name="voto" value="Partido B">Votar no Partido B</button><br><br>
                <button type="submit" name="voto" value="Partido C">Votar no Partido C</button><br><br>
                <button type="submit" name="voto" value="Abstenções">Abster-se</button>
            </form>
        {% endif %}

        <br><br>
        <a href="{{ url_for('resultado') }}">Ver resultado parcial / final</a>
    </body>
    </html>
    """, fora_do_horario=fora_do_horario, usuario=session["usuario"])

@app.route("/resultado")
def resultado():
    if "usuario" not in session:
        return redirect(url_for("login"))

    max_votos = max(votos["Partido A"], votos["Partido B"], votos["Partido C"])
    vencedores = [p for p in ["Partido A", "Partido B", "Partido C"] if votos[p] == max_votos and max_votos > 0]

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>Resultado da Votação</title></head>
    <body>
        <h1>Resultado Final</h1>
        <p>Usuário logado: <strong>{{ usuario }}</strong> | <a href="{{ url_for('logout') }}">Sair</a></p>
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
        <p><a href="{{ url_for('index') }}">Voltar para votação</a></p>
    </body>
    </html>
    """, votos=votos, vencedores=vencedores, usuario=session["usuario"])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

