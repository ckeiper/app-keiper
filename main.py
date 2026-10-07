import os, time, html, json, datetime, csv, io
from flask import Flask, request, redirect, jsonify, Response
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from apscheduler.schedulers.background import BackgroundScheduler

CLIENT_ID = os.getenv("ML_CLIENT_ID")
CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ML_REDIRECT_URI")
DATABASE_URL = os.getenv("DATABASE_URL")

API = "https://api.mercadolibre.com"
AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

app = Flask(__name__)
esc = html.escape

FRETE_PRECO_BANDAS = [
    (0, 18.99), (19, 48.99), (49, 78.99), (79, 99.99),
    (100, 119.99), (120, 149.99), (150, 199.99), (200, 10**9)
]
FRETE_PESO_BANDAS = [
    (0, 0.3), (0.3, 0.5), (0.5, 1), (1, 1.5), (1.5, 2), (2, 3), (3, 4), (4, 5),
    (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11), (11, 13), (13, 15),
    (15, 17), (17, 20), (20, 25), (25, 30), (30, 40), (40, 50), (50, 60),
    (60, 70), (70, 80), (80, 90), (90, 100), (100, 125), (125, 150), (150, 10**9)
]
FRETE_TABELA = [
    [5.65, 6.85, 8.15, 12.95, 14.95, 16.95, 19.05, 21.65],
    [5.95, 6.95, 8.25, 13.85, 16.15, 18.15, 20.45, 23.25],
    [6.05, 7.15, 8.45, 14.45, 16.85, 19.05, 21.35, 24.45],
    [6.15, 7.35, 8.65, 14.75, 17.15, 19.45, 21.75, 25.45],
    [6.25, 7.45, 8.75, 15.05, 17.65, 19.85, 22.25, 25.55],
    [6.35, 8.65, 9.15, 16.45, 19.15, 21.65, 24.35, 27.05],
    [6.45, 8.75, 9.75, 17.85, 20.75, 23.35, 26.35, 29.25],
    [6.55, 8.85, 10.25, 19.75, 22.85, 26.05, 29.25, 32.45],
    [6.65, 8.95, 10.35, 25.95, 29.15, 33.35, 36.45, 40.85],
    [6.75, 9.05, 10.45, 27.55, 31.65, 36.75, 40.85, 45.25],
    [6.85, 9.25, 10.55, 29.45, 34.35, 39.25, 44.15, 49.35],
    [6.95, 9.35, 10.65, 30.25, 35.25, 40.35, 45.35, 50.75],
    [7.05, 9.45, 10.85, 38.25, 45.05, 51.95, 58.75, 65.85],
    [7.05, 9.65, 11.05, 41.65, 48.55, 55.45, 62.35, 69.35],
    [7.15, 10.05, 11.45, 42.55, 49.75, 56.85, 63.85, 70.95],
    [7.25, 10.25, 11.65, 45.55, 52.95, 60.55, 68.15, 75.65],
    [7.35, 10.45, 11.85, 48.95, 56.55, 64.05, 71.35, 79.35],
    [7.45, 10.65, 12.05, 55.15, 64.35, 73.55, 82.75, 91.95],
    [7.65, 11.05, 12.25, 64.55, 75.75, 85.45, 96.25, 106.85],
    [7.75, 11.25, 12.45, 66.45, 76.05, 86.25, 97.15, 107.85],
    [7.85, 11.45, 12.65, 68.35, 79.65, 89.75, 100.05, 107.95],
    [7.95, 11.65, 12.85, 70.95, 81.85, 92.85, 103.45, 111.65],
    [8.05, 11.85, 13.05, 75.55, 87.25, 99.05, 110.25, 119.05],
    [8.15, 12.05, 13.25, 80.95, 93.75, 105.95, 118.05, 127.45],
    [8.25, 12.25, 13.45, 84.65, 97.95, 110.75, 123.35, 133.15],
    [8.35, 12.45, 13.65, 94.05, 108.35, 122.95, 136.95, 147.85],
    [8.45, 12.65, 13.85, 107.45, 124.85, 140.45, 156.45, 168.85],
    [8.55, 12.85, 14.05, 120.15, 138.95, 156.95, 174.85, 188.85],
    [8.65, 12.85, 14.25, 127.45, 147.05, 166.55, 185.55, 200.35],
    [8.75, 12.85, 14.45, 167.05, 193.35, 218.45, 243.45, 262.85],
]

def frete_esperado(preco, peso_kg):
    if preco is None or peso_kg is None or peso_kg <= 0:
        return None
    if preco < 19:
        return round(min(preco / 2.0, 5.65), 2)
    col = None
    for i, (lo, hi) in enumerate(FRETE_PRECO_BANDAS):
        if lo <= preco < hi:
            col = i
            break
    if col is None:
        col = len(FRETE_PRECO_BANDAS) - 1
    linha = None
    for i, (lo, hi) in enumerate(FRETE_PESO_BANDAS):
        if lo <= peso_kg < hi:
            linha = i
            break
    if linha is None:
        linha = len(FRETE_PESO_BANDAS) - 1
    return FRETE_TABELA[linha][col]


TAGS_BOAS = {"good_quality_picture", "real_size", "immediate_delivery", "catalog_product",
             "good_quality_thumbnail", "fast_shipping", "free_shipping", "brand_quality"}
TAGS_RUINS = {"dragged_bids", "poor_quality_picture", "out_of_stock", "under_review",
              "suspended", "no_picture", "real_size_mismatch", "loses_rank", "low_quality"}


def montar_demandas_anuncio(a, em_promocao, conversao):
    demandas = []
    qtd = a["quantidade"] or 0
    fotos = a["fotos"] or 0
    if qtd <= 0:
        demandas.append(("Repor estoque (está zerado)", "urgente"))
    elif qtd < 5:
        demandas.append(("Repor estoque (baixo: " + str(qtd) + ")", "atencao"))
    if fotos <= 0:
        demandas.append(("Adicionar fotos (está sem nenhuma)", "urgente"))
    elif fotos < 10:
        demandas.append(("Adicionar " + str(10 - fotos) + " fotos (ideal 10)", "atencao"))
    clips = a["clips"]
    if clips is None:
        demandas.append(("Verificar se tem vídeo (clips não confirmado)", "atencao"))
    elif clips < 2:
        demandas.append(("Adicionar vídeo/clip (ideal 2)", "atencao"))
    tags = []
    try:
        tags = json.loads(a["tags"]) if a["tags"] else []
    except Exception:
        tags = []
    for t in tags:
        if t in TAGS_RUINS:
            demandas.append(("Resolver tag ruim: " + t, "urgente"))
    st = str(a["status"])
    if st not in ("active", "ACTIVE"):
        demandas.append(("Reativar anúncio (status: " + st + ")", "urgente"))
    if conversao is not None and conversao < 5 and (a.get("visitas") or 0) > 0:
        demandas.append(("Melhorar conversão (%.2f%% com %d visitas) — revise preço, título e fotos" % (conversao, a.get("visitas") or 0), "atencao"))
    return demandas


CSS = """
<style>
* { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',Arial,sans-serif; }
body { background:#f4f6f9; color:#1a1a2e; }
.top { background:#3483FA; color:#fff; padding:18px 32px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; }
.top h1 { font-size:22px; font-weight:700; }
.top .brand { font-size:14px; opacity:.9; }
.top a.btn { background:#FFE600; color:#1a1a2e; text-decoration:none; padding:9px 18px; border-radius:8px; font-weight:600; font-size:14px; }
.wrap { max-width:1300px; margin:28px auto; padding:0 20px; }
.card { background:#fff; border-radius:14px; box-shadow:0 2px 10px rgba(0,0,0,.06); padding:22px; margin-bottom:22px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }
.stat { background:#fff; border-radius:14px; box-shadow:0 2px 10px rgba(0,0,0,.06); padding:18px; border-left:4px solid #3483FA; }
.stat .num { font-size:26px; font-weight:700; color:#3483FA; }
.stat .lab { font-size:13px; color:#6b7280; margin-top:4px; }
table { width:100%; border-collapse:collapse; margin-top:12px; font-size:13.5px; }
th { background:#f0f4ff; color:#1a1a2e; text-align:left; padding:10px 12px; font-weight:600; white-space:nowrap; }
td { padding:9px 12px; border-bottom:1px solid #eef1f5; vertical-align:top; }
tr:hover td { background:#fafbff; }
.tag { display:inline-block; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.tag.ativa { background:#e6f7ee; color:#1a9d5c; }
.tag.pausado { background:#fdeaea; color:#d64545; }
.tag.expirada { background:#fdeaea; color:#d64545; }
.tag.normal { background:#eef1f5; color:#6b7280; }
.tag.respondida { background:#e6f7ee; color:#1a9d5c; }
.tag.pendente { background:#fff7e0; color:#8a6d00; }
.tag.boa { background:#e6f7ee; color:#1a9d5c; }
.tag.ruim { background:#fdeaea; color:#d64545; }
.tag.promocao { background:#FFE600; color:#1a1a2e; }
.tag.sem { background:#eef1f5; color:#9aa1ad; }
.alerta { padding:2px 8px; border-radius:6px; font-size:12px; font-weight:600; }
.alerta.urgente { background:#fdeaea; color:#d64545; }
.alerta.atencao { background:#fff7e0; color:#8a6d00; }
.alerta.ok { background:#e6f7ee; color:#1a9d5c; }
.alerta.subiu { background:#e6f7ee; color:#1a9d5c; }
.alerta.caiu { background:#fdeaea; color:#d64545; }
.alerta.estavel { background:#eef1f5; color:#6b7280; }
h2 { font-size:18px; color:#1a1a2e; margin-bottom:4px; }
.sub { color:#6b7280; font-size:13px; margin-bottom:14px; }
a.link { color:#3483FA; text-decoration:none; font-weight:600; }
a.link:hover { text-decoration:underline; }
.icon-link { text-decoration:none; font-size:16px; margin-left:6px; }
.input-inline { width:220px; max-width:60%; padding:6px 10px; border:1px solid #d5dbe5; border-radius:6px; font-size:15px; }
.btn-pequeno { background:#3483FA; color:#fff; border:0; border-radius:6px; padding:7px 14px; font-size:13px; font-weight:600; cursor:pointer; margin-left:6px; }
.badge { background:#FFE600; color:#1a1a2e; border-radius:20px; padding:2px 10px; font-size:12px; font-weight:700; }
.aviso { background:#fff7e0; border:1px solid #ffe28a; color:#8a6d00; border-radius:10px; padding:12px 16px; font-size:14px; margin-bottom:14px; }
.muted { color:#6b7280; font-size:12px; margin-top:14px; }
.btn-danger { display:inline-block; background:#d64545; color:#fff; text-decoration:none; padding:6px 14px; border-radius:8px; font-size:13px; font-weight:600; }
.btn-danger:hover { background:#b93a3a; }
.btn-salvar { background:#3483FA; color:#fff; border:0; border-radius:8px; padding:12px 20px; font-size:15px; font-weight:600; cursor:pointer; }
.btn-acoes { display:inline-block; background:#3483FA; color:#fff; text-decoration:none; padding:9px 16px; border-radius:8px; font-size:13px; font-weight:600; margin-right:8px; }
.btn-acoes:hover { background:#2a6fd6; }
.btn-acoes.verde { background:#1a9d5c; }
.btn-acoes.verde:hover { background:#15804a; }
.btn-acoes.laranja { background:#f59e0b; }
.btn-acoes.laranja:hover { background:#d97706; }
.btn-acoes.cinza { background:#6b7280; }
.btn-acoes.cinza:hover { background:#4b5563; }
.btn-acoes.rosa { background:#ec4899; }
.btn-acoes.rosa:hover { background:#db2777; }
.input { width:100%; padding:12px; border:1px solid #d5dbe5; border-radius:8px; font-size:15px; margin-bottom:12px; }
.filtro { display:inline-block; padding:6px 12px; border:1px solid #d5dbe5; border-radius:6px; font-size:13px; margin-right:8px; margin-bottom:8px; }
.filtro-btn { background:#3483FA; color:#fff; border:0; border-radius:6px; padding:7px 16px; font-size:13px; font-weight:600; cursor:pointer; }
.grafico-box { position:relative; height:340px; width:100%; }
.insight { display:flex; align-items:flex-start; gap:10px; padding:10px 0; border-bottom:1px solid #eef1f5; font-size:14px; }
.insight:last-child { border-bottom:0; }
.insight .icone { font-size:18px; }
.sugestao { background:#f0f6ff; border-left:4px solid #3483FA; border-radius:8px; padding:12px 14px; margin-top:10px; font-size:14px; color:#1a1a2e; }
.demanda-item { border:1px solid #eef1f5; border-radius:10px; padding:14px 16px; margin-bottom:12px; }
.demanda-item.urgente { border-left:4px solid #d64545; }
.demanda-item.atencao { border-left:4px solid #f59e0b; }
.demanda-item .titulo { font-size:15px; font-weight:700; margin-bottom:6px; }
.demanda-item .acao { padding:4px 0; font-size:13.5px; }
.demanda-item .acao.urgente { color:#d64545; }
.demanda-item .acao.atencao { color:#b45309; }
.promo-item { border:1px solid #eef1f5; border-radius:10px; padding:14px 16px; margin-bottom:12px; }
.promo-item.ativa { border-left:4px solid #1a9d5c; }
.promo-item.candidata { border-left:4px solid #f59e0b; }
.promo-item.finalizada { border-left:4px solid #9aa1ad; }
.promo-item .titulo { font-size:15px; font-weight:700; margin-bottom:6px; }
.promo-item .meta { font-size:12.5px; color:#6b7280; margin-bottom:8px; }
.promo-item table { margin-top:6px; }
@media print { .top, .no-print, .btn-acoes { display:none !important; } body { background:#fff; } }
</style>
"""

SCRIPT = """
<script>
function editarNome(id){
  var span = document.getElementById('nome-' + id);
  if (!span || span.querySelector('input')) { return; }
  var atual = span.textContent.trim();
  var caixa = span.parentNode;
  var input = document.createElement('input');
  input.value = atual;
  input.className = 'input-inline';
  input.maxLength = 120;
  var btn = document.createElement('button');
  btn.textContent = 'Salvar';
  btn.className = 'btn-pequeno';
  span.style.display = 'none';
  caixa.appendChild(input);
  caixa.appendChild(btn);
  input.focus();
  function salvar(){
    var novo = input.value.trim();
    if (!novo) { alert('O nome não pode ficar vazio.'); return; }
    fetch('/renomear/' + id, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: 'cliente=' + encodeURIComponent(novo)
    }).then(function(r){ return r.json(); }).then(function(d){
      if (d.ok) {
        span.textContent = novo;
        span.style.display = '';
        input.remove();
        btn.remove();
      } else { alert('Não foi possível salvar. Tente de novo.'); }
    }).catch(function(){ alert('Erro ao salvar. Tente de novo.'); });
  }
  btn.onclick = salvar;
  input.addEventListener('keydown', function(e){
    if (e.key === 'Enter') { salvar(); }
    if (e.key === 'Escape') { span.style.display = ''; input.remove(); btn.remove(); }
  });
}
function editarCusto(cid, itemId){
  var span = document.getElementById('custo-' + cid + '-' + itemId);
  if (!span || span.querySelector('input')) { return; }
  var atual = span.textContent.trim().replace('R$','').trim();
  var caixa = span.parentNode;
  var input = document.createElement('input');
  input.value = atual;
  input.className = 'input-inline';
  input.type = 'number';
  input.step = '0.01';
  input.style.width = '90px';
  var btn = document.createElement('button');
  btn.textContent = 'OK';
  btn.className = 'btn-pequeno';
  span.style.display = 'none';
  caixa.appendChild(input);
  caixa.appendChild(btn);
  input.focus();
  function salvar(){
    var novo = parseFloat(input.value.replace(',','.'));
    if (isNaN(novo) || novo < 0) { alert('Digite um custo válido.'); return; }
    fetch('/salvar_custo/' + cid + '/' + itemId, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: 'custo=' + novo
    }).then(function(r){ return r.json(); }).then(function(d){
      if (d.ok) {
        span.textContent = 'R$ ' + novo.toFixed(2);
        span.style.display = '';
        input.remove();
        btn.remove();
      } else { alert('Não foi possível salvar.'); }
    }).catch(function(){ alert('Erro ao salvar.'); });
  }
  btn.onclick = salvar;
  input.addEventListener('keydown', function(e){
    if (e.key === 'Enter') { salvar(); }
    if (e.key === 'Escape') { span.style.display = ''; input.remove(); btn.remove(); }
  });
}
</script>
"""

def pagina(titulo, corpo):
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>" + esc(titulo) + "</title>" + CSS + "</head><body>"
            "<h1>Keiper Consultoria</h1>"
            "Painel de lojas Mercado Livre



"
            "<a class='btn' href='/'>+ Conectar loja</a>

"
            "" + corpo + "

" + SCRIPT + "</body></html>")


def banco():
    return psycopg2.connect(DATABASE_URL)


def consultar(conn, sql, params=None):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params or ())
    return cur.fetchall()


def executar(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or ())
    return cur


def iniciar_banco():
    with banco() as conn:
        executar(conn, """CREATE TABLE IF NOT EXISTS conexoes (
            id SERIAL PRIMARY KEY,
            cliente TEXT NOT NULL,
            user_id BIGINT,
            access_token TEXT,
            refresh_token TEXT,
            expires_at BIGINT,
            status TEXT DEFAULT 'ativa'
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS dados_conta (
            conexao_id INTEGER PRIMARY KEY,
            user_id BIGINT, nickname TEXT, nome TEXT, sobrenome TEXT,
            reputacao TEXT, pontos INTEGER, atualizado_em BIGINT
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS anuncios (
            id SERIAL PRIMARY KEY,
            conexao_id INTEGER, item_id TEXT, titulo TEXT, preco REAL,
            quantidade INTEGER, status TEXT, vendidos INTEGER, atualizado_em BIGINT,
            fotos INTEGER DEFAULT 0, clips INTEGER DEFAULT 0, tags TEXT, peso REAL,
            custo REAL,
            UNIQUE(conexao_id, item_id)
        )""")
        try:
            executar(conn, "ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS fotos INTEGER DEFAULT 0")
            executar(conn, "ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS clips INTEGER DEFAULT 0")
            executar(conn, "ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS tags TEXT")
            executar(conn, "ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS peso REAL")
            executar(conn, "ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS custo REAL")
        except Exception:
            pass
        executar(conn, """CREATE TABLE IF NOT EXISTS pedidos (
            id SERIAL PRIMARY KEY,
            conexao_id INTEGER, pedido_id TEXT, status TEXT,
            total REAL, moeda TEXT, fechado_em TEXT, atualizado_em BIGINT,
            UNIQUE(conexao_id, pedido_id)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS metricas (
            conexao_id INTEGER, item_id TEXT, vendidos INTEGER,
            visitas INTEGER, conversao REAL, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, item_id)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS desempenho_historico (
            conexao_id INTEGER, item_id TEXT, data TEXT,
            visitas INTEGER DEFAULT 0, vendidos INTEGER DEFAULT 0, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, item_id, data)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS perguntas (
            conexao_id INTEGER, pergunta_id TEXT, item_id TEXT, texto TEXT,
            status TEXT, resposta TEXT, data TEXT, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, pergunta_id)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS envios (
            conexao_id INTEGER, envio_id TEXT, status TEXT, tracking TEXT,
            pedido_id TEXT, data TEXT, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, envio_id)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS promocoes (
            conexao_id INTEGER, promocao_id TEXT, tipo TEXT, nome TEXT,
            status TEXT, inicio TEXT, fim TEXT, qtd_itens INTEGER, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, promocao_id)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS promocoes_itens (
            conexao_id INTEGER, item_id TEXT, promocao_id TEXT,
            preco_promocional REAL, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, item_id, promocao_id)
        )""")
        try:
            executar(conn, "ALTER TABLE promocoes_itens ADD COLUMN IF NOT EXISTS preco_promocional REAL")
        except Exception:
            pass
        executar(conn, """CREATE TABLE IF NOT EXISTS ads_campanhas (
            conexao_id INTEGER, campanha_id TEXT, nome TEXT, status TEXT,
            tipo TEXT, data_inicio TEXT, data_fim TEXT, orcamento REAL, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, campanha_id)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS ads_metricas (
            conexao_id INTEGER, ad_id TEXT, campanha_id TEXT, item_id TEXT,
            impressoes INTEGER, cliques INTEGER, ctr REAL, gasto REAL, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, ad_id)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS erros (
            conexao_id INTEGER, categoria TEXT, mensagem TEXT, quando BIGINT,
            PRIMARY KEY (conexao_id, categoria)
        )""")


# ---------- PÁGINAS ----------

@app.route("/")
def home():
    corpo = """
    
        <h2>Conectar loja ao Mercado Livre</h2>
        Digite o nome do cliente e clique em conectar


        <form action='/conectar' method='get' style='margin-top:16px'>
            <input name='cliente' required placeholder='Nome do cliente' class='input'>
            <button class='btn-salvar' style='width:100%'>Conectar</button>
        </form>
        <a class='link' href='/painel'>Ver painel de lojas</a>


    

"""
    return pagina("Conectar loja", corpo)


@app.route("/conectar")
def conectar():
    cliente = request.args.get("cliente", "sem_nome")
    url = AUTH_URL + "?response_type=code&client_id=" + CLIENT_ID + "&redirect_uri=" + REDIRECT_URI + "&state=" + cliente
    return redirect(url)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    cliente = (request.args.get("state", "") or "").strip() or "sem_nome"
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    })
    dados = resp.json()
    if "access_token" not in dados:
        msg = dados.get("error_description") or dados.get("error") or str(dados)
        corpo = (""
                 "<h2 style='color:#d64545'>Falha ao conectar a loja " + esc(cliente) + "</h2>"
                 "**O Mercado Livre não autorizou a conexão.**
"
                 "Erro: " + esc(str(msg)) + "

"
                 "A loja **não foi salva**. Tente conectar novamente e complete a autorização até o fim.

"
                 "<a class='link' href='/'>← Tentar novamente</a>



")
        return pagina("Erro ao conectar", corpo)
    user_id = dados.get("user_id")
    agora = int(time.time())
    with banco() as conn:
        existente = consultar(conn, "SELECT id FROM conexoes WHERE user_id=%s", (user_id,))
        if existente:
            executar(conn, "UPDATE conexoes SET cliente=%s, access_token=%s, refresh_token=%s, expires_at=%s, status='ativa' WHERE user_id=%s",
                     (cliente, dados["access_token"], dados["refresh_token"], agora + dados["expires_in"], user_id))
        else:
            executar(conn, "INSERT INTO conexoes (cliente, user_id, access_token, refresh_token, expires_at, status) VALUES (%s,%s,%s,%s,%s,'ativa')",
                     (cliente, user_id, dados["access_token"], dados["refresh_token"], agora + dados["expires_in"]))
    corpo = (""
             "<h2>Loja de " + esc(cliente) + " conectada com sucesso!</h2>"
             "Os dados serão carregados automaticamente

"
             "<a class='link' href='/painel'>Ver painel</a>



")
    return pagina("Conectado", corpo)


@app.route("/status")
def status():
    with banco() as conn:
        linhas = consultar(conn, "SELECT cliente, user_id, status, expires_at FROM conexoes")
    linhas_html = ""
    for l in linhas:
        quando = time.strftime("%d/%m/%Y %H:%M", time.localtime(l["expires_at"])) if l["expires_at"] else "-"
        tag = "tag " + (l["status"] if l["status"] in ("ativa", "pausado", "expirada") else "normal")
        linhas_html += ("<tr><td>" + esc(str(l["cliente"])) + "</td><td>" + str(l["user_id"]) +
                        "</td><td>" + esc(l["status"]) + "</td><td>" + quando + "</td></tr>")
    corpo = ("<h2>Conexões</h2>Status de cada loja conectada

"
             "| Cliente | Loja | Status | Expira em |
| --- | --- | --- | --- |

")
    return pagina("Status", corpo)


@app.route("/renomear/<int:cid>", methods=["POST"])
def renomear(cid):
    novo = (request.form.get("cliente") or "").strip()
    if not novo:
        return jsonify({"ok": False}), 400
    with banco() as conn:
        executar(conn, "UPDATE conexoes SET cliente=%s WHERE id=%s", (novo, cid))
    return jsonify({"ok": True})


@app.route("/salvar_custo/<int:cid>/<item_id>", methods=["POST"])
def salvar_custo(cid, item_id):
    try:
        custo = float((request.form.get("custo") or "0").replace(",", "."))
    except Exception:
        return jsonify({"ok": False}), 400
    if custo < 0:
        return jsonify({"ok": False}), 400
    with banco() as conn:
        executar(conn, "UPDATE anuncios SET custo=%s WHERE conexao_id=%s AND item_id=%s", (custo, cid, item_id))
    return jsonify({"ok": True})


@app.route("/painel")
def painel():
    with banco() as conn:
        linhas = consultar(conn, """
            SELECT c.id, c.cliente, c.user_id, c.status,
              (SELECT COUNT(*) FROM anuncios a WHERE a.conexao_id=c.id) qtd_anuncios,
              (SELECT COUNT(*) FROM pedidos p WHERE p.conexao_id=c.id) qtd_pedidos,
              (SELECT COUNT(*) FROM perguntas q WHERE q.conexao_id=c.id AND q.status != 'ANSWERED') qtd_perguntas_pendentes
            FROM conexoes c ORDER BY c.id
        """)
    if not linhas:
        corpo = (""
                 "<h2>Nenhuma loja conectada ainda</h2>"
                 "Comece conectando a primeira loja

"
                 "<a class='link' href='/'>Conectar loja</a>



")
        return pagina("Painel", corpo)
    cards = ""
    for l in linhas:
        tag = "tag " + (l["status"] if l["status"] in ("ativa", "pausado", "expirada") else "normal")
        cards += (""
                  ""
                  "<h2>" + esc(str(l["cliente"])) + " "
                  "<a class='icon-link' href='#' onclick='editarNome(" + str(l["id"]) + "); return false;' title='Renomear loja'>✏️</a></h2>"
                  "" + esc(l["status"]) + "

"
                  ""
                  "" + str(l["qtd_anuncios"]) + "

Anúncios



"
                  "" + str(l["qtd_pedidos"]) + "

Pedidos



"
                  "" + str(l["qtd_perguntas_pendentes"]) + "

Perguntas p/ responder



"
                  "

"
                  ""
                  "<a class='link' href='/painel/" + str(l["id"]) + "'>Abrir detalhes</a>"
                  " <a class='link' href='/anuncios/" + str(l["id"]) + "'>Anúncios</a>"
                  " <a class='link' href='/desempenho/" + str(l["id"]) + "'>Desempenho</a>"
                  " <a class='link' href='/demandas/" + str(l["id"]) + "'>Demandas</a>"
                  " <a class='link' href='/promocoes/" + str(l["id"]) + "'>Promoções</a>"
                  " <a class='link' href='/atualizar?cid=" + str(l["id"]) + "'>Atualizar dados</a>"
                  " <a class='btn-danger' href='/excluir/" + str(l["id"]) + "'>Excluir</a>"
                  "



")
    corpo = "<h2 style='margin-bottom:16px'>Lojas conectadas</h2>" + cards
    return pagina("Painel", corpo)


@app.route("/excluir/<int:cid>", methods=["GET", "POST"])
def excluir(cid):
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
    if not c:
        return pagina("Não encontrada", "<h2>Loja não encontrada</h2>

")
    if request.method == "POST":
        with banco() as conn:
            for tabela in ("dados_conta", "anuncios", "pedidos", "metricas", "desempenho_historico", "perguntas", "envios", "promocoes", "promocoes_itens", "ads_campanhas", "ads_metricas", "erros"):
                executar(conn, "DELETE FROM " + tabela + " WHERE conexao_id=%s", (cid,))
            executar(conn, "DELETE FROM conexoes WHERE id=%s", (cid,))
        corpo = (""
                 "<h2>Loja excluída com sucesso!</h2>"
                 "Todos os dados dessa loja foram removidos

"
                 "<a class='link' href='/painel'>Voltar ao painel</a>



")
        return pagina("Excluída", corpo)
    corpo = (""
             "<h2>Excluir loja de " + esc(str(c["cliente"])) + "?</h2>"
             "Essa ação remove a conexão e todos os dados da loja. Essa ação não pode ser desfeita.

"
             "<form method='post' action='/excluir/" + str(cid) + "' style='margin-top:16px'>"
             "<button class='btn-danger' style='padding:13px 24px;font-size:15px'>Sim, excluir</button>"
             "</form>"
             "<a class='link' href='/painel'>← Cancelar</a>

"
             "

")
    return pagina("Excluir loja", corpo)


@app.route("/promocoes/<int:cid>")
def promocoes(cid):
    hoje = datetime.date.today()
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if c:
            promos = consultar(conn, "SELECT * FROM promocoes WHERE conexao_id=%s ORDER BY fim DESC", (cid,))
            itens_promo = consultar(conn, """
                SELECT pi.promocao_id, pi.item_id, pi.preco_promocional,
                       a.titulo, a.preco, a.custo, a.quantidade, a.status
                FROM promocoes_itens pi
                LEFT JOIN anuncios a ON a.conexao_id=pi.conexao_id AND a.item_id=pi.item_id
                WHERE pi.conexao_id=%s
            """, (cid,))
    if not c:
        return pagina("Não encontrada", "<h2>Loja não encontrada</h2>

")

    itens_por_promo = {}
    for it in itens_promo:
        itens_por_promo.setdefault(it["promocao_id"], []).append(it)

    corpo = (""
             "<h2>Promoções de " + esc(str(c["cliente"])) + " "
             "<a class='icon-link' href='#' onclick='editarNome(" + str(cid) + "); return false;' title='Renomear loja'>✏️</a></h2>"
             ""
             "<a class='link' href='/painel/" + str(cid) + "'>← Detalhes</a>"
             "<a class='btn-acoes' href='/anuncios/" + str(cid) + "'>Anúncios</a>"
             "<a class='btn-acoes' href='/atualizar?cid=" + str(cid) + "'>Atualizar dados</a>"
             "



")

    if not promos:
        corpo += (""
                  "<h2>Nenhuma promoção carregada ainda</h2>"
                  "Clique em 'Atualizar dados' para buscar as promoções da loja



")
        return pagina("Promoções", corpo)

    ativas = sum(1 for p in promos if str(p["status"]) in ("active", "ACTIVE"))
    candidatas = sum(1 for p in promos if str(p["status"]) in ("candidate", "CANDIDATE"))
    finalizadas = sum(1 for p in promos if str(p["status"]) not in ("active", "ACTIVE", "candidate", "CANDIDATE"))
    corpo += (""
              "" + str(ativas) + "

Promoções ativas



"
              "" + str(candidatas) + "

Candidatas



"
              "" + str(finalizadas) + "

Finalizadas



"
              "

")

    alertas = []
    for p in promos:
        if str(p["status"]) not in ("active", "ACTIVE"):
            continue
        fim = p["fim"]
        if not fim:
            continue
        try:
            d_fim = datetime.datetime.fromisoformat(fim[:10]).date()
        except Exception:
            continue
        dias = (d_fim - hoje).days
        if dias <= 3:
            alertas.append((p["nome"] or p["promocao_id"], dias, "urgente"))
        elif dias <= 7:
            alertas.append((p["nome"] or p["promocao_id"], dias, "atencao"))
    if alertas:
        corpo += "<h2>⏰ Alertas de expiração</h2>Promoções ativas que estão terminando

"
        for nome, dias, grav in alertas:
            txt = "expira hoje" if dias <= 0 else "expira em " + str(dias) + " dia(s)"
            corpo += "" + esc(nome) + " — " + txt + "

"
        corpo += "

"
    else:
        corpo += "<h2>⏰ Alertas de expiração</h2>Nenhuma promoção ativa perto de expirar

OK

"

    for p in promos:
        st = str(p["status"])
        if st in ("active", "ACTIVE"):
            classe, st_txt = "ativa", "ATIVA"
        elif st in ("candidate", "CANDIDATE"):
            classe, st_txt = "candidata", "CANDIDATA"
        else:
            classe, st_txt = "finalizada", "FINALIZADA"
        itens = itens_por_promo.get(p["promocao_id"], [])
        corpo += (""
                  "" + esc(p["nome"] or ("Promoção " + str(p["promocao_id"]))) +
                  " " + st_txt + "

"
                  "Tipo: " + esc(str(p["tipo"] or "-")) + " · Início: " + esc(str(p["inicio"] or "-")[:10]) +
                  " · Fim: " + esc(str(p["fim"] or "-")[:10]) + " · Itens: " + str(len(itens)) + "

")
        if itens:
            corpo += ("| Anúncio | Preço normal | Preço promo | Desconto | Custo | Margem na promo |
| --- | --- | --- | --- | --- | --- |
| " + esc(str(it["titulo"] or it["item_id"])) + "" + str(it["item_id"]) + " | R$ %.2f" % preco + " | " + preco_promo_html + " | " + desc_html + " | " + custo_html + " | " + margem_html + " |"
        else:
            corpo += "Sem itens associados a esta promoção.

"
        corpo += "

"

    corpo += ("Para o comparativo de margem, defina o **custo** de cada anúncio clicando em '+ definir' ou '+ custo'. "
              "O painel calcula o desconto aplicado e se a promoção ainda deixa margem para o vendedor.

")
    return pagina("Promoções de " + str(c["cliente"]), corpo)


@app.route("/exportar_demandas/<int:cid>")
def exportar_demandas(cid):
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if c:
            anuncios = consultar(conn, "SELECT * FROM anuncios WHERE conexao_id=%s", (cid,))
            metricas = consultar(conn, "SELECT item_id, visitas, conversao FROM metricas WHERE conexao_id=%s", (cid,))
            promos_ativas = consultar(conn, """SELECT DISTINCT pi.item_id
                FROM promocoes_itens pi JOIN promocoes p ON p.conexao_id=pi.conexao_id AND p.promocao_id=pi.promocao_id
                WHERE pi.conexao_id=%s AND p.status IN ('active','ACTIVE')""", (cid,))
    if not c:
        return "Loja não encontrada", 404

    itens_promocao = {r["item_id"] for r in promos_ativas}
    visitas_por_item = {m["item_id"]: (m["visitas"] or 0) for m in metricas}
    conv_por_item = {m["item_id"]: (m["conversao"] or 0) for m in metricas}

    linhas = []
    for a in anuncios:
        a["visitas"] = visitas_por_item.get(a["item_id"], 0)
        demandas_lista = montar_demandas_anuncio(a, a["item_id"] in itens_promocao, conv_por_item.get(a["item_id"]))
        if not demandas_lista:
            continue
        for acao, grav in demandas_lista:
            linhas.append([c["cliente"], a["item_id"], a["titulo"], grav, acao])

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Cliente", "Item", "Anúncio", "Gravidade", "Demanda"])
    for l in linhas:
        writer.writerow(l)
    nome_arq = ("demandas_" + str(c["cliente"]).replace(" ", "_") + ".csv")
    return Response(
        buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=" + nome_arq}
    )


@app.route("/demandas/<int:cid>")
def demandas(cid):
    limite = request.args.get("limite", type=int, default=20)
    if limite < 1:
        limite = 20
    if limite > 200:
        limite = 200
    filtro = request.args.get("filtro", "").strip()

    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if c:
            anuncios = consultar(conn, "SELECT * FROM anuncios WHERE conexao_id=%s", (cid,))
            metricas = consultar(conn, "SELECT item_id, visitas, conversao FROM metricas WHERE conexao_id=%s", (cid,))
            promos_ativas = consultar(conn, """SELECT DISTINCT pi.item_id
                FROM promocoes_itens pi JOIN promocoes p ON p.conexao_id=pi.conexao_id AND p.promocao_id=pi.promocao_id
                WHERE pi.conexao_id=%s AND p.status IN ('active','ACTIVE')""", (cid,))
    if not c:
        return pagina("Não encontrada", "<h2>Loja não encontrada</h2>

")

    itens_promocao = {r["item_id"] for r in promos_ativas}
    visitas_por_item = {m["item_id"]: (m["visitas"] or 0) for m in metricas}
    conv_por_item = {m["item_id"]: (m["conversao"] or 0) for m in metricas}

    itens_demandas = []
    for a in anuncios:
        a["visitas"] = visitas_por_item.get(a["item_id"], 0)
        demandas_lista = montar_demandas_anuncio(a, a["item_id"] in itens_promocao, conv_por_item.get(a["item_id"]))
        if not demandas_lista:
            continue
        urgentes = sum(1 for _, g in demandas_lista if g == "urgente")
        itens_demandas.append({
            "item_id": a["item_id"],
            "titulo": a["titulo"],
            "demandas": demandas_lista,
            "urgentes": urgentes,
            "total": len(demandas_lista)
        })

    itens_demandas.sort(key=lambda x: (-x["urgentes"], -x["total"]))

    corpo = (""
             "<h2>Central de Demandas de " + esc(str(c["cliente"])) + " "
             "<a class='icon-link' href='#' onclick='editarNome(" + str(cid) + "); return false;' title='Renomear loja'>✏️</a></h2>"
             ""
             "<a class='link' href='/painel/" + str(cid) + "'>← Detalhes</a>"
             "<a class='btn-acoes' href='/anuncios/" + str(cid) + "'>Anúncios</a>"
             "<a class='btn-acoes verde' href='/desempenho/" + str(cid) + "'>Desempenho</a>"
             "<a class='btn-acoes rosa' href='/promocoes/" + str(cid) + "'>Promoções</a>"
             "<a class='btn-acoes cinza' href='/exportar_demandas/" + str(cid) + "'>⬇ Exportar CSV</a>"
             "<a class='btn-acoes cinza' href='#' onclick='window.print(); return false;'>🖨 Imprimir/PDF</a>"
             "<a class='btn-acoes' href='/atualizar?cid=" + str(cid) + "'>Atualizar dados</a>"
             "



")

    total_anuncios = len(anuncios)
    com_demanda = len(itens_demandas)
    urgentes_total = sum(i["urgentes"] for i in itens_demandas)
    corpo += (""
              "" + str(total_anuncios) + "

Total de anúncios



"
              "" + str(com_demanda) + "

Precisam de ação



"
              "" + str(urgentes_total) + "

Demandas urgentes



"
              "

")

    corpo += ("<h2>Central de Demandas</h2>"
              "Principais pontos de alerta por anúncio, ordenados por prioridade

"
              "<form method='get' action='/demandas/" + str(cid) + "' style='display:flex;flex-wrap:wrap;align-items:center;gap:8px'>"
              "<label style='font-size:13px;color:#6b7280'>Mostrar:</label>"
              "<input type='number' name='limite' value='" + str(limite) + "' min='1' max='200' class='filtro' style='width:90px'>"
              "anúncios"
              "<button class='filtro-btn'>Aplicar</button>"
              "</form>"
              "**Filtrar por tipo:** "
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite=" + str(limite) + "' style='text-decoration:none'>Todos</a>"
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite=" + str(limite) + "&filtro=estoque' style='text-decoration:none'>Estoque</a>"
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite=" + str(limite) + "&filtro=fotos' style='text-decoration:none'>Fotos</a>"
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite=" + str(limite) + "&filtro=clips' style='text-decoration:none'>Clips</a>"
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite=" + str(limite) + "&filtro=tag' style='text-decoration:none'>Tags</a>"
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite=" + str(limite) + "&filtro=conversao' style='text-decoration:none'>Conversão</a>"
              "



")

    if not itens_demandas:
        corpo += (""
                  "<h2>Nenhuma demanda encontrada</h2>"
                  "Todos os anúncios carregados estão em dia. Clique em 'Atualizar dados' para buscar os dados mais recentes.



")
        return pagina("Demandas", corpo)

    if filtro:
        filtrados = []
        for i in itens_demandas:
            if filtro == "estoque" and any("epor estoque" in d or "Estoque" in d for d, _ in i["demandas"]):
                filtrados.append(i)
            elif filtro == "fotos" and any("foto" in d.lower() for d, _ in i["demandas"]):
                filtrados.append(i)
            elif filtro == "clips" and any("clip" in d.lower() or "vídeo" in d.lower() or "video" in d.lower() for d, _ in i["demandas"]):
                filtrados.append(i)
            elif filtro == "tag" and any("tag" in d.lower() for d, _ in i["demandas"]):
                filtrados.append(i)
            elif filtro == "conversao" and any("onversão" in d for d, _ in i["demandas"]):
                filtrados.append(i)
        itens_demandas = filtrados
        if not itens_demandas:
            corpo += ("<h2>Nenhum anúncio com esse tipo de demanda</h2>

")
            return pagina("Demandas", corpo)

    itens_demandas = itens_demandas[:limite]

    corpo += "<h2>Anúncios que precisam de ação " + str(len(itens_demandas)) + "</h2>"
    for i in itens_demandas:
        classe = "urgente" if i["urgentes"] > 0 else "atencao"
        corpo += (""
                  "" + esc(i["titulo"]) + " <small class='muted'>(" + str(i["item_id"]) + ")</small>"
                  " " + str(i["total"]) + " demandas

")
        for acao, grav in i["demandas"]:
            corpo += "" + ("🔴 " if grav == "urgente" else "🟡 ") + esc(acao) + "

"
        corpo += "

"
    corpo += "

"

    return pagina("Demandas de " + str(c["cliente"]), corpo)


@app.route("/anuncios/<int:cid>")
def anuncios(cid):
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        anuncios = consultar(conn, "SELECT * FROM anuncios WHERE conexao_id=%s ORDER BY vendidos DESC", (cid,))
        promos_ativas = consultar(conn, """SELECT DISTINCT pi.item_id
            FROM promocoes_itens pi JOIN promocoes p ON p.conexao_id=pi.conexao_id AND p.promocao_id=pi.promocao_id
            WHERE pi.conexao_id=%s AND p.status IN ('active','ACTIVE')""", (cid,))
        erros = consultar(conn, "SELECT * FROM erros WHERE conexao_id=%s", (cid,))
    if not c:
        return pagina("Não encontrada", "<h2>Loja não encontrada</h2>

")

    itens_promocao = {r["item_id"] for r in promos_ativas}

    corpo = (""
             "<h2>Anúncios de " + esc(str(c["cliente"])) + " "
             "<a class='icon-link' href='#' onclick='editarNome(" + str(cid) + "); return false;' title='Renomear loja'>✏️</a></h2>"
             ""
             "<a class='link' href='/painel/" + str(cid) + "'>← Detalhes</a>"
             "<a class='btn-acoes verde' href='/desempenho/" + str(cid) + "'>Desempenho</a>"
             "<a class='btn-acoes laranja' href='/demandas/" + str(cid) + "'>Demandas</a>"
             "<a class='btn-acoes rosa' href='/promocoes/" + str(cid) + "'>Promoções</a>"
             "<a class='btn-acoes' href='/atualizar?cid=" + str(cid) + "'>Atualizar dados</a>"
             "



")

    if not anuncios:
        corpo += (""
                  "<h2>Nenhum anúncio carregado ainda</h2>"
                  "Clique em 'Atualizar dados' para buscar os anúncios da loja



")
        return pagina("Anúncios", corpo)

    total = len(anuncios)
    com_estoque_zero = sum(1 for a in anuncios if (a["quantidade"] or 0) <= 0)
    com_fotos_baixas = sum(1 for a in anuncios if (a["fotos"] or 0) < 10)
    em_promocao = sum(1 for a in anuncios if a["item_id"] in itens_promocao)
    corpo += (""
              "" + str(total) + "

Total de anúncios



"
              "" + str(com_estoque_zero) + "

Estoque zerado



"
              "" + str(com_fotos_baixas) + "

Fotos abaixo de 10



"
              "" + str(em_promocao) + "

Em promoção



"
              "

")

    linhas_html = ""
    for a in anuncios:
        em_promo = a["item_id"] in itens_promocao
        st = str(a["status"])
        if st in ("active", "ACTIVE"):
            st_tag, st_txt = "tag ativa", "ativo"
        elif st in ("paused", "PAUSED"):
            st_tag, st_txt = "tag pausado", "pausado"
        else:
            st_tag, st_txt = "tag normal", st
        fotos = a["fotos"] or 0
        if fotos >= 10:
            fotos_html = "" + str(fotos) + "/10"
        elif fotos > 0:
            fotos_html = "" + str(fotos) + "/10"
        else:
            fotos_html = "0/10"
        clips = a["clips"] if a["clips"] is not None else None
        if clips is None:
            clips_html = "não verificado"
        elif clips >= 2:
            clips_html = "" + str(clips) + ""
        elif clips > 0:
            clips_html = "" + str(clips) + ""
        else:
            clips_html = "0"
        promo_html = ("Em promoção" if em_promo
                      else "—")
        tags = []
        try:
            tags = json.loads(a["tags"]) if a["tags"] else []
        except Exception:
            tags = []
        tags_html = ""
        for t in tags[:6]:
            if t in TAGS_RUINS:
                tags_html += "" + esc(t) + " "
            elif t in TAGS_BOAS:
                tags_html += "" + esc(t) + " "
            else:
                tags_html += "" + esc(t) + " "
        if not tags_html:
            tags_html = "sem tags"

        peso_kg = a["peso"]
        f = frete_esperado(a["preco"], peso_kg)
        if f is not None:
            frete_html = "R$ %.2f" % f
            peso_txt = ("%.2f kg" % peso_kg) if peso_kg else "-"
        else:
            frete_html = "sem peso"
            peso_txt = "-"

        linhas_html += ("<tr>"
                        "<td>**" + esc(str(a["titulo"])) + "**
<small class='muted'>" + str(a["item_id"]) + "</small></td>"
                        "<td>R$ %.2f" % (a["preco"] or 0) + "</td>"
                        "<td>" + str(a["quantidade"] or 0) + "</td>"
                        "<td>" + fotos_html + "</td>"
                        "<td>" + clips_html + "</td>"
                        "<td>" + st_txt + "</td>"
                        "<td>" + promo_html + "</td>"
                        "<td>" + tags_html + "</td>"
                        "<td>" + str(a["vendidos"] or 0) + "</td>"
                        "<td>" + peso_txt + "</td>"
                        "<td>" + frete_html + "</td>"
                        "</tr>")

    corpo += ("<h2>Lista de anúncios " + str(total) + "</h2>"
              "Análises por produto — fotos, clips, promoção, tags e frete esperado

"
              "| Anúncio | Preço | Estoque | Fotos | Clips | Status | Promoção | Tags | Vendidos | Peso | Frete esperado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

"
              "Frete esperado = custo do Mercado Livre pela tabela oficial (peso × faixa de preço). "
              "Veja as demandas urgentes na <a class='link' href='/demandas/" + str(cid) + "'>Central de Demandas</a> e as promoções na <a class='link' href='/promocoes/" + str(cid) + "'>tela de Promoções</a>.



")

    if erros:
        avisos = ""
        for e in erros:
            if e["categoria"] in ("financeiro",):
                continue
            avisos += "" + esc(e["categoria"]) + ": " + esc(e["mensagem"]) + "

"
        if avisos:
            corpo += "**Avisos:** " + avisos + "

"

    return pagina("Anúncios de " + str(c["cliente"]), corpo)


@app.route("/desempenho/<int:cid>")
def desempenho(cid):
    dias = request.args.get("dias", type=int, default=30)
    de = request.args.get("de", "").strip()
    ate = request.args.get("ate", "").strip()
    hoje = datetime.date.today()
    if de and ate:
        try:
            d_inicio = datetime.datetime.strptime(de, "%Y-%m-%d").date()
            d_fim = datetime.datetime.strptime(ate, "%Y-%m-%d").date()
        except Exception:
            d_inicio = hoje - datetime.timedelta(days=30)
            d_fim = hoje
    else:
        d_inicio = hoje - datetime.timedelta(days=dias)
        d_fim = hoje
    if d_fim < d_inicio:
        d_inicio, d_fim = d_fim, d_inicio
    dur = (d_fim - d_inicio).days + 1
    p_inicio = d_inicio - datetime.timedelta(days=dur)
    p_fim = d_inicio - datetime.timedelta(days=1)

    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if c:
            linhas = consultar(conn, """
                SELECT a.item_id, a.titulo, a.status, a.preco,
                  COALESCE(SUM(CASE WHEN h.data BETWEEN %s AND %s THEN h.visitas ELSE 0 END),0) AS visitas,
                  COALESCE(SUM(CASE WHEN h.data BETWEEN %s AND %s THEN h.vendidos ELSE 0 END),0) AS vendidos,
                  COALESCE(SUM(CASE WHEN h.data BETWEEN %s AND %s THEN h.visitas ELSE 0 END),0) AS visitas_ant,
                  COALESCE(SUM(CASE WHEN h.data BETWEEN %s AND %s THEN h.vendidos ELSE 0 END),0) AS vendidos_ant
                FROM anuncios a
                LEFT JOIN desempenho_historico h ON h.conexao_id=a.conexao_id AND h.item_id=a.item_id
                WHERE a.conexao_id=%s
                GROUP BY a.item_id, a.titulo, a.status, a.preco
                ORDER BY vendidos DESC
            """, (d_inicio.isoformat(), d_fim.isoformat(),
                  d_inicio.isoformat(), d_fim.isoformat(),
                  p_inicio.isoformat(), p_fim.isoformat(),
                  p_inicio.isoformat(), p_fim.isoformat(), cid))
            grafico_v = consultar(conn, """
                SELECT h.data, COALESCE(SUM(h.visitas),0) AS visitas
                FROM desempenho_historico h
                WHERE h.conexao_id=%s AND h.data BETWEEN %s AND %s
                GROUP BY h.data ORDER BY h.data
            """, (cid, d_inicio.isoformat(), d_fim.isoformat()))
            grafico_f = consultar(conn, """
                SELECT SUBSTRING(fechado_em,1,10) AS dia, COALESCE(SUM(total),0) AS total
                FROM pedidos
                WHERE conexao_id=%s AND fechado_em IS NOT NULL
                  AND SUBSTRING(fechado_em,1,10) BETWEEN %s AND %s
                GROUP BY SUBSTRING(fechado_em,1,10)
            """, (cid, d_inicio.isoformat(), d_fim.isoformat()))
    if not c:
        return pagina("Não encontrada", "<h2>Loja não encontrada</h2>

")

    visitas_por_dia = {r["data"]: r["visitas"] for r in grafico_v}
    fat_por_dia = {r["dia"]: r["total"] for r in grafico_f}
    rotulos, visitas_serie, fat_serie = [], [], []
    d = d_inicio
    while d <= d_fim:
        iso = d.isoformat()
        rotulos.append(d.strftime("%d/%m"))
        visitas_serie.append(visitas_por_dia.get(iso, 0))
        fat_serie.append(round(fat_por_dia.get(iso, 0), 2))
        d += datetime.timedelta(days=1)

    corpo = (""
             "<h2>Desempenho de " + esc(str(c["cliente"])) + " "
             "<a class='icon-link' href='#' onclick='editarNome(" + str(cid) + "); return false;' title='Renomear loja'>✏️</a></h2>"
             ""
             "<a class='link' href='/painel/" + str(cid) + "'>← Detalhes</a>"
             "<a class='btn-acoes' href='/anuncios/" + str(cid) + "'>Anúncios</a>"
             "<a class='btn-acoes laranja' href='/demandas/" + str(cid) + "'>Demandas</a>"
             "<a class='btn-acoes rosa' href='/promocoes/" + str(cid) + "'>Promoções</a>"
             "<a class='btn-acoes' href='/atualizar?cid=" + str(cid) + "'>Atualizar dados</a>"
             "



")

    corpo += ("<h2>Período de análise</h2>Escolha o período para comparar visitas, vendas e faturamento

"
              "<form method='get' action='/desempenho/" + str(cid) + "' style='display:flex;flex-wrap:wrap;align-items:center;gap:8px'>"
              "<a class='filtro' href='/desempenho/" + str(cid) + "?dias=7' style='text-decoration:none'>7 dias</a>"
              "<a class='filtro' href='/desempenho/" + str(cid) + "?dias=30' style='text-decoration:none'>30 dias</a>"
              "<a class='filtro' href='/desempenho/" + str(cid) + "?dias=90' style='text-decoration:none'>90 dias</a>"
              "<input type='date' name='de' value='" + de + "' class='filtro' style='margin-left:10px'>"
              "até"
              "<input type='date' name='ate' value='" + ate + "' class='filtro'>"
              "<button class='filtro-btn'>Aplicar</button>"
              "</form>"
              "Período selecionado: " + d_inicio.strftime("%d/%m/%Y") + " a " + d_fim.strftime("%d/%m/%Y") +
              " (comparado com " + p_inicio.strftime("%d/%m/%Y") + " a " + p_fim.strftime("%d/%m/%Y") + ")



")

    if not linhas:
        corpo += (""
                  "<h2>Sem dados de desempenho ainda</h2>"
                  "O histórico é gravado automaticamente a cada atualização. Clique em 'Atualizar dados' para começar a acumular.



")
        return pagina("Desempenho", corpo)

    tot_visitas = sum(r["visitas"] or 0 for r in linhas)
    tot_vendas = sum(r["vendidos"] or 0 for r in linhas)
    tot_conv = round((tot_vendas * 100.0 / tot_visitas), 2) if tot_visitas else 0
    tot_fat = round(sum(fat_serie), 2)
    corpo += (""
              "" + str(tot_visitas) + "

Visitas no período



"
              "" + str(tot_vendas) + "

Vendas no período



"
              "R$ %.2f" % tot_fat + "

Faturamento no período



"
              "" + ("%.2f%%" % tot_conv) + "

Conversão



"
              "

")

    corpo += ("<h2>Evolução diária</h2>"
              "Faturamento diário (R$) e visitas no período

"
              "<canvas id='graficoDesempenho'></canvas>

"
              "

")

    corpo += ("<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'></script>"
              "<script>"
              "var rotulos = " + json.dumps(rotulos) + ";"
              "var visitas = " + json.dumps(visitas_serie) + ";"
              "var faturamento = " + json.dumps(fat_serie) + ";"
              "new Chart(document.getElementById('graficoDesempenho'), {"
              "type:'line',"
              "data:{labels:rotulos,datasets:["
              "{label:'Visitas',data:visitas,borderColor:'#3483FA',backgroundColor:'rgba(52,131,250,0.12)',yAxisID:'y',tension:0.3,fill:true},"
              "{label:'Faturamento (R$)',data:faturamento,borderColor:'#FFE600',backgroundColor:'rgba(255,230,0,0.25)',yAxisID:'y1',tension:0.3,fill:true}"
              "]},"
              "options:{responsive:true,maintainAspectRatio:false,"
              "plugins:{legend:{position:'top'}},"
              "scales:{"
              "y:{type:'linear',position:'left',title:{display:true,text:'Visitas'},beginAtZero:true},"
              "y1:{type:'linear',position:'right',title:{display:true,text:'Faturamento (R$)'},beginAtZero:true,grid:{drawOnChartArea:false}}"
              "}}});"
              "</script>")

    linhas_html = ""
    for r in linhas:
        st = str(r["status"])
        if st in ("active", "ACTIVE"):
            st_tag, st_txt = "tag ativa", "ativo"
        elif st in ("paused", "PAUSED"):
            st_tag, st_txt = "tag pausado", "pausado"
        else:
            st_tag, st_txt = "tag normal", st
        visitas = r["visitas"] or 0
        vendidos = r["vendidos"] or 0
        conv = round((vendidos * 100.0 / visitas), 2) if visitas else 0
        v_ant = r["visitas_ant"] or 0
        if v_ant > 0:
            delta_v = round(((visitas - v_ant) * 100.0 / v_ant), 1)
            if delta_v > 0:
                tend_v = "▲ +" + str(delta_v) + "%"
            elif delta_v < 0:
                tend_v = "▼ " + str(delta_v) + "%"
            else:
                tend_v = "— 0%"
        else:
            tend_v = "sem base"
        s_ant = r["vendidos_ant"] or 0
        if s_ant > 0:
            delta_s = round(((vendidos - s_ant) * 100.0 / s_ant), 1)
            if delta_s > 0:
                tend_s = "▲ +" + str(delta_s) + "%"
            elif delta_s < 0:
                tend_s = "▼ " + str(delta_s) + "%"
            else:
                tend_s = "— 0%"
        else:
            tend_s = "sem base"
        conv_txt = ("%.2f%%" % conv) if visitas else "-"
        linhas_html += ("<tr>"
                        "<td>**" + esc(str(r["titulo"])) + "**
<small class='muted'>" + str(r["item_id"]) + "</small></td>"
                        "<td>" + st_txt + "</td>"
                        "<td>R$ %.2f" % (r["preco"] or 0) + "</td>"
                        "<td>" + str(visitas) + " " + tend_v + "</td>"
                        "<td>" + str(vendidos) + " " + tend_s + "</td>"
                        "<td>" + conv_txt + "</td>"
                        "</tr>")

    corpo += ("<h2>Desempenho por anúncio " + str(len(linhas)) + "</h2>"
              "Visitas, vendas e conversão no período, com tendência vs período anterior

"
              "| Anúncio | Status | Preço | Visitas | Vendas | Conversão |
| --- | --- | --- | --- | --- | --- |

"
              "▲/▼ compara com o período anterior de mesma duração. O histórico acumula automaticamente a cada atualização.



")

    return pagina("Desempenho de " + str(c["cliente"]), corpo)


@app.route("/painel/<int:cid>")
def painel_detalhe(cid):
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        conta = consultar(conn, "SELECT * FROM dados_conta WHERE conexao_id=%s", (cid,))
        conta = conta[0] if conta else None
        anuncios = consultar(conn, "SELECT * FROM anuncios WHERE conexao_id=%s ORDER BY vendidos DESC LIMIT 100", (cid,))
        pedidos = consultar(conn, "SELECT * FROM pedidos WHERE conexao_id=%s ORDER BY fechado_em DESC LIMIT 100", (cid,))
        metricas = consultar(conn, """
            SELECT a.titulo, m.vendidos, m.visitas, m.conversao
            FROM metricas m LEFT JOIN anuncios a ON a.conexao_id=m.conexao_id AND a.item_id=m.item_id
            WHERE m.conexao_id=%s ORDER BY m.vendidos DESC LIMIT 100
        """, (cid,))
        perguntas = consultar(conn, "SELECT * FROM perguntas WHERE conexao_id=%s ORDER BY data DESC LIMIT 100", (cid,))
        envios = consultar(conn, "SELECT * FROM envios WHERE conexao_id=%s ORDER BY data DESC LIMIT 100", (cid,))
        promos = consultar(conn, "SELECT * FROM promocoes WHERE conexao_id=%s ORDER BY fim DESC LIMIT 100", (cid,))
        ads_camp = consultar(conn, "SELECT * FROM ads_campanhas WHERE conexao_id=%s ORDER BY data_inicio DESC LIMIT 100", (cid,))
        ads_met = consultar(conn, "SELECT * FROM ads_metricas WHERE conexao_id=%s ORDER BY gasto DESC LIMIT 100", (cid,))
        erros = consultar(conn, "SELECT * FROM erros WHERE conexao_id=%s", (cid,))
    if not c:
        return pagina("Não encontrada", "<h2>Loja não encontrada</h2>

")

    corpo = (""
             "<h2>" + esc(str(c["cliente"])) + " "
             "<a class='icon-link' href='#' onclick='editarNome(" + str(cid) + "); return false;' title='Renomear loja'>✏️</a></h2>"
             ""
             "<a class='link' href='/painel'>← Voltar</a>"
             "<a class='btn-acoes' href='/anuncios/" + str(cid) + "'>Anúncios</a>"
             "<a class='btn-acoes verde' href='/desempenho/" + str(cid) + "'>Desempenho</a>"
             "<a class='btn-acoes laranja' href='/demandas/" + str(cid) + "'>Demandas</a>"
             "<a class='btn-acoes rosa' href='/promocoes/" + str(cid) + "'>Promoções</a>"
             "<a class='btn-acoes' href='/atualizar?cid=" + str(cid) + "'>Atualizar agora</a>"
             "<a class='btn-danger' href='/excluir/" + str(cid) + "'>Excluir</a>"
             "



")

    if conta:
        corpo += ("<h2>Conta</h2>Informações do vendedor

"
                  ""
                  "" + esc(str(conta["nickname"])) + "

Nickname



"
                  "" + esc(str(conta["nome"])) + " " + esc(str(conta["sobrenome"])) + "

Nome



"
                  "" + esc(str(conta["reputacao"])) + "

Reputação



"
                  "" + str(conta["pontos"]) + "

Vendas concluídas



"
                  "



")

    if anuncios:
        linhas_html = ""
        for a in anuncios:
            tag = "tag " + (a["status"] if a["status"] in ("ativa", "pausado", "expirada") else "normal")
            peso_kg = a["peso"]
            f = frete_esperado(a["preco"], peso_kg)
            if f is not None:
                frete_html = "R$ %.2f" % f
                peso_txt = ("%.2f kg" % peso_kg) if peso_kg else "-"
            else:
                frete_html = "sem peso"
                peso_txt = "-"
            linhas_html += ("<tr><td>" + esc(str(a["titulo"])) + "</td><td>R$ %.2f" % (a["preco"] or 0) +
                            "</td><td>" + str(a["quantidade"]) + "</td><td>" + esc(str(a["status"])) +
                            "</td><td>" + str(a["vendidos"]) + "</td><td>" + peso_txt + "</td><td>" + frete_html + "</td></tr>")
        corpo += ("<h2>Anúncios " + str(len(anuncios)) + "</h2>"
                  "Produtos da loja — <a class='link' href='/anuncios/" + str(cid) + "'>ver análises completas</a> · <a class='link' href='/desempenho/" + str(cid) + "'>ver desempenho</a> · <a class='link' href='/demandas/" + str(cid) + "'>ver demandas</a> · <a class='link' href='/promocoes/" + str(cid) + "'>ver promoções</a>

"
                  "| Título | Preço | Estoque | Status | Vendidos | Peso | Frete esperado |
| --- | --- | --- | --- | --- | --- | --- |

")

    if metricas:
        linhas_html = ""
        for m in metricas:
            conv_txt = ("%.2f%%" % m["conversao"]) if m["conversao"] is not None else "-"
            linhas_html += ("<tr><td>" + esc(str(m["titulo"]) or "-") + "</td><td>" + str(m["vendidos"]) +
                            "</td><td>" + str(m["visitas"]) + "</td><td>" + conv_txt + "</td></tr>")
        corpo += ("<h2>Métricas " + str(len(metricas)) + "</h2>"
                  "Visitas, vendidos e conversão por anúncio

"
                  "| Anúncio | Vendidos | Visitas | Conversão |
| --- | --- | --- | --- |

")

    if perguntas:
        linhas_html = ""
        for q in perguntas:
            tag = "tag " + ("respondida" if q["status"] == "ANSWERED" else "pendente")
            resp_txt = esc(str(q["resposta"]) or "-")
            if len(resp_txt) > 80:
                resp_txt = resp_txt[:80] + "..."
            linhas_html += ("<tr><td>" + esc(str(q["texto"])) + "</td><td>" + str(q["item_id"]) +
                            "</td><td>" + ("Respondida" if q["status"] == "ANSWERED" else "Pendente") +
                            "</td><td>" + resp_txt + "</td></tr>")
        corpo += ("<h2>Perguntas " + str(len(perguntas)) + "</h2>"
                  "Perguntas dos clientes nos anúncios

"
                  "| Pergunta | Anúncio | Status | Resposta |
| --- | --- | --- | --- |

")

    if envios:
        linhas_html = ""
        for s in envios:
            linhas_html += ("<tr><td>" + str(s["envio_id"]) + "</td><td>" + esc(str(s["status"])) +
                            "</td><td>" + esc(str(s["tracking"]) or "-") + "</td><td>" + str(s["pedido_id"]) +
                            "</td><td>" + esc(str(s["data"])) + "</td></tr>")
        corpo += ("<h2>Envios " + str(len(envios)) + "</h2>"
                  "Status e rastreio dos envios

"
                  "| Envio | Status | Rastreio | Pedido | Data |
| --- | --- | --- | --- | --- |

")

    if promos:
        linhas_html = ""
        for pr in promos:
            st = str(pr["status"])
            if st == "active":
                tag, st_txt = "tag ativa", "ativa"
            elif st == "candidate":
                tag, st_txt = "tag pendente", "candidata"
            elif st == "paused":
                tag, st_txt = "tag expirada", "pausada"
            else:
                tag, st_txt = "tag normal", "finalizada"
            linhas_html += ("<tr><td>" + esc(str(pr["nome"]) or "-") + "</td><td>" + st_txt + "</td>"
                            "<td>" + esc(str(pr["tipo"]) or "-") + "</td><td>" + esc(str(pr["inicio"]) or "-") + "</td>"
                            "<td>" + esc(str(pr["fim"]) or "-") + "</td><td>" + str(pr["qtd_itens"] or 0) + "</td></tr>")
        corpo += ("<h2>Promoções " + str(len(promos)) + "</h2>"
                  "Promoções e ofertas da loja — <a class='link' href='/promocoes/" + str(cid) + "'>ver análise completa</a>

"
                  "| Nome | Status | Tipo | Início | Fim | Itens |
| --- | --- | --- | --- | --- | --- |

")

    if ads_camp:
        linhas_html = ""
        for ac in ads_camp:
            st = str(ac["status"])
            if st in ("active", "ACTIVE", "running"):
                tag, st_txt = "tag ativa", "ativa"
            elif st in ("paused", "PAUSED"):
                tag, st_txt = "tag expirada", "pausada"
            elif st in ("finished", "FINISHED", "ended"):
                tag, st_txt = "tag normal", "finalizada"
            else:
                tag, st_txt = "tag normal", st
            orc_txt = ("R$ %.2f" % ac["orcamento"]) if ac["orcamento"] is not None else "-"
            linhas_html += ("<tr><td>" + esc(str(ac["nome"]) or "-") + "</td><td>" + st_txt + "</td>"
                            "<td>" + esc(str(ac["tipo"]) or "-") + "</td><td>" + esc(str(ac["data_inicio"]) or "-") + "</td>"
                            "<td>" + esc(str(ac["data_fim"]) or "-") + "</td><td>" + orc_txt + "</td></tr>")
        corpo += ("<h2>Mercado Ads — Campanhas " + str(len(ads_camp)) + "</h2>"
                  "Campanhas de publicidade da loja

"
                  "| Campanha | Status | Tipo | Início | Fim | Orçamento |
| --- | --- | --- | --- | --- | --- |

")

    if ads_met:
        linhas_html = ""
        for am in ads_met:
            ctr_txt = ("%.2f%%" % am["ctr"]) if am["ctr"] is not None else "-"
            gasto_txt = ("R$ %.2f" % am["gasto"]) if am["gasto"] is not None else "-"
            linhas_html += ("<tr><td>" + str(am["ad_id"]) + "</td><td>" + str(am["campanha_id"]) +
                            "</td><td>" + str(am["item_id"]) + "</td><td>" + str(am["impressoes"] or 0) +
                            "</td><td>" + str(am["cliques"] or 0) + "</td><td>" + ctr_txt + "</td><td>" + gasto_txt + "</td></tr>")
        corpo += ("<h2>Mercado Ads — Métricas " + str(len(ads_met)) + "</h2>"
                  "Impressões, cliques, CTR e gasto por anúncio patrocinado

"
                  "| Anúncio | Campanha | Item | Impressões | Cliques | CTR | Gasto |
| --- | --- | --- | --- | --- | --- | --- |

")

    if pedidos:
        linhas_html = ""
        for p in pedidos:
            total_txt = ("R$ %.2f" % p["total"]) if p["total"] is not None else "-"
            linhas_html += ("<tr><td>" + str(p["pedido_id"]) + "</td><td>" + esc(str(p["status"])) +
                            "</td><td>" + total_txt + "</td><td>" + esc(str(p["fechado_em"])) + "</td></tr>")
        corpo += ("<h2>Pedidos " + str(len(pedidos)) + "</h2>"
                  "Últimas vendas

"
                  "| Pedido | Status | Total | Data |
| --- | --- | --- | --- |

")

    if erros:
        avisos = ""
        for e in erros:
            if e["categoria"] == "financeiro":
                continue
            avisos += "" + esc(e["categoria"]) + ": " + esc(e["mensagem"]) + "

"
        if avisos:
            corpo += "**Avisos:** " + avisos + "

"

    corpo += "Os dados são atualizados automaticamente a cada hora.

"
    return pagina("Painel de " + str(c["cliente"]), corpo)


@app.route("/atualizar")
def atualizar():
    cid = request.args.get("cid", type=int)
    with banco() as conn:
        if cid:
            c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        else:
            c = consultar(conn, "SELECT * FROM conexoes WHERE status='ativa' ORDER BY id LIMIT 1")
        c = c[0] if c else None
    if not c:
        return pagina("Sem loja", "<h2>Nenhuma loja conectada</h2><a class='link' href='/'>Conectar</a>



")
    token = token_atual(c)
    if not token:
        return pagina("Erro", "<h2>Falha ao renovar o token</h2>Tente conectar a loja novamente.



")
    user_id = c["user_id"]
    puxar_conta(c["id"], token)
    if user_id:
        puxar_anuncios(c["id"], token, user_id)
        puxar_pedidos(c["id"], token, user_id)
        puxar_metricas(c["id"], token)
        puxar_perguntas(c["id"], token, user_id)
        puxar_envios(c["id"], token, user_id)
        puxar_promocoes(c["id"], token, user_id)
        puxar_ads(c["id"], token, user_id)
    gravar_historico(c["id"])
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
        executar(conn, "UPDATE conexoes SET access_token=%s, refresh_token=%s, expires_at=%s, status='ativa' WHERE id=%s",
                 (dados["access_token"], dados["refresh_token"], agora + dados["expires_in"], c["id"]))
    return dados["access_token"]


def job_refresh():
    agora = int(time.time())
    with banco() as conn:
        conexoes = consultar(conn, "SELECT * FROM conexoes WHERE status='ativa' AND expires_at < %s", (agora + 1800,))
        for c in conexoes:
            try:
                dados = renovar(c["refresh_token"])
                executar(conn, "UPDATE conexoes SET access_token=%s, refresh_token=%s, expires_at=%s, status='ativa' WHERE id=%s",
                         (dados["access_token"], dados["refresh_token"], agora + dados["expires_in"], c["id"]))
            except Exception:
                executar(conn, "UPDATE conexoes SET status='expirada' WHERE id=%s", (c["id"],))


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
        executar(conn, """INSERT INTO erros (conexao_id, categoria, mensagem, quando)
                        VALUES (%s,%s,%s,%s)
                        ON CONFLICT (conexao_id, categoria)
                        DO UPDATE SET mensagem=EXCLUDED.mensagem, quando=EXCLUDED.quando""",
                 (conexao_id, categoria, (mensagem or "")[:300], int(time.time())))


def gravar_historico(conexao_id):
    hoje = datetime.date.today().isoformat()
    agora = int(time.time())
    with banco() as conn:
        linhas = consultar(conn, "SELECT item_id, vendidos FROM anuncios WHERE conexao_id=%s", (conexao_id,))
        metricas = consultar(conn, "SELECT item_id, visitas FROM metricas WHERE conexao_id=%s", (conexao_id,))
    visitas_por_item = {m["item_id"]: (m["visitas"] or 0) for m in metricas}
    for l in linhas:
        item_id = l["item_id"]
        visitas = visitas_por_item.get(item_id, 0)
        vendidos = l["vendidos"] or 0
        with banco() as conn:
            executar(conn, """INSERT INTO desempenho_historico (conexao_id, item_id, data, visitas, vendidos, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, item_id, data) DO UPDATE SET
                              visitas=EXCLUDED.visitas, vendidos=EXCLUDED.vendidos, atualizado_em=EXCLUDED.atualizado_em""",
                     (conexao_id, item_id, hoje, visitas, vendidos, agora))


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
        executar(conn, """INSERT INTO dados_conta (conexao_id, user_id, nickname, nome, sobrenome, reputacao, pontos, atualizado_em)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (conexao_id) DO UPDATE SET
                          user_id=EXCLUDED.user_id, nickname=EXCLUDED.nickname, nome=EXCLUDED.nome,
                          sobrenome=EXCLUDED.sobrenome, reputacao=EXCLUDED.reputacao,
                          pontos=EXCLUDED.pontos, atualizado_em=EXCLUDED.atualizado_em""",
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
        executar(conn, "DELETE FROM anuncios WHERE conexao_id=%s", (conexao_id,))
    for item_id in ids:
        det, det_erro = api_get(token, "/items/" + str(item_id),
                                {"attributes": "id,title,price,available_quantity,status,sold_quantity,pictures,video_id,tags,shipping"})
        if det_erro or not det:
            continue
        fotos = 0
        pics = det.get("pictures")
        if isinstance(pics, list):
            fotos = len(pics)
        clips = det.get("video_id")
        if clips is None:
            clips = None
        else:
            clips = 1 if clips else 0
        tags = det.get("tags") or []
        peso = None
        shipping = det.get("shipping") or {}
        dims = shipping.get("dimensions") or ""
        if isinstance(dims, str) and "," in dims:
            try:
                peso = float(dims.split(",")[-1].strip()) / 1000.0
            except Exception:
                peso = None
        with banco() as conn:
            executar(conn, """INSERT INTO anuncios
                            (conexao_id, item_id, titulo, preco, quantidade, status, vendidos, atualizado_em, fotos, clips, tags, peso)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, item_id) DO UPDATE SET
                              titulo=EXCLUDED.titulo, preco=EXCLUDED.preco, quantidade=EXCLUDED.quantidade,
                              status=EXCLUDED.status, vendidos=EXCLUDED.vendidos, atualizado_em=EXCLUDED.atualizado_em,
                              fotos=EXCLUDED.fotos, clips=EXCLUDED.clips, tags=EXCLUDED.tags, peso=EXCLUDED.peso""",
                     (conexao_id, det.get("id"), det.get("title"), det.get("price"),
                      det.get("available_quantity"), det.get("status"), det.get("sold_quantity"), agora,
                      fotos, clips, json.dumps(tags, ensure_ascii=False), peso))


def puxar_metricas(conexao_id, token):
    with banco() as conn:
        linhas = consultar(conn, "SELECT item_id, vendidos FROM anuncios WHERE conexao_id=%s", (conexao_id,))
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
                executar(conn, """INSERT INTO metricas
                                (conexao_id, item_id, vendidos, visitas, conversao, atualizado_em)
                                VALUES (%s,%s,%s,%s,%s,%s)
                                ON CONFLICT (conexao_id, item_id) DO UPDATE SET
                                  vendidos=EXCLUDED.vendidos, visitas=EXCLUDED.visitas,
                                  conversao=EXCLUDED.conversao, atualizado_em=EXCLUDED.atualizado_em""",
                         (conexao_id, item_id, vendidos, visitas, conversao, agora))
            total_puxado += 1
    if total_puxado == 0:
        registrar_erro(conexao_id, "metricas", "nenhum dado de visita retornado")


def puxar_perguntas(conexao_id, token, user_id):
    dados, erro = api_get(token, "/questions/search",
                          {"seller_id": user_id, "api_version": 4, "limit": 50})
    if erro or not dados:
        registrar_erro(conexao_id, "perguntas", erro or "sem resposta")
        return
    perguntas = dados.get("questions") or []
    agora = int(time.time())
    with banco() as conn:
        executar(conn, "DELETE FROM perguntas WHERE conexao_id=%s", (conexao_id,))
    for q in perguntas:
        resp = q.get("answer") or {}
        with banco() as conn:
            executar(conn, """INSERT INTO perguntas
                            (conexao_id, pergunta_id, item_id, texto, status, resposta, data, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, pergunta_id) DO UPDATE SET
                              item_id=EXCLUDED.item_id, texto=EXCLUDED.texto, status=EXCLUDED.status,
                              resposta=EXCLUDED.resposta, data=EXCLUDED.data, atualizado_em=EXCLUDED.atualizado_em""",
                     (conexao_id, str(q.get("id")), q.get("item_id"), q.get("text"),
                      q.get("status"), resp.get("text"), q.get("date_created"), agora))


def puxar_envios(conexao_id, token, user_id):
    dados, erro = api_get(token, "/shipments/search", {"seller_id": user_id, "limit": 50})
    if erro or not dados:
        registrar_erro(conexao_id, "envios", erro or "sem resposta")
        return
    resultados = dados.get("results") or []
    agora = int(time.time())
    with banco() as conn:
        executar(conn, "DELETE FROM envios WHERE conexao_id=%s", (conexao_id,))
    for s in resultados:
        with banco() as conn:
            executar(conn, """INSERT INTO envios
                            (conexao_id, envio_id, status, tracking, pedido_id, data, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, envio_id) DO UPDATE SET
                              status=EXCLUDED.status, tracking=EXCLUDED.tracking,
                              pedido_id=EXCLUDED.pedido_id, data=EXCLUDED.data, atualizado_em=EXCLUDED.atualizado_em""",
                     (conexao_id, str(s.get("id")), s.get("status"), s.get("tracking_number"),
                      s.get("order_id"), s.get("date_created"), agora))


def puxar_promocoes(conexao_id, token, user_id):
    promos = []
    viu_erro = None
    for st in ("active", "candidate", "paused", "finished"):
        dados, erro = api_get(token, "/sellers/" + str(user_id) + "/promotions",
                              {"promotion_type": "PRICE_DISCOUNT", "status": st, "limit": 50})
        if erro:
            if not viu_erro:
                viu_erro = erro
            continue
        if isinstance(dados, dict):
            lista = dados.get("results") or []
        else:
            lista = dados or []
        for p in lista:
            promos.append(p)
    if viu_erro and not promos:
        registrar_erro(conexao_id, "promocoes", viu_erro)
        return
    agora = int(time.time())
    with banco() as conn:
        executar(conn, "DELETE FROM promocoes WHERE conexao_id=%s", (conexao_id,))
        executar(conn, "DELETE FROM promocoes_itens WHERE conexao_id=%s", (conexao_id,))
        for p in promos:
            itens = p.get("items")
            qtd = len(itens) if isinstance(itens, list) else None
            executar(conn, """INSERT INTO promocoes
                            (conexao_id, promocao_id, tipo, nome, status, inicio, fim, qtd_itens, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, promocao_id) DO UPDATE SET
                              tipo=EXCLUDED.tipo, nome=EXCLUDED.nome, status=EXCLUDED.status,
                              inicio=EXCLUDED.inicio, fim=EXCLUDED.fim, qtd_itens=EXCLUDED.qtd_itens,
                              atualizado_em=EXCLUDED.atualizado_em""",
                     (conexao_id, str(p.get("id")), p.get("type") or p.get("promotion_type"),
                      p.get("name"), p.get("status"), p.get("start_date"), p.get("end_date"), qtd, agora))
            if isinstance(itens, list):
                for it in itens:
                    if isinstance(it, dict):
                        item_id = it.get("id")
                        preco_promo = it.get("price") or it.get("sale_price")
                    else:
                        item_id = it
                        preco_promo = None
                    if item_id:
                        executar(conn, """INSERT INTO promocoes_itens (conexao_id, item_id, promocao_id, preco_promocional, atualizado_em)
                                        VALUES (%s,%s,%s,%s,%s)
                                        ON CONFLICT (conexao_id, item_id, promocao_id) DO UPDATE SET
                                          preco_promocional=EXCLUDED.preco_promocional, atualizado_em=EXCLUDED.atualizado_em""",
                                 (conexao_id, str(item_id), str(p.get("id")), preco_promo, agora))


def puxar_ads(conexao_id, token, user_id):
    cab = {"Authorization": "Bearer " + (token or ""), "Api-Version": "2"}
    base = "/advertising/advertisers/" + str(user_id) + "/product_ads"
    agora = int(time.time())

    campanhas = []
    offset = 0
    while offset < 200:
        try:
            r = requests.get(API + base + "/campaigns/search", headers=cab,
                             params={"limit": 50, "offset": offset}, timeout=25)
            if r.status_code != 200:
                registrar_erro(conexao_id, "ads", "campanhas HTTP " + str(r.status_code) + ": " + r.text[:180])
                break
            dados = r.json()
            resultados = dados.get("results") or []
            campanhas.extend(resultados)
            if len(resultados) < 50:
                break
            offset += len(resultados)
        except Exception as e:
            registrar_erro(conexao_id, "ads", "campanhas: " + str(e))
            break
    with banco() as conn:
        executar(conn, "DELETE FROM ads_campanhas WHERE conexao_id=%s", (conexao_id,))
        for c in campanhas:
            executar(conn, """INSERT INTO ads_campanhas
                            (conexao_id, campanha_id, nome, status, tipo, data_inicio, data_fim, orcamento, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, campanha_id) DO UPDATE SET
                              nome=EXCLUDED.nome, status=EXCLUDED.status, tipo=EXCLUDED.tipo,
                              data_inicio=EXCLUDED.data_inicio, data_fim=EXCLUDED.data_fim,
                              orcamento=EXCLUDED.orcamento, atualizado_em=EXCLUDED.atualizado_em""",
                     (conexao_id, str(c.get("id")), c.get("name"), c.get("status"),
                      c.get("type") or c.get("campaign_type"), c.get("start_date"), c.get("end_date"),
                      c.get("budget") or c.get("daily_budget"), agora))

    ads = []
    offset = 0
    while offset < 200:
        try:
            r = requests.get(API + base + "/ads/search", headers=cab,
                             params={"limit": 50, "offset": offset}, timeout=25)
            if r.status_code != 200:
                registrar_erro(conexao_id, "ads", "anuncios HTTP " + str(r.status_code) + ": " + r.text[:180])
                break
            dados = r.json()
            resultados = dados.get("results") or []
            ads.extend(resultados)
            if len(resultados) < 50:
                break
            offset += len(resultados)
        except Exception as e:
            registrar_erro(conexao_id, "ads", "anuncios: " + str(e))
            break
    with banco() as conn:
        executar(conn, "DELETE FROM ads_metricas WHERE conexao_id=%s", (conexao_id,))
        for ad in ads:
            met = ad.get("metrics") or {}
            executar(conn, """INSERT INTO ads_metricas
                            (conexao_id, ad_id, campanha_id, item_id, impressoes, cliques, ctr, gasto, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, ad_id) DO UPDATE SET
                              campanha_id=EXCLUDED.campanha_id, item_id=EXCLUDED.item_id,
                              impressoes=EXCLUDED.impressoes, cliques=EXCLUDED.cliques,
                              ctr=EXCLUDED.ctr, gasto=EXCLUDED.gasto, atualizado_em=EXCLUDED.atualizado_em""",
                     (conexao_id, str(ad.get("id")), ad.get("campaign_id") or ad.get("ad_group_id"),
                      ad.get("item_id"), met.get("impressions"), met.get("clicks"),
                      met.get("ctr"), met.get("total_spend"), agora))


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
        executar(conn, "DELETE FROM pedidos WHERE conexao_id=%s", (conexao_id,))
        cur = conn.cursor()
        cur.executemany("""INSERT INTO pedidos
                            (conexao_id, pedido_id, status, total, moeda, fechado_em, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, pedido_id) DO UPDATE SET
                              status=EXCLUDED.status, total=EXCLUDED.total, moeda=EXCLUDED.moeda,
                              fechado_em=EXCLUDED.fechado_em, atualizado_em=EXCLUDED.atualizado_em""", lista)


def job_dados():
    with banco() as conn:
        conexoes = consultar(conn, "SELECT * FROM conexoes WHERE status='ativa'")
    for c in conexoes:
        token = token_atual(c)
        if not token:
            continue
        puxar_conta(c["id"], token)
        if c["user_id"]:
            puxar_anuncios(c["id"], token, c["user_id"])
            puxar_pedidos(c["id"], token, c["user_id"])
            puxar_metricas(c["id"], token)
            puxar_perguntas(c["id"], token, c["user_id"])
            puxar_envios(c["id"], token, c["user_id"])
            puxar_promocoes(c["id"], token, c["user_id"])
            puxar_ads(c["id"], token, c["user_id"])
        gravar_historico(c["id"])


iniciar_banco()

scheduler = BackgroundScheduler()
scheduler.add_job(job_refresh, "interval", minutes=30)
scheduler.add_job(job_dados, "interval", minutes=60)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
