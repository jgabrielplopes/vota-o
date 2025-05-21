from flask import Flask, request, redirect, url_for, render_template_string, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = "uma-chave-secreta-muito-segura"  # obrigatório para usar sessões

# Dicionário de votos
votos = {
    "Partido A": 0,
    "Partido B": 0,
    "Partido C": 0,
    "Abstenções": 0
}

def dentro_do_horario():
    agora = datetime.now().time()
    return datetime.strptime("08:00", "%H:%M").time() <= agora <= datetime.strptime("20:00", "%H:%M").time()

@app.route("/", methods=["GET", "POST"])
def index():
    # Se usuário já votou, redireciona para resultado
    if session.get("ja_votou"):
        return redirect(url_for("resultado"))

    fora_do_horario = not dentro_do_horario()

    if request.method == "POST":
        voto = request.form.get("voto")
        if voto in votos:
            votos[voto] += 1
            session["ja_votou"] = True  # marca que votou
            return redirect(url_for("resultado"))

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>Votação</title></head>
    <body>
        <h1>Sistema de Votação</h1>

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
    """, fora_do_horario=fora_do_horario)

@app.route("/resultado")
def resultado():
    max_votos = max(votos["Partido A"], votos["Partido B"], votos["Partido C"])
    vencedores = [p for p in ["Partido A", "Partido B", "Partido C"] if votos[p] == max_votos and max_votos > 0]

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>Resultado da Votação</title></head>
    <body>
        <h1>Resultado Final</h1>
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
    """, votos=votos, vencedores=vencedores)

if __name__ == "__main__":
    app.run(debug=True)
