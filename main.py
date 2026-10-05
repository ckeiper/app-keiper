import os, time, sqlite3
from flask import Flask, request, redirect
import requests
from apscheduler.schedulers.background import BackgroundScheduler

CLIENT_ID = os.getenv("ML_CLIENT_ID")
CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ML_REDIRECT_URI")

AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

app = Flask(__name__)

def banco():
    conn = sqlite3.connect("app.db")
    conn.row_factory = sqlite3.Row
    return conn

def iniciar_banco():
    with banco() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conexoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT NOT NULL,
                user_id INTEGER,
                access_token TEXT,
                refresh_token TEXT,
                expires_at INTEGER,
                status TEXT DEFAULT 'ativa'
            )
        """)

@app.route("/")
def home():
    return """
    <h1>Conectar loja ao Mercado Livre</h1>
    <form action="/conectar" method="get">
        <label>Nome do cliente:</label>
        <input name="cliente" required>
        <button>Conectar</button>
    </form>
    """

@app.route("/conectar")
def conectar():
    cliente = request.args.get("cliente", "sem_nome")
    url = f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state={cliente}"
    return redirect(url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    cliente = request.args.get("state", "sem_nome")
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    })
    dados = resp.json()
    if "access_token" not in dados:
        return f"Erro ao conectar: {dados}"
    with banco() as conn:
        conn.execute("DELETE FROM conexoes WHERE cliente = ?", (cliente,))
        conn.execute("""
            INSERT INTO conexoes (cliente, user_id, access_token, refresh_token, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """, (cliente, dados.get("user_id"), dados["access_token"],
              dados["refresh_token"], int(time.time()) + dados["expires_in"]))
    return f"<h1>Loja de {cliente} conectada com sucesso!</h1>"

def renovar(refresh_token):
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
    })
    return resp.json()

def job_refresh():
    agora = int(time.time())
    with banco() as conn:
        conexoes = conn.execute(
            "SELECT * FROM conexoes WHERE status = 'ativa' AND expires_at < ?",
            (agora + 1800,)
        ).fetchall()
        for c in conexoes:
            try:
                dados = renovar(c["refresh_token"])
                conn.execute("""
                    UPDATE conexoes
                    SET access_token = ?, refresh_token = ?, expires_at = ?, status = 'ativa'
                    WHERE id = ?
                """, (dados["access_token"], dados["refresh_token"],
                      agora + dados["expires_in"], c["id"]))
            except Exception:
                conn.execute("UPDATE conexoes SET status = 'expirada' WHERE id = ?", (c["id"],))

@app.route("/status")
def status():
    with banco() as conn:
        linhas = conn.execute("SELECT cliente, user_id, status, expires_at FROM conexoes").fetchall()
    html = "<h1>Conexões</h1><table border=1><tr><th>Cliente</th><th>Loja</th><th>Status</th><th>Expira em</th></tr>"
    for l in linhas:
        quando = time.strftime("%d/%m/%Y %H:%M", time.localtime(l["expires_at"])) if l["expires_at"] else "-"
        html += f"<tr><td>{l['cliente']}</td><td>{l['user_id']}</td><td>{l['status']}</td><td>{quando}</td></tr>"
    html += "</table>"
    return html

iniciar_banco()

scheduler = BackgroundScheduler()
scheduler.add_job(job_refresh, "interval", minutes=30)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
