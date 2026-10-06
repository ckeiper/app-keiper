import os, time, sqlite3, html, json
from flask import Flask, request, redirect
import requests
from apscheduler.schedulers.background import BackgroundScheduler

CLIENT_ID = os.getenv("ML_CLIENT_ID")
CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ML_REDIRECT_URI")

API = "https://api.mercadolibre.com"
AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

app = Flask(__name__)
esc = html.escape

CSS = """
<style>
* { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',Arial,sans-serif; }
body { background:#f4f6f9; color:#1a1a2e; }
.top { background:#3483FA; color:#fff; padding:18px 32px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; }
.top h1 { font-size:22px; font-weight:700; }
.top .brand { font-size:14px; opacity:.9; }
.top a.btn { background:#FFE600; color:#1a1a2e; text-decoration:none; padding:9px 18px; border-radius:8px; font-weight:600; font-size:14px; }
.wrap { max-width:1200px; margin:28px auto; padding:0 20px; }
.card { background:#fff; border-radius:14px; box-shadow:0 2px 10px rgba(0,0,0,.06); padding:22px; margin-bottom:22px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }
.stat { background:#fff; border-radius:14px; box-shadow:0 2px 10px rgba(0,0,0,.06); padding:18px; border-left:4px solid #3483FA; }
.stat .num { font-size:26px; font-weight:700; color:#3483FA; }
.stat .lab { font-size:13px; color:#6b7280; margin-top:4px; }
table { width:100%; border-collapse:collapse; margin-top:12px; font-size:14px; }
th { background:#f0f4ff; color:#1a1a2e; text-align:left; padding:10px 12px; font-weight:600; }
td { padding:10px 12px; border-bottom:1px solid #eef1f5; }
tr:hover td { background:#fafbff; }
.tag { display:inline-block; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.tag.ativa { background:#e6f7ee; color:#1a9d5c; }
.tag.pausado { background:#fdeaea; color:#d64545; }
.tag.expirada { background:#fdeaea; color:#d64545; }
.tag.normal { background:#eef1f5; color:#6b7280; }
h2 { font-size:18px; color:#1a1a2e; margin-bottom:4px; }
.sub { color:#6b7280; font-size:13px; margin-bottom:14px; }
a.link { color:#3483FA; text-decoration:none; font-weight:600; }
a.link:hover { text-decoration:underline; }
.badge { background:#FFE600; color:#1a1a2e; border-radius:20px; padding:2px 10px; font-size:12px; font-weight:700; }
.empty { color:#6b7280; font-size:14px; padding:14px 0; }
.aviso { background:#fff7e0; border:1px solid #ffe28a; color:#8a6d00; border-radius:10px; padding:12px 16px; font-size:14px; margin-bottom:14px; }
.muted { color:#6b7280; font-size:12px; margin-top:14px; }
</style>
"""

def pagina(titulo, corpo):
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>" + esc(titulo) + "</title>" + CSS + "</head><body>"
            "<div class='top'><div><h1>Keiper Consultoria</h1>"
            "<div class='brand'>Painel de lojas Mercado Livre</div></div>"
            "<a class='btn' href='/'>+ Conectar loja</a></div>"
            "<div class='wrap'>" + corpo + "</div></body></html>")


def banco():
    conn = sqlite3.connect("app.db")
    conn.row_factory = sqlite3.Row
    return conn


def iniciar_banco():
    with banco() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS conexoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL,
            user_id INTEGER,
            access_token TEXT,
            refresh_token TEXT,
            expires_at INTEGER,
            status TEXT DEFAULT 'ativa'
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS dados_conta (
            conexao_id INTEGER PRIMARY KEY,
            user_id INTEGER, nickname TEXT, nome TEXT, sobrenome TEXT,
            reputacao TEXT, pontos INTEGER, atualizado_em INTEGER
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS anuncios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conexao_id INTEGER, item_id TEXT, titulo TEXT, preco REAL,
            quantidade INTEGER, status TEXT, vendidos INTEGER, atualizado_em INTEGER,
            UNIQUE(conexao_id, item_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conexao_id INTEGER, pedido_id TEXT, status TEXT,
            total REAL, moeda TEXT, fechado_em TEXT, atualizado_em INTEGER,
            UNIQUE(conexao_id, pedido_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS financeiro (
            conexao_id INTEGER PRIMARY KEY,
            saldo REAL, detalhe TEXT, atualizado_em INTEGER
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS metricas (
            conexao_id INTEGER, item_id TEXT, vendidos INTEGER,
            visitas INTEGER, conversao REAL, atualizado_em INTEGER,
            PRIMARY KEY (conexao_id, item_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS erros (
            conexao_id INTEGER, categoria TEXT, mensagem TEXT, quando INTEGER,
            PRIMARY KEY (conexao_id, categoria)
        )""")


# ---------- PÁGINAS ----------

@app.route("/")
def home():
    corpo = """
    <div class='card' style='max-width:520px;margin:40px auto;text-align:center'>
        <h2>Conectar loja ao Mercado Livre</h2>
        <div class='sub'>Digite o nome do cliente e clique em conectar</div>
        <form action='/conectar' method='get' style='margin-top:16px'>
            <input name='cliente' required placeholder='Nome do cliente'
              style='width:100%;padding:12px;border:1px solid #d5dbe5;border-radius:8px;font-size:15px;margin-bottom:12px'>
            <button style='width:100%;padding:13px;background:#3483FA;color:#fff;border:0;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer'>Conectar</button>
        </form>
        <p style='margin-top:16px'><a class='link' href='/painel'>Ver painel de lojas</a></p>
    </div>"""
    return pagina("Conectar loja", corpo)


@app.route("/conectar")
def conectar():
    cliente = request.args.get("cliente", "sem_nome")
    url = AUTH_URL + "?response_type=code&client_id=" + CLIENT_ID + "&redirect_uri=" + REDIRECT_URI + "&state=" + cliente
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
        return pagina("Erro", "<div class='card'><h2>Erro ao conectar</h2><p>" + esc(str(dados)) + "</p></div>")
    with banco() as conn:
        conn.execute("DELETE FROM conexoes WHERE cliente = ?", (cliente,))
        conn.execute("INSERT INTO conexoes (cliente, user_id, access_token, refresh_token, expires_at) VALUES (?, ?, ?, ?, ?)",
                     (cliente, dados.get("user_id"), dados["access_token"], dados["refresh_token"],
                      int(time.time()) + dados["expires_in"]))
    corpo = ("<div class='card' style='max-width:520px;margin:40px auto;text-align:center'>"
             "<h2>Loja de " + esc(cliente) + " conectada com sucesso!</h2>"
             "<div class='sub'>Os dados serão carregados automaticamente</div>"
             "<p style='margin-top:16px'><a class='link' href='/painel'>Ver painel</a></p></div>")
    return pagina("Conectado", corpo)


@app.route("/status")
def status():
    with banco() as conn:
        linhas = conn.execute("SELECT cliente, user_id, status, expires_at FROM conexoes").fetchall()
    linhas_html = ""
    for l in linhas:
        quando = time.strftime("%d/%m/%Y %H:%M", time.localtime(l["expires_at"])) if l["expires_at"] else "-"
        tag = "tag " + (l["status"] if l["status"] in ("ativa", "pausado", "expirada") else "normal")
        linhas_html += ("<tr><td>" + esc(str(l["cliente"])) + "</td><td>" + str(l["user_id"]) +
                        "</td><td><span class='" + tag + "'>" + esc(l["status"]) + "</span></td><td>" + quando + "</td></tr>")
    corpo = ("<div class='card'><h2>Conexões</h2><div class='sub'>Status de cada loja conectada</div>"
             "<table><thead><tr><th>Cliente</th><th>Loja</th><th>Status</th><th>Expira em</th></tr></thead>"
             "<tbody>" + linhas_html + "</tbody></table></div>")
    return pagina("Status", corpo)


@app.route("/painel")
def painel():
    with banco() as conn:
        linhas = conn.execute("""
            SELECT c.id, c.cliente, c.user_id, c.status,
              (SELECT COUNT(*) FROM anuncios a WHERE a.conexao_id=c.id) qtd_anuncios,
              (SELECT COUNT(*) FROM pedidos p WHERE p.conexao_id=c.id) qtd_pedidos,
              (SELECT saldo FROM financeiro f WHERE f.conexao_id=c.id) saldo
            FROM conexoes c ORDER BY c.id
        """).fetchall()
    if not linhas:
        corpo = ("<div class='card' style='text-align:center;padding:50px'>"
                 "<h2>Nenhuma loja conectada ainda</h2>"
                 "<div class='sub'>Comece conectando a primeira loja</div>"
                 "<p><a class='link' href='/'>Conectar loja</a></p></div>")
        return pagina("Painel", corpo)
    cards = ""
    for l in linhas:
        saldo_txt = ("R$ %.2f" % l["saldo"]) if l["saldo"] is not None else "-"
        tag = "tag " + (l["status"] if l["status"] in ("ativa", "pausado", "expirada") else "normal")
        cards += ("<div class='card'>"
                  "<div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px'>"
                  "<h2>" + esc(str(l["cliente"])) + "</h2>"
                  "<span class='" + tag + "'>" + esc(l["status"]) + "</span></div>"
                  "<div class='grid' style='margin-top:14px'>"
                  "<div class='stat'><div class='num'>" + str(l["qtd_anuncios"]) + "</div><div class='lab'>Anúncios</div></div>"
                  "<div class='stat'><div class='num'>" + str(l["qtd_pedidos"]) + "</div><div class='lab'>Pedidos</div></div>"
                  "<div class='stat'><div class='num'>" + saldo_txt + "</div><div class='lab'>Saldo</div></div>"
                  "</div>"
                  "<div style='margin-top:14px'><a class='link' href='/painel/" + str(l["id"]) + "'>Abrir detalhes</a>"
                  " &nbsp;·&nbsp; <a class='link' href='/atualizar?cid=" + str(l["id"]) + "'>Atualizar dados</a></div>"
                  "</div>")
    corpo = "<h2 style='margin-bottom:16px'>Lojas conectadas</h2>" + cards
    return pagina("Painel", corpo)


@app.route("/painel/<int:cid>")
def painel_detalhe(cid):
    with banco() as conn:
        c = conn.execute("SELECT * FROM conexoes WHERE id=?", (cid,)).fetchone()
        conta = conn.execute("SELECT * FROM dados_conta WHERE conexao_id=?", (cid,)).fetchone()
        fin = conn.execute("SELECT * FROM financeiro WHERE conexao_id=?", (cid,)).fetchone()
        anuncios = conn.execute("SELECT * FROM anuncios WHERE conexao_id=? ORDER BY vendidos DESC LIMIT 100", (cid,)).fetchall()
        pedidos = conn.execute("SELECT * FROM pedidos WHERE conexao_id=? ORDER BY fechado_em DESC LIMIT 100", (cid,)).fetchall()
        metricas = conn.execute("""
            SELECT a.titulo, m.vendidos, m.visitas, m.conversao
            FROM metricas m LEFT JOIN anuncios a ON a.conexao_id=m.conexao_id AND a.item_id=m.item_id
            WHERE m.conexao_id=? ORDER BY m.vendidos DESC LIMIT 100
        """, (cid,)).fetchall()
        erros = conn.execute("SELECT * FROM erros WHERE conexao_id=?", (cid,)).fetchall()
    if not c:
        return pagina("Não encontrada", "<div class='card'><h2>Loja não encontrada</h2></div>")

    corpo = ("<div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:18px'>"
             "<h2>" + esc(str(c["cliente"])) + "</h2>"
             "<div><a class='link' href='/painel'>← Voltar</a> &nbsp;·&nbsp; "
             "<a class='link' href='/atualizar?cid=" + str(cid) + "'>Atualizar agora</a></div></div>")

    if conta:
        corpo += ("<div class='card'><h2>Conta</h2><div class='sub'>Informações do vendedor</div>"
                  "<div class='grid'>"
                  "<div class='stat'><div class='num'>" + esc(str(conta["nickname"])) + "</div><div class='lab'>Nickname</div></div>"
                  "<div class='stat'><div class='num'>" + esc(str(conta["nome"])) + " " + esc(str(conta["sobrenome"])) + "</div><div class='lab'>Nome</div></div>"
                  "<div class='stat'><div class='num'>" + esc(str(conta["reputacao"])) + "</div><div class='lab'>Reputação</div></div>"
                  "<div class='stat'><div class='num'>" + str(conta["pontos"]) + "</div><div class='lab'>Vendas concluídas</div></div>"
                  "</div></div>")

    if fin:
        saldo_txt = ("R$ %.2f" % fin["saldo"]) if fin["saldo"] is not None else "-"
        corpo += ("<div class='card'><h2>Financeiro</h2><div class='sub'>Saldo disponível na conta</div>"
                  "<div class='grid'><div class='stat'><div class='num'>" + saldo_txt + "</div><div class='lab'>Saldo</div></div></div>"
                  "</div>")

    if anuncios:
        linhas_html = ""
        for a in anuncios:
            tag = "tag " + (a["status"] if a["status"] in ("ativa", "pausado", "expirada") else "normal")
            linhas_html += ("<tr><td>" + esc(str(a["titulo"])) + "</td><td>R$ %.2f" % (a["preco"] or 0) +
                            "</td><td>" + str(a["quantidade"]) + "</td><td><span class='" + tag + "'>" + esc(str(a["status"])) +
                            "</span></td><td>" + str(a["vendidos"]) + "</td></tr>")
        corpo += ("<div class='card'><h2>Anúncios <span class='badge'>" + str(len(anuncios)) + "</span></h2>"
                  "<div class='sub'>Produtos da loja</div>"
                  "<table><thead><tr><th>Título</th><th>Preço</th><th>Estoque</th><th>Status</th><th>Vendidos</th></tr></thead>"
                  "<tbody>" + linhas_html + "</tbody></table></div>")

    if metricas:
        linhas_html = ""
        for m in metricas:
            conv_txt = ("%.2f%%" % m["conversao"]) if m["conversao"] is not None else "-"
            linhas_html += ("<tr><td>" + esc(str(m["titulo"]) or "-") + "</td><td>" + str(m["vendidos"]) +
                            "</td><td>" + str(m["visitas"]) + "</td><td>" + conv_txt + "</td></tr>")
        corpo += ("<div class='card'><h2>Métricas <span class='badge'>" + str(len(metricas)) + "</span></h2>"
                  "<div class='sub'>Visitas, vendidos e conversão por anúncio</div>"
                  "<table><thead><tr><th>Anúncio</th><th>Vendidos</th><th>Visitas</th><th>Conversão</th></tr></thead>"
                  "<tbody>" + linhas_html + "</tbody></table></div>")

    if pedidos:
        linhas_html = ""
        for p in pedidos:
            total_txt = ("R$ %.2f" % p["total"]) if p["total"] is not None else "-"
            linhas_html += ("<tr><td>" + str(p["pedido_id"]) + "</td><td>" + esc(str(p["status"])) +
                            "</td><td>" + total_txt + "</td><td>" + esc(str(p["fechado_em"])) + "</td></tr>")
        corpo += ("<div class='card'><h2>Pedidos <span class='badge'>" + str(len(pedidos)) + "</span></h2>"
                  "<div class='sub'>Últimas vendas</div>"
                  "<table><thead><tr><th>Pedido</th><th>Status</th><th>Total</th><th>Data</th></tr></thead>"
                  "<tbody>" + linhas_html + "</tbody></table></div>")

    if erros:
        avisos = ""
        for e in erros:
            avisos += "<div>" + esc(e["categoria"]) + ": " + esc(e["mensagem"]) + "</div>"
        corpo += "<div class='aviso'><b>Avisos:</b> " + avisos + "</div>"

    corpo += "<div class='muted'>Os dados são atualizados automaticamente a cada hora.</div>"
    return pagina("Painel de " + str(c["cliente"]), corpo)


@app.route("/atualizar")
def atualizar():
    cid = request.args.get("cid", type=int)
    with banco() as conn:
        if cid:
            c = conn.execute("SELECT * FROM conexoes WHERE id=?", (cid,)).fetchone()
        else:
            c = conn.execute("SELECT * FROM conexoes WHERE status='ativa' ORDER BY id LIMIT 1").fetchone()
    if not c:
        return pagina("Sem loja", "<div class='card'><h2>Nenhuma loja conectada</h2><p><a class='link' href='/'>Conectar</a></p></div>")
    token = token_atual(c)
    if not token:
        return pagina("Erro", "<div class='card'><h2>Falha ao renovar o token</h2><p>Tente conectar a loja novamente.</p></div>")
    user_id = c["user_id"]
    puxar_conta(c["id"], token)
    if user_id:
        puxar_anuncios(c["id"], token, user_id)
        puxar_pedidos(c["id"], token, user_id)
        puxar_financeiro(c["id"], token, user_id)
        puxar_metricas(c["id"], token)
    if cid:
        return redirect("/painel/" + str(cid))
    return redirect("/painel")


# ---------- CONEXÃO / TOKENS ----------

def renovar(refresh_token):
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
    })
    return resp.json()


def token_atual(c):
    agora = int(time.time())
    if c["expires_at"] and c["expires_at"] > agora + 600:
        return c["access_token"]
    dados = renovar(c["refresh_token"])
    if "access_token" not in dados:
        registrar_erro(c["id"], "token", str(dados)[:200])
        return None
    with banco() as conn:
        conn.execute("UPDATE conexoes SET access_token=?, refresh_token=?, expires_at=?, status='ativa' WHERE id=?",
                     (dados["access_token"], dados["refresh_token"], agora + dados["expires_in"], c["id"]))
    return dados["access_token"]


def job_refresh():
    agora = int(time.time())
    with banco() as conn:
        conexoes = conn.execute("SELECT * FROM conexoes WHERE status='ativa' AND expires_at < ?",
                                (agora + 1800,)).fetchall()
        for c in conexoes:
            try:
                dados = renovar(c["refresh_token"])
                conn.execute("UPDATE conexoes SET access_token=?, refresh_token=?, expires_at=?, status='ativa' WHERE id=?",
                             (dados["access_token"], dados["refresh_token"], agora + dados["expires_in"], c["id"]))
            except Exception:
                conn.execute("UPDATE conexoes SET status='expirada' WHERE id=?", (c["id"],))


# ---------- PUXAR DADOS ----------

def api_get(token, path, params=None):
    try:
        r = requests.get(API + path, headers={"Authorization": "Bearer " + (token or "")},
                         params=params, timeout=25)
        if r.status_code == 200:
            return r.json(), None
        return None, "HTTP " + str(r.status_code) + ": " + r.text[:180]
    except Exception as e:
        return None, str(e)


def registrar_erro(conexao_id, categoria, mensagem):
    with banco() as conn:
        conn.execute("""INSERT INTO erros (conexao_id, categoria, mensagem, quando)
                        VALUES (?,?,?,?)
                        ON CONFLICT(conexao_id, categoria)
                        DO UPDATE SET mensagem=excluded.mensagem, quando=excluded.quando""",
                     (conexao_id, categoria, (mensagem or "")[:300], int(time.time())))


def puxar_conta(conexao_id, token):
    dados, erro = api_get(token, "/users/me")
    if erro or not dados:
        registrar_erro(conexao_id, "conta", erro or "sem resposta")
        return
    rep = dados.get("seller_reputation") or {}
    metricas = rep.get("metrics") or {}
    sales = metricas.get("sales") or {}
    pontos = sales.get("completed") or rep.get("transactions_completed")
    with banco() as conn:
        conn.execute("""INSERT INTO dados_conta (conexao_id, user_id, nickname, nome, sobrenome, reputacao, pontos, atualizado_em)
                        VALUES (?,?,?,?,?,?,?,?)
                        ON CONFLICT(conexao_id) DO UPDATE SET
                          user_id=excluded.user_id, nickname=excluded.nickname, nome=excluded.nome,
                          sobrenome=excluded.sobrenome, reputacao=excluded.reputacao,
                          pontos=excluded.pontos, atualizado_em=excluded.atualizado_em""",
                     (conexao_id, dados.get("id"), dados.get("nickname"), dados.get("first_name"),
                      dados.get("last_name"), rep.get("level_id"), pontos, int(time.time())))


def puxar_anuncios(conexao_id, token, user_id):
    ids = []
    offset = 0
    total = 50
    while offset < 200 and offset <= total:
        dados, erro = api_get(token, "/users/" + str(user_id) + "/items/search",
                              {"limit": 50, "offset": offset})
        if erro or not dados:
            registrar_erro(conexao_id, "anuncios", erro or "sem resposta")
            break
        resultados = dados.get("results") or []
        ids.extend(resultados)
        total = (dados.get("paging") or {}).get("total") or len(resultados)
        offset += len(resultados)
        if len(resultados) < 50:
            break
    agora = int(time.time())
    with banco() as conn:
        conn.execute("DELETE FROM anuncios WHERE conexao_id=?", (conexao_id,))
    for item_id in ids:
        det, det_erro = api_get(token, "/items/" + str(item_id),
                                {"attributes": "id,title,price,available_quantity,status,sold_quantity"})
        if det_erro or not det:
            continue
        with banco() as conn:
            conn.execute("""INSERT OR REPLACE INTO anuncios
                            (conexao_id, item_id, titulo, preco, quantidade, status, vendidos, atualizado_em)
                            VALUES (?,?,?,?,?,?,?,?)""",
                         (conexao_id, det.get("id"), det.get("title"), det.get("price"),
                          det.get("available_quantity"), det.get("status"), det.get("sold_quantity"), agora))


def puxar_metricas(conexao_id, token):
    with banco() as conn:
        linhas = conn.execute(
            "SELECT item_id, vendidos FROM anuncios WHERE conexao_id=?",
            (conexao_id,)).fetchall()
    itens = [l["item_id"] for l in linhas]
    if not itens:
        return
    vendidos_por_item = {l["item_id"]: (l["vendidos"] or 0) for l in linhas}
    agora = int(time.time())
    total_puxado = 0
    for i in range(0, len(itens), 100):
        lote = itens[i:i + 100]
        dados, erro = api_get(token, "/visits/items", {"ids": ",".join(lote)})
        if erro or not isinstance(dados, dict):
            registrar_erro(conexao_id, "metricas", erro or "sem resposta")
            continue
        for item_id in lote:
            v = dados.get(item_id)
            if isinstance(v, dict):
                visitas = v.get("total_visits") or 0
            elif isinstance(v, (int, float)):
                visitas = v
            else:
                continue
            vendidos = vendidos_por_item.get(item_id) or 0
            conversao = round((vendidos * 100.0 / visitas), 2) if visitas else 0
            with banco() as conn:
                conn.execute("""INSERT OR REPLACE INTO metricas
                                (conexao_id, item_id, vendidos, visitas, conversao, atualizado_em)
                                VALUES (?,?,?,?,?,?)""",
                             (conexao_id, item_id, vendidos, visitas, conversao, agora))
            total_puxado += 1
    if total_puxado == 0:
        registrar_erro(conexao_id, "metricas", "nenhum dado de visita retornado")


def puxar_pedidos(conexao_id, token, user_id):
    lista = []
    offset = 0
    total = 50
    agora = int(time.time())
    while offset < 300 and offset <= total:
        dados, erro = api_get(token, "/orders/search",
                              {"seller": user_id, "sort": "date_desc", "limit": 50, "offset": offset})
        if erro or not dados:
            registrar_erro(conexao_id, "pedidos", erro or "sem resposta")
            break
        resultados = dados.get("results") or []
        for o in resultados:
            lista.append((conexao_id, str(o.get("id")), o.get("status"), o.get("total_amount"),
                          o.get("currency_id"), o.get("date_closed") or o.get("date_created"), agora))
        total = (dados.get("paging") or {}).get("total") or len(resultados)
        offset += len(resultados)
        if len(resultados) < 50:
            break
    with banco() as conn:
        conn.execute("DELETE FROM pedidos WHERE conexao_id=?", (conexao_id,))
        conn.executemany("""INSERT OR REPLACE INTO pedidos
                            (conexao_id, pedido_id, status, total, moeda, fechado_em, atualizado_em)
                            VALUES (?,?,?,?,?,?,?)""", lista)


def puxar_financeiro(conexao_id, token, user_id):
    dados, erro = api_get(token, "/v1/balance", {"user_id": user_id})
    if erro or not dados:
        registrar_erro(conexao_id, "financeiro", erro or "sem resposta")
        return
    saldo = dados.get("available_balance") or dados.get("balance")
    detalhe = json.dumps(dados, ensure_ascii=False)[:2000]
    with banco() as conn:
        conn.execute("""INSERT OR REPLACE INTO financeiro (conexao_id, saldo, detalhe, atualizado_em)
                        VALUES (?,?,?,?)""",
                     (conexao_id, saldo, detalhe, int(time.time())))


def job_dados():
    with banco() as conn:
        conexoes = conn.execute("SELECT * FROM conexoes WHERE status='ativa'").fetchall()
    for c in conexoes:
        token = token_atual(c)
        if not token:
            continue
        puxar_conta(c["id"], token)
        if c["user_id"]:
            puxar_anuncios(c["id"], token, c["user_id"])
            puxar_pedidos(c["id"], token, c["user_id"])
            puxar_financeiro(c["id"], token, c["user_id"])
            puxar_metricas(c["id"], token)


iniciar_banco()

scheduler = BackgroundScheduler()
scheduler.add_job(job_refresh, "interval", minutes=30)
scheduler.add_job(job_dados, "interval", minutes=60)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
