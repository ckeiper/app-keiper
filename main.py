import os, time, html, json, datetime, csv, io, threading, smtplib, secrets, hashlib
from email.mime.text import MIMEText
from functools import wraps
from flask import Flask, request, redirect, jsonify, Response, session, send_from_directory
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash
try:
    import openpyxl
except Exception:
    openpyxl = None

CLIENT_ID = os.getenv("ML_CLIENT_ID")
CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ML_REDIRECT_URI")
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave")

API = "https://api.mercadolibre.com"
AUTH_URL = "https://auth.mercadolibre.com.br/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo_Keiper_Consultoria.png")

app = Flask(__name__)
app.secret_key = SECRET_KEY
esc = html.escape

ATUALIZANDO = set()
LOCK_ATUALIZACAO = threading.Lock()
GATILHO_AUTO_SEG = 1800

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


def img_logo(altura=34):
    if os.path.exists(LOGO_PATH):
        return ("<img src='/logo.png' alt='Keiper Consultoria' style='height:"
                + str(altura) + "px;vertical-align:middle;"
                "margin-right:10px;border-radius:8px'>")
    return ""


CSS = """
<style>
* { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',Arial,sans-serif; }
body { background:#f4f6f9; color:#1a1a2e; }
.top { background:#3483FA; color:#fff; padding:18px 32px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; }
.top h1 { font-size:22px; font-weight:700; display:flex; align-items:center; }
.top .brand { font-size:14px; opacity:.9; }
.top a.btn { background:#FFE600; color:#1a1a2e; text-decoration:none; padding:9px 18px; border-radius:8px; font-weight:600; font-size:14px; }
.top a.btn.sair { background:#d64545; color:#fff; }
.wrap { max-width:1300px; margin:28px auto; padding:0 20px; }
.layout { display:flex; gap:20px; align-items:flex-start; }
.menu-lateral { width:210px; flex-shrink:0; background:#fff; border-radius:14px; box-shadow:0 2px 10px rgba(0,0,0,.06); padding:14px; position:sticky; top:16px; }
.menu-lateral .voltar { display:block; font-size:13px; color:#6b7280; text-decoration:none; margin-bottom:10px; font-weight:600; }
.menu-lateral a.item { display:block; padding:9px 12px; border-radius:8px; color:#1a1a2e; text-decoration:none; font-size:14px; font-weight:600; margin-bottom:2px; }
.menu-lateral a.item:hover { background:#f0f4ff; }
.menu-lateral a.item.atual { background:#3483FA; color:#fff; }
.menu-lateral a.item.perigo { color:#d64545; }
.conteudo { flex:1; min-width:0; }
@media (max-width:820px) { .layout { flex-direction:column; } .menu-lateral { width:100%; position:static; } }
.card { background:#fff; border-radius:14px; box-shadow:0 2px 10px rgba(0,0,0,.06); padding:22px; margin-bottom:22px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; }
.stat { background:#fff; border-radius:14px; box-shadow:0 2px 10px rgba(0,0,0,.06); padding:18px; border-left:4px solid #3483FA; }
.stat .num { font-size:24px; font-weight:700; color:#3483FA; }
.stat .lab { font-size:13px; color:#6b7280; margin-top:4px; }
.stat .var { font-size:12px; font-weight:600; margin-top:6px; }
.var.subiu { color:#1a9d5c; }
.var.caiu { color:#d64545; }
.var.estavel { color:#6b7280; }
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
.sucesso { background:#e6f7ee; border:1px solid #b7e4c7; color:#1a9d5c; border-radius:10px; padding:12px 16px; font-size:14px; margin-bottom:14px; }
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
.btn-acoes.roxo { background:#8b5cf6; }
.btn-acoes.roxo:hover { background:#7c3aed; }
.input { width:100%; padding:12px; border:1px solid #d5dbe5; border-radius:8px; font-size:15px; margin-bottom:12px; }
.filtro { display:inline-block; padding:6px 12px; border:1px solid #d5dbe5; border-radius:6px; font-size:13px; margin-right:8px; margin-bottom:8px; }
.filtro-btn { background:#3483FA; color:#fff; border:0; border-radius:6px; padding:7px 16px; font-size:13px; font-weight:600; cursor:pointer; }
.grafico-box { position:relative; height:300px; width:100%; }
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
.campanha-item { border:1px solid #eef1f5; border-radius:10px; padding:14px 16px; margin-bottom:12px; }
.campanha-item .titulo { font-size:15px; font-weight:700; margin-bottom:6px; }
.campanha-item .meta { font-size:12.5px; color:#6b7280; margin-bottom:8px; }
.campanha-item table { margin-top:6px; }
.barra-topo { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:14px; }
.barra-topo h2 { margin:0; }
@media print { .top, .menu-lateral, .btn-acoes { display:none !important; } .layout { display:block; } body { background:#fff; } }
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
function editarRoas(cid, campanhaId){
  var span = document.getElementById('roas-' + cid + '-' + campanhaId);
  if (!span || span.querySelector('input')) { return; }
  var atual = span.textContent.trim();
  var caixa = span.parentNode;
  var input = document.createElement('input');
  input.value = atual;
  input.className = 'input-inline';
  input.type = 'number';
  input.step = '0.1';
  input.style.width = '80px';
  var btn = document.createElement('button');
  btn.textContent = 'OK';
  btn.className = 'btn-pequeno';
  span.style.display = 'none';
  caixa.appendChild(input);
  caixa.appendChild(btn);
  input.focus();
  function salvar(){
    var novo = parseFloat(input.value.replace(',','.'));
    if (isNaN(novo) || novo < 0) { alert('Digite um ROAS válido.'); return; }
    fetch('/salvar_roas/' + cid + '/' + campanhaId, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: 'roas=' + novo
    }).then(function(r){ return r.json(); }).then(function(d){
      if (d.ok) {
        span.textContent = novo.toFixed(1);
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
function gerarSenha(){
  var campo = document.getElementById('campo-senha');
  if (!campo) { return; }
  var chars = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789!@#$%';
  var s = '';
  for (var i = 0; i < 10; i++) { s += chars.charAt(Math.floor(Math.random() * chars.length)); }
  campo.value = s;
}
</script>
"""

def pagina(titulo, corpo):
    topo = "<div class='top'><div><h1>" + img_logo(34) + "Keiper Consultoria</h1>"
    marca = "<div class='brand'>Painel de lojas Mercado Livre</div></div>"
    links = ""
    links += "<a class='btn' href='/'>+ Conectar loja</a></div>"
    cab = "<!doctype html><html><head><meta charset='utf-8'>"
    cab += "<meta name='viewport' content='width=device-width,initial-scale=1'>"
    cab += "<title>" + esc(titulo) + "</title>" + CSS + "</head><body>"
    fim = "<div class='wrap'>" + corpo + "</div>" + SCRIPT + "</body></html>"
    return cab + topo + marca + links + fim


def pagina_loja(titulo, cid, cliente, secao, corpo):
    itens = [
        ("resumo", "📊 Resumo", "/painel/" + str(cid)),
        ("anuncios", "📦 Anúncios", "/anuncios/" + str(cid)),
        ("desempenho", "📈 Desempenho", "/desempenho/" + str(cid)),
        ("demandas", "🟡 Demandas", "/demandas/" + str(cid)),
        ("promocoes", "🏷️ Promoções", "/promocoes/" + str(cid)),
        ("campanhas", "📢 Campanhas", "/campanhas/" + str(cid)),
        ("custos", "💰 Custos", "/custos/" + str(cid)),
        ("vendas", "🛒 Vendas", "/vendas/" + str(cid)),
    ]
    menu = "<div class='menu-lateral'>"
    menu += "<a class='voltar' href='/painel'>← Todas as lojas</a>"
    for chave, rotulo, href in itens:
        classe = "item"
        if secao == chave:
            classe += " atual"
        menu += "<a class='" + classe + "' href='" + href + "'>"
        menu += rotulo + "</a>"
    menu += "<a class='item' href='/atualizar?cid=" + str(cid) + "'>"
    menu += "🔄 Atualizar dados</a>"
    menu += "<a class='item' href='/diagnostico'>🔍 Diagnóstico</a>"
    menu += "<a class='item perigo' href='/excluir/" + str(cid) + "'>"
    menu += "🗑️ Excluir loja</a></div>"
    links = ""
    links += "<a class='btn sair' href='/logout'>Sair</a></div>"
    cab = "<!doctype html><html><head><meta charset='utf-8'>"
    cab += "<meta name='viewport' content='width=device-width,initial-scale=1'>"
    cab += "<title>" + esc(titulo) + "</title>" + CSS
    cab += "</head><body><div class='top' style='position:relative'>"
    cab += "<div><h1>" + img_logo(34) + "Keiper Consultoria</h1></div>"
    cab += ("<div class='brand' style='position:absolute;left:50%;"
            "top:50%;transform:translate(-50%,-50%);font-size:16px;"
            "font-weight:600'>")
    cab += esc(str(cliente)) + "</div>"
    cab += links
    cab += "<div class='wrap'><div class='layout'>" + menu
    cab += "<div class='conteudo'>" + corpo
    cab += "</div></div></div>" + SCRIPT + "</body></html>"
    return cab


FUSO_BR = datetime.timezone(datetime.timedelta(hours=-3))


def hora_br(ts):
    if not ts:
        return "nunca"
    return datetime.datetime.fromtimestamp(ts, FUSO_BR).strftime(
        "%d/%m/%Y %H:%M")


def barra_atualizar(cid, ultima, tipo="resumo"):
    ult_txt = hora_br(ultima)
    return ("<div style='display:flex;gap:12px;align-items:center;"
            "flex-wrap:wrap;margin-bottom:14px'>"
            "<a class='btn-acoes' href='/atualizar/" + tipo + "/" + str(cid) + "'>"
            "🔄 Atualizar agora</a>"
            "<span style='color:#6b7280;font-size:13px'>"
            "Última atualização: " + ult_txt + "</span>"
            "</div>")


def ultima_atualizacao(cid):
    with banco() as conn:
        ult = consultar(conn, "SELECT MAX(atualizado_em) AS ult FROM anuncios WHERE conexao_id=%s", (cid,))
    return ult[0]["ult"] if ult and ult[0]["ult"] else None


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
        try:
            executar(conn, "ALTER TABLE conexoes ADD COLUMN IF NOT EXISTS aliquota_imposto REAL DEFAULT 0")
            executar(conn, "ALTER TABLE conexoes ADD COLUMN IF NOT EXISTS comissao_pct REAL DEFAULT 12")
        except Exception:
            pass
        executar(conn, """CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            nome TEXT,
            tipo TEXT DEFAULT 'cliente',
            conexao_id INTEGER,
            criado_em BIGINT
        )""")
        try:
            executar(conn, "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT")
        except Exception:
            pass
        admin = consultar(conn, "SELECT id FROM usuarios WHERE username=%s", ("admin",))
        if not admin:
            executar(conn, "INSERT INTO usuarios (username, senha_hash, nome, tipo, criado_em) VALUES (%s,%s,%s,%s,%s)",
                     ("admin", generate_password_hash("keiper2026"), "Administrador", "admin", int(time.time())))
        executar(conn, """CREATE TABLE IF NOT EXISTS reset_tokens (
            token_hash TEXT PRIMARY KEY,
            usuario_id INTEGER,
            expira_em BIGINT
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
            custo REAL, sku TEXT,
            UNIQUE(conexao_id, item_id)
        )""")
        try:
            executar(conn, "ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS fotos INTEGER DEFAULT 0")
            executar(conn, "ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS clips INTEGER DEFAULT 0")
            executar(conn, "ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS tags TEXT")
            executar(conn, "ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS peso REAL")
            executar(conn, "ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS custo REAL")
            executar(conn, "ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS sku TEXT")
        except Exception:
            pass
        executar(conn, """CREATE TABLE IF NOT EXISTS pedidos (
            id SERIAL PRIMARY KEY,
            conexao_id INTEGER, pedido_id TEXT, status TEXT,
            total REAL, moeda TEXT, fechado_em TEXT, atualizado_em BIGINT,
            UNIQUE(conexao_id, pedido_id)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS pedidos_itens (
            conexao_id INTEGER, pedido_id TEXT, item_id TEXT,
            quantidade INTEGER, preco_unitario REAL, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, pedido_id, item_id)
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
            pedido_id TEXT, data TEXT, custo_frete REAL, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, envio_id)
        )""")
        try:
            executar(conn, "ALTER TABLE envios ADD COLUMN IF NOT EXISTS custo_frete REAL")
        except Exception:
            pass
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
        try:
            executar(conn, "ALTER TABLE ads_campanhas ADD COLUMN IF NOT EXISTS roas_objetivo REAL")
        except Exception:
            pass
        executar(conn, """CREATE TABLE IF NOT EXISTS ads_metricas (
            conexao_id INTEGER, ad_id TEXT, campanha_id TEXT, item_id TEXT,
            impressoes INTEGER, cliques INTEGER, ctr REAL, gasto REAL, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, ad_id)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS ads_dia (
            conexao_id INTEGER, data TEXT,
            gasto REAL, faturamento REAL, impressoes INTEGER, cliques INTEGER, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, data)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS ads_campanha_dia (
            conexao_id INTEGER, campanha_id TEXT, data TEXT,
            gasto REAL, faturamento REAL, atualizado_em BIGINT,
            PRIMARY KEY (conexao_id, campanha_id, data)
        )""")
        executar(conn, """CREATE TABLE IF NOT EXISTS erros (
            conexao_id INTEGER, categoria TEXT, mensagem TEXT, quando BIGINT,
            PRIMARY KEY (conexao_id, categoria)
        )""")
        # ---------- AUTENTICAÇÃO ----------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect("/login")
        if session.get("tipo") != "admin":
            return pagina("Acesso negado", "<div class='card'><h2>Acesso restrito</h2></div>")
        return f(*args, **kwargs)
    return wrapper


def pode_ver_loja(cid):
    if session.get("tipo") == "admin":
        return True
    return session.get("conexao_id") == cid


def smtp_configurado():
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))


def enviar_email(destino, assunto, corpo_texto):
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    senha = os.getenv("SMTP_PASS")
    if not host or not user or not senha or not destino:
        return False
    porta = int(os.getenv("SMTP_PORT", "587"))
    de = os.getenv("SMTP_FROM", user)
    msg = MIMEText(corpo_texto, "plain", "utf-8")
    msg["Subject"] = assunto
    msg["From"] = de
    msg["To"] = destino
    try:
        with smtplib.SMTP(host, porta) as s:
            s.starttls()
            s.login(user, senha)
            s.sendmail(de, [destino], msg.as_string())
        return True
    except Exception:
        return False


def criar_token_reset(usuario_id):
    token = secrets.token_urlsafe(32)
    th = hashlib.sha256(token.encode()).hexdigest()
    with banco() as conn:
        executar(conn, "INSERT INTO reset_tokens (token_hash, usuario_id, expira_em) VALUES (%s,%s,%s)",
                 (th, usuario_id, int(time.time()) + 1800))
    return token


@app.route("/logo.png")
def logo_arquivo():
    return send_from_directory(BASE_DIR, "logo_Keiper_Consultoria.png")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        senha = request.form.get("senha") or ""
        with banco() as conn:
            u = consultar(conn, "SELECT * FROM usuarios WHERE username=%s", (username,))
        u = u[0] if u else None
        if u and check_password_hash(u["senha_hash"], senha):
            session["usuario_id"] = u["id"]
            session["username"] = u["username"]
            session["nome"] = u["nome"]
            session["tipo"] = u["tipo"]
            session["conexao_id"] = u["conexao_id"]
            if u["tipo"] == "cliente" and u["conexao_id"]:
                return redirect("/painel/" + str(u["conexao_id"]))
            return redirect("/painel")
        corpo = ("<div class='card' style='max-width:420px;margin:60px auto;text-align:center'>"
                 + img_logo(64) + "<h2>Login</h2>"
                 + "<div class='aviso'>Usuário ou senha incorretos.</div>"
                 + form_login() + "</div>")
        return pagina("Login", corpo)
    corpo = ("<div class='card' style='max-width:420px;margin:60px auto;text-align:center'>"
             + img_logo(64) + "<h2>Login</h2>"
             + "<div class='sub'>Acesse o painel Keiper Consultoria</div>"
             + form_login() + "</div>")
    return pagina("Login", corpo)


def form_login():
    return ("<form method='post' action='/login' style='margin-top:12px'>"
            "<input name='username' required placeholder='Usuário' class='input'>"
            "<input type='password' name='senha' required placeholder='Senha' class='input'>"
            "<button class='btn-salvar' style='width:100%'>Entrar</button></form>"
            "<p style='margin-top:12px'><a class='link' href='/recuperar'>Esqueci minha senha</a></p>")


@app.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if request.method == "POST":
        ident = (request.form.get("ident") or "").strip()
        if not smtp_configurado():
            corpo = ("<div class='card' style='max-width:460px;margin:60px auto;text-align:center'>"
                     "<h2>Recuperar senha</h2>"
                     "<div class='aviso'>A recuperação por e-mail <b>não está configurada</b> "
                     "no servidor. Peça ao administrador para redefinir sua senha "
                     "na tela de Usuários.</div>"
                     "<p><a class='link' href='/login'>← Voltar ao login</a></p></div>")
            return pagina("Recuperar senha", corpo)
        with banco() as conn:
            u = consultar(conn, "SELECT * FROM usuarios WHERE email=%s OR username=%s",
                          (ident, ident))
        u = u[0] if u else None
        if u and u["email"]:
            token = criar_token_reset(u["id"])
            link = request.url_root.rstrip("/") + "/redefinir/" + token
            texto = ("Olá " + (u["nome"] or u["username"]) + ",\n\n"
                     "Recebemos um pedido de redefinição de senha do painel "
                     "Keiper Consultoria.\n"
                     "Use o link abaixo para criar uma nova senha "
                     "(válido por 30 minutos):\n\n"
                     + link + "\n\nSe não foi você quem pediu, ignore este e-mail.")
            enviar_email(u["email"], "Redefinição de senha — Keiper Consultoria", texto)
        corpo = ("<div class='card' style='max-width:460px;margin:60px auto;text-align:center'>"
                 "<h2>Recuperar senha</h2>"
                 "<div class='sucesso'>Se este e-mail estiver cadastrado, você receberá "
                 "o link de redefinição em instantes. Verifique também a caixa de spam.</div>"
                 "<p><a class='link' href='/login'>← Voltar ao login</a></p></div>")
        return pagina("Recuperar senha", corpo)
    corpo = ("<div class='card' style='max-width:460px;margin:60px auto;text-align:center'>"
             "<h2>Recuperar senha</h2>"
             "<div class='sub'>Digite seu usuário ou e-mail cadastrado. "
             "Enviaremos um link para criar uma nova senha.</div>"
             "<form method='post' action='/recuperar'>"
             "<input name='ident' required placeholder='Usuário ou e-mail' class='input'>"
             "<button class='btn-salvar' style='width:100%'>Enviar link</button></form>"
             "<p style='margin-top:12px'><a class='link' href='/login'>← Voltar ao login</a></p></div>")
    return pagina("Recuperar senha", corpo)


@app.route("/redefinir/<token>", methods=["GET", "POST"])
def redefinir(token):
    th = hashlib.sha256(token.encode()).hexdigest()
    with banco() as conn:
        r = consultar(conn, "SELECT * FROM reset_tokens WHERE token_hash=%s", (th,))
    r = r[0] if r else None
    if not r or r["expira_em"] < int(time.time()):
        corpo = ("<div class='card' style='max-width:460px;margin:60px auto;text-align:center'>"
                 "<h2>Link inválido</h2>"
                 "<div class='aviso'>Este link de redefinição é inválido ou expirou. "
                 "Solicite um novo.</div>"
                 "<p><a class='link' href='/recuperar'>Solicitar novo link</a></p></div>")
        return pagina("Redefinir senha", corpo)
    erro = ""
    if request.method == "POST":
        senha = request.form.get("senha") or ""
        if len(senha) < 6:
            erro = "A senha precisa ter pelo menos 6 caracteres."
        else:
            with banco() as conn:
                executar(conn, "UPDATE usuarios SET senha_hash=%s WHERE id=%s",
                         (generate_password_hash(senha), r["usuario_id"]))
                executar(conn, "DELETE FROM reset_tokens WHERE token_hash=%s", (th,))
            corpo = ("<div class='card' style='max-width:460px;margin:60px auto;text-align:center'>"
                     "<h2>Senha alterada com sucesso!</h2>"
                     "<div class='sucesso'>Agora você pode entrar com a nova senha.</div>"
                     "<p><a class='link' href='/login'>Ir para o login</a></p></div>")
            return pagina("Senha alterada", corpo)
    corpo = ("<div class='card' style='max-width:460px;margin:60px auto;text-align:center'>"
             "<h2>Criar nova senha</h2>"
             + ("<div class='aviso'>" + esc(erro) + "</div>" if erro else "")
             + "<form method='post' action='/redefinir/" + esc(token) + "'>"
             "<input type='password' name='senha' required "
             "placeholder='Nova senha (mín. 6 caracteres)' class='input'>"
             "<button class='btn-salvar' style='width:100%'>Salvar senha</button></form></div>")
    return pagina("Redefinir senha", corpo)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
def home():
    if "usuario_id" not in session:
        return redirect("/login")
    return redirect("/painel")


@app.route("/status")
@login_required
def status():
    with banco() as conn:
        if session.get("tipo") == "admin":
            linhas = consultar(conn, "SELECT cliente, user_id, status, expires_at FROM conexoes")
        else:
            linhas = consultar(conn, "SELECT cliente, user_id, status, expires_at "
                                     "FROM conexoes WHERE id=%s",
                               (session.get("conexao_id"),))
    linhas_html = ""
    for l in linhas:
        quando = "-"
        if l["expires_at"]:
            quando = hora_br(l["expires_at"])
        tag = "tag " + (l["status"] if l["status"] in ("ativa", "pausado", "expirada") else "normal")
        linhas_html += ("<tr><td>" + esc(str(l["cliente"])) + "</td><td>"
                        + str(l["user_id"]) + "</td><td><span class='" + tag + "'>"
                        + esc(l["status"]) + "</span></td><td>" + quando + "</td></tr>")
    corpo = ("<div class='card'><h2>Conexões</h2>"
             "<div class='sub'>Status de cada loja conectada</div>"
             "<table><thead><tr><th>Cliente</th><th>Loja</th><th>Status</th>"
             "<th>Expira em</th></tr></thead>"
             "<tbody>" + linhas_html + "</tbody></table></div>")
    return pagina("Status", corpo)


@app.route("/renomear/<int:cid>", methods=["POST"])
@login_required
def renomear(cid):
    if not pode_ver_loja(cid):
        return jsonify({"ok": False}), 403
    novo = (request.form.get("cliente") or "").strip()
    if not novo:
        return jsonify({"ok": False}), 400
    with banco() as conn:
        executar(conn, "UPDATE conexoes SET cliente=%s WHERE id=%s", (novo, cid))
    return jsonify({"ok": True})


@app.route("/salvar_custo/<int:cid>/<item_id>", methods=["POST"])
@login_required
def salvar_custo(cid, item_id):
    if not pode_ver_loja(cid):
        return jsonify({"ok": False}), 403
    try:
        custo = float((request.form.get("custo") or "0").replace(",", "."))
    except Exception:
        return jsonify({"ok": False}), 400
    if custo < 0:
        return jsonify({"ok": False}), 400
    with banco() as conn:
        executar(conn, "UPDATE anuncios SET custo=%s WHERE conexao_id=%s AND item_id=%s",
                 (custo, cid, item_id))
    return jsonify({"ok": True})


@app.route("/salvar_roas/<int:cid>/<campanha_id>", methods=["POST"])
@login_required
def salvar_roas(cid, campanha_id):
    if not pode_ver_loja(cid):
        return jsonify({"ok": False}), 403
    try:
        roas = float((request.form.get("roas") or "0").replace(",", "."))
    except Exception:
        return jsonify({"ok": False}), 400
    if roas < 0:
        return jsonify({"ok": False}), 400
    with banco() as conn:
        executar(conn, "UPDATE ads_campanhas SET roas_objetivo=%s "
                       "WHERE conexao_id=%s AND campanha_id=%s",
                 (roas, cid, campanha_id))
    return jsonify({"ok": True})


@app.route("/salvar_config/<int:cid>", methods=["POST"])
@login_required
def salvar_config(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado", "<div class='card'><h2>Acesso restrito</h2></div>")
    try:
        aliquota = float((request.form.get("aliquota") or "0").replace(",", "."))
    except Exception:
        aliquota = 0
    try:
        comissao = float((request.form.get("comissao") or "0").replace(",", "."))
    except Exception:
        comissao = 12
    with banco() as conn:
        executar(conn, "UPDATE conexoes SET aliquota_imposto=%s, comissao_pct=%s WHERE id=%s",
                 (aliquota, comissao, cid))
    return redirect("/custos/" + str(cid))


@app.route("/upload_custos/<int:cid>", methods=["POST"])
@login_required
def upload_custos(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado", "<div class='card'><h2>Acesso restrito</h2></div>")
    if openpyxl is None:
        return redirect("/custos/" + str(cid) + "?erro=biblioteca")
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        return redirect("/custos/" + str(cid) + "?erro=sem_arquivo")
    try:
        wb = openpyxl.load_workbook(arquivo, data_only=True, read_only=True)
        ws = wb.active
    except Exception:
        return redirect("/custos/" + str(cid) + "?erro=arquivo_invalido")
    with banco() as conn:
        anuncios = consultar(conn, "SELECT item_id, sku FROM anuncios WHERE conexao_id=%s", (cid,))
    mapa = {}
    for a in anuncios:
        if a["sku"]:
            mapa[str(a["sku"]).strip().upper()] = a["item_id"]
        mapa[str(a["item_id"]).strip().upper()] = a["item_id"]
    atualizados = 0
    nao_achados = []
    for row in ws.iter_rows(min_row=2, max_col=2, values_only=True):
        sku = row[0] if len(row) > 0 else None
        custo = row[1] if len(row) > 1 else None
        if sku is None or custo is None:
            continue
        try:
            custo_v = float(str(custo).replace("R$", "").replace(" ", "").replace(",", "."))
        except Exception:
            continue
        item_id = mapa.get(str(sku).strip().upper())
        if item_id:
            with banco() as conn:
                executar(conn, "UPDATE anuncios SET custo=%s "
                               "WHERE conexao_id=%s AND item_id=%s",
                         (custo_v, cid, item_id))
            atualizados += 1
        else:
            nao_achados.append(str(sku))
    try:
        wb.close()
    except Exception:
        pass
    return redirect("/custos/" + str(cid) + "?ok=" + str(atualizados)
                    + "&faltam=" + str(len(nao_achados)))


@app.route("/modelo_custos/<int:cid>")
@login_required
def modelo_custos(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado", "<div class='card'><h2>Acesso restrito</h2></div>")
    if openpyxl is None:
        return pagina("Erro", "<div class='card'><h2>Biblioteca de Excel não instalada</h2>"
                      "<div class='sub'>Adicione 'openpyxl' no requirements.txt "
                      "e faça o deploy de novo.</div></div>")
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if not c:
            return "Loja não encontrada", 404
        anuncios = consultar(conn, "SELECT item_id, sku, titulo FROM anuncios "
                                   "WHERE conexao_id=%s ORDER BY titulo", (cid,))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Custos"
    ws.append(["SKU", "Custo"])
    for a in anuncios:
        ws.append([a["sku"] or a["item_id"], None])
    buf = io.BytesIO()
    wb.save(buf)
    nome = "modelo_custos_" + str(c["cliente"]).replace(" ", "_") + ".xlsx"
    return Response(buf.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=" + nome})


@app.route("/custos/<int:cid>")
@login_required
def custos(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado", "<div class='card'><h2>Acesso restrito</h2></div>")
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if c:
            anuncios = consultar(conn, "SELECT * FROM anuncios WHERE conexao_id=%s "
                                       "ORDER BY titulo", (cid,))
    if not c:
        return pagina("Não encontrada", "<div class='card'><h2>Loja não encontrada</h2></div>")
    ok = request.args.get("ok")
    faltam = request.args.get("faltam")
    erro = request.args.get("erro")
    aliquota = c["aliquota_imposto"] if c["aliquota_imposto"] is not None else 0
    comissao = c["comissao_pct"] if c["comissao_pct"] is not None else 12
    ultima = ultima_atualizacao(cid)
    corpo = "<h2 style='margin-bottom:10px'>Custos</h2>" + barra_atualizar(cid, ultima, "custos")
    if erro == "sem_arquivo":
        corpo += "<div class='aviso'>Nenhum arquivo selecionado. " \
                 "Escolha a planilha e clique em Importar.</div>"
    elif erro == "arquivo_invalido":
        corpo += "<div class='aviso'>Não consegui ler o arquivo. " \
                 "Use um Excel no formato .xlsx.</div>"
    elif erro == "biblioteca":
        corpo += "<div class='aviso'>A biblioteca de Excel não está instalada. " \
                 "Adicione 'openpyxl' no requirements.txt e faça o deploy de novo.</div>"
    if ok is not None:
        msg = "<b>Importação concluída:</b> " + ok + " custo(s) atualizado(s)."
        if faltam and faltam != "0":
            msg += (" " + faltam + " SKU(s) não encontrados nos anúncios desta loja "
                    "(confira a grafia ou use o código MLB).")
        corpo += "<div class='sucesso'>" + msg + "</div>"
    com_custo = sum(1 for a in anuncios if a["custo"] is not None)
    corpo += ("<div class='grid' style='margin-bottom:18px'>"
              "<div class='stat'><div class='num'>" + str(len(anuncios))
              + "</div><div class='lab'>Anúncios na loja</div></div>"
              "<div class='stat'><div class='num'>" + str(com_custo)
              + "</div><div class='lab'>Com custo cadastrado</div></div>"
              "<div class='stat'><div class='num'>" + str(len(anuncios) - com_custo)
              + "</div><div class='lab'>Falta cadastrar custo</div></div>"
              "</div>")
    corpo += ("<div class='card'><h2>Configuração da loja</h2>"
              "<div class='sub'>Usadas no cálculo da Margem de Contribuição "
              "na tela de Vendas</div>"
              "<form method='post' action='/salvar_config/" + str(cid)
              + "' style='display:flex;flex-wrap:wrap;gap:10px;align-items:center'>"
              "<label style='font-size:13px'>Alíquota de imposto (%):</label>"
              "<input type='number' step='0.01' min='0' name='aliquota' value='"
              + str(aliquota) + "' class='filtro' style='width:100px'>"
              "<label style='font-size:13px'>Comissão ML (%):</label>"
              "<input type='number' step='0.01' min='0' name='comissao' value='"
              + str(comissao) + "' class='filtro' style='width:100px'>"
              "<button class='filtro-btn'>Salvar</button>"
              "</form></div>")
    corpo += ("<div class='card'><h2>Importar custos em massa (Excel)</h2>"
              "<div class='sub'>Planilha com a <b>1ª coluna = SKU</b> e a "
              "<b>2ª coluna = custo (R$)</b>. Pode usar o SKU cadastrado no anúncio "
              "ou o código MLB do item. A primeira linha é o cabeçalho e é ignorada.</div>"
              "<form method='post' action='/upload_custos/" + str(cid)
              + "' enctype='multipart/form-data' "
              "style='display:flex;flex-wrap:wrap;gap:10px;align-items:center'>"
              "<input type='file' name='arquivo' accept='.xlsx' required "
              "class='filtro' style='padding:6px'>"
              "<button class='filtro-btn'>Importar</button>"
              "</form>"
              "<div style='margin-top:10px'><a class='link' href='/modelo_custos/"
              + str(cid) + "'>⬇ Baixar modelo (Excel) já com os SKUs da loja "
              "— preencha a coluna Custo e suba de volta</a></div>"
              "</div>")
    if not anuncios:
        corpo += ("<div class='card' style='text-align:center;padding:40px'>"
                  "<h2>Nenhum anúncio carregado ainda</h2>"
                  "<div class='sub'>Use 'Atualizar dados' no menu lateral "
                  "para buscar os anúncios da loja</div></div>")
        return pagina_loja("Custos", cid, c["cliente"], "custos", corpo)
    linhas_html = ""
    for a in anuncios:
        if a["sku"]:
            sku_txt = esc(str(a["sku"]))
        else:
            sku_txt = "<span class='tag sem'>—</span>"
        if a["custo"] is not None:
            custo_html = ("<span id='custo-" + str(cid) + "-" + str(a["item_id"])
                          + "'>R$ %.2f</span>" % a["custo"])
        else:
            custo_html = ("<span id='custo-" + str(cid) + "-" + str(a["item_id"])
                          + "'><a class='link' href='#' onclick='editarCusto("
                          + str(cid) + ", \"" + str(a["item_id"])
                          + "\"); return false;'>+ definir</a></span>")
        linhas_html += ("<tr><td>" + sku_txt + "</td>"
                        "<td><b>" + esc(str(a["titulo"]))
                        + "</b><br><small class='muted'>" + str(a["item_id"]) + "</small></td>"
                        "<td>R$ %.2f" % (a["preco"] or 0) + "</td>"
                        "<td>" + custo_html + "</td></tr>")
    corpo += ("<div class='card'><h2>Custos por anúncio <span class='badge'>"
              + str(len(anuncios)) + "</span></h2>"
              "<div class='sub'>Clique em '+ definir' ou no valor para editar "
              "o custo de cada anúncio</div>"
              "<div style='overflow-x:auto'><table>"
              "<thead><tr><th>SKU</th><th>Anúncio</th><th>Preço</th>"
              "<th>Custo</th></tr></thead>"
              "<tbody>" + linhas_html + "</tbody></table></div>"
              "<div class='muted'>O custo é usado no cálculo da Margem de Contribuição "
              "(tela de Vendas) e na análise de promoções.</div></div>")
    return pagina_loja("Custos", cid, c["cliente"], "custos", corpo)


def calcular_vendas(cid):
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if not c:
            return None, []
        pedidos = consultar(conn, "SELECT * FROM pedidos WHERE conexao_id=%s "
                                  "AND fechado_em IS NOT NULL "
                                  "ORDER BY fechado_em DESC LIMIT 100", (cid,))
        itens = consultar(conn, """SELECT pi.pedido_id, pi.quantidade, pi.preco_unitario,
                                          a.custo, a.peso
                                   FROM pedidos_itens pi
                                   LEFT JOIN anuncios a
                                     ON a.conexao_id=pi.conexao_id AND a.item_id=pi.item_id
                                   WHERE pi.conexao_id=%s""", (cid,))
        envios = consultar(conn, "SELECT pedido_id, custo_frete FROM envios "
                                 "WHERE conexao_id=%s AND custo_frete IS NOT NULL", (cid,))
    aliquota_pct = c["aliquota_imposto"] if c["aliquota_imposto"] is not None else 0
    comissao_pct = c["comissao_pct"] if c["comissao_pct"] is not None else 12
    aliquota = aliquota_pct / 100.0
    comissao = comissao_pct / 100.0
    itens_por_pedido = {}
    for it in itens:
        itens_por_pedido.setdefault(it["pedido_id"], []).append(it)
    frete_por_pedido = {}
    for e in envios:
        pid = e["pedido_id"]
        if pid and pid not in frete_por_pedido:
            frete_por_pedido[pid] = e["custo_frete"] or 0
    vendas = []
    for p in pedidos:
        receita = p["total"] or 0
        itens_p = itens_por_pedido.get(p["pedido_id"], [])
        custo_prod = 0.0
        frete = 0.0
        sem_custo = False
        sem_itens = not itens_p
        for it in itens_p:
            qtd = it["quantidade"] or 1
            pu = it["preco_unitario"] or 0
            if it["custo"] is None:
                sem_custo = True
            else:
                custo_prod += (it["custo"] or 0) * qtd
            f = frete_esperado(pu, it["peso"])
            if f is not None:
                frete += f * qtd
        frete_fonte = "estimado"
        frete_real = frete_por_pedido.get(p["pedido_id"])
        if frete_real is not None:
            frete = frete_real
            frete_fonte = "real"
        imposto = receita * aliquota
        comissao_v = receita * comissao
        mc = receita - custo_prod - imposto - comissao_v - frete
        mc_pct = (mc * 100.0 / receita) if receita else 0
        vendas.append({
            "pedido_id": p["pedido_id"],
            "data": str(p["fechado_em"])[:16].replace("T", " "),
            "status": str(p["status"]),
            "receita": receita,
            "custo_prod": custo_prod,
            "imposto": imposto,
            "comissao": comissao_v,
            "frete": frete,
            "frete_fonte": frete_fonte,
            "mc": mc,
            "mc_pct": mc_pct,
            "sem_itens": sem_itens,
            "sem_custo": sem_custo,
        })
    return c, vendas


@app.route("/vendas/<int:cid>")
@login_required
def vendas(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado", "<div class='card'><h2>Acesso restrito</h2></div>")
    c, vendas = calcular_vendas(cid)
    if not c:
        return pagina("Não encontrada", "<div class='card'><h2>Loja não encontrada</h2></div>")
    aliquota_pct = c["aliquota_imposto"] if c["aliquota_imposto"] is not None else 0
    comissao_pct = c["comissao_pct"] if c["comissao_pct"] is not None else 12
    ultima = ultima_atualizacao(cid)
    corpo = ("<div class='barra-topo'><h2>Vendas e Margem de Contribuição</h2>"
             "<div style='display:flex;gap:10px;flex-wrap:wrap;align-items:center'>"
             "<a class='btn-acoes cinza' href='/exportar_vendas/"
             + str(cid) + "'>⬇ Exportar CSV</a>"
             "</div></div>"
             + barra_atualizar(cid, ultima, "vendas"))
    if not vendas:
        corpo += ("<div class='card' style='text-align:center;padding:40px'>"
                  "<h2>Nenhuma venda carregada ainda</h2>"
                  "<div class='sub'>Use 'Atualizar agora' acima para buscar os pedidos "
                  "da loja. As vendas analisadas são os pedidos fechados.</div></div>")
        return pagina_loja("Vendas", cid, c["cliente"], "vendas", corpo)
    analisadas = sum(1 for v in vendas if not v["sem_itens"] and not v["sem_custo"])
    pendentes = len(vendas) - analisadas
    tot_receita = sum(v["receita"] for v in vendas
                      if not v["sem_itens"] and not v["sem_custo"])
    tot_mc = sum(v["mc"] for v in vendas
                 if not v["sem_itens"] and not v["sem_custo"])
    mc_medio = (tot_mc * 100.0 / tot_receita) if tot_receita else 0
    com_frete_real = sum(1 for v in vendas if v["frete_fonte"] == "real")
    corpo += ("<div class='grid' style='margin-bottom:18px'>"
              "<div class='stat'><div class='num'>R$ %.2f" % tot_receita
              + "</div><div class='lab'>Receita das vendas analisadas</div></div>"
              "<div class='stat'><div class='num'>R$ %.2f" % tot_mc
              + "</div><div class='lab'>Margem de Contribuição total</div></div>"
              "<div class='stat'><div class='num'>" + ("%.1f%%" % mc_medio)
              + "</div><div class='lab'>MG média (MC ÷ Receita)</div></div>"
              "<div class='stat'><div class='num'>" + str(pendentes)
              + "</div><div class='lab'>Vendas sem custo cadastrado</div></div>"
              "</div>")
    linhas_html = ""
    for v in vendas:
        if v["sem_itens"]:
            mc_html = "<span class='tag sem'>itens não registrados</span>"
        elif v["sem_custo"]:
            mc_html = "<a class='link' href='/custos/" + str(cid) + "'>cadastre o custo</a>"
        elif v["mc_pct"] <= 0:
            mc_html = "<span class='alerta urgente'>" + ("%.1f%% (R$ %.2f)"
                      % (v["mc_pct"], v["mc"])) + "</span>"
        elif v["mc_pct"] < 20:
            mc_html = "<span class='alerta atencao'>" + ("%.1f%% (R$ %.2f)"
                      % (v["mc_pct"], v["mc"])) + "</span>"
        else:
            mc_html = "<span class='alerta ok'>" + ("%.1f%% (R$ %.2f)"
                      % (v["mc_pct"], v["mc"])) + "</span>"
        fonte = "<small class='muted'>real</small>" if v["frete_fonte"] == "real" \
            else "<small class='muted'>est.</small>"
        if v["frete"]:
            frete_html = ("R$ %.2f " % v["frete"]) + fonte
        else:
            frete_html = "<span class='tag sem'>—</span>"
        if v["sem_itens"]:
            custo_html = "<span class='tag sem'>—</span>"
        else:
            custo_html = "R$ %.2f" % v["custo_prod"]
        linhas_html += ("<tr>"
                        "<td><b>" + str(v["pedido_id"]) + "</b><br>"
                        "<small class='muted'>" + esc(v["data"]) + "</small></td>"
                        "<td>" + esc(v["status"]) + "</td>"
                        "<td>R$ %.2f" % v["receita"] + "</td>"
                        "<td>" + custo_html + "</td>"
                        "<td>R$ %.2f" % v["imposto"] + "</td>"
                        "<td>R$ %.2f" % v["comissao"] + "</td>"
                        "<td>" + frete_html + "</td>"
                        "<td>" + mc_html + "</td>"
                        "</tr>")
    corpo += ("<div class='card'><h2>Vendas <span class='badge'>"
              + str(len(vendas)) + "</span></h2>"
              "<div class='sub'>MG = Receita − Custo dos produtos − Imposto ("
              + str(aliquota_pct) + "%) − Comissão ML (" + str(comissao_pct)
              + "%) − Frete. Entre parênteses, o lucro em R$ de cada venda.</div>"
              "<div style='overflow-x:auto'><table>"
              "<thead><tr><th>Pedido</th><th>Status</th><th>Receita</th>"
              "<th>Custo produtos</th><th>Imposto</th><th>Comissão</th>"
              "<th>Frete</th><th>MG (Lucro R$)</th></tr></thead>"
              "<tbody>" + linhas_html + "</tbody></table></div>"
              "<div class='muted'>Frete: usa o <b>valor real</b> do envio quando o "
              "Mercado Livre informa (" + str(com_frete_real)
              + " vendas com frete real); senão, estimativa pela tabela oficial do ML "
              "(marcado como 'est.'). Imposto e comissão são configurados na "
              "<a class='link' href='/custos/" + str(cid) + "'>tela de Custos</a>.</div></div>")
    return pagina_loja("Vendas", cid, c["cliente"], "vendas", corpo)


@app.route("/exportar_vendas/<int:cid>")
@login_required
def exportar_vendas(cid):
    if not pode_ver_loja(cid):
        return "Acesso negado", 403
    c, vendas = calcular_vendas(cid)
    if not c:
        return "Loja não encontrada", 404
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Pedido", "Data", "Status", "Receita", "Custo produtos",
                     "Imposto", "Comissao", "Frete", "Fonte frete", "MC %", "Lucro R$"])
    for v in vendas:
        writer.writerow([v["pedido_id"], v["data"], v["status"],
                         ("%.2f" % v["receita"]).replace(".", ","),
                         ("%.2f" % v["custo_prod"]).replace(".", ","),
                         ("%.2f" % v["imposto"]).replace(".", ","),
                         ("%.2f" % v["comissao"]).replace(".", ","),
                         ("%.2f" % v["frete"]).replace(".", ","),
                         v["frete_fonte"],
                         ("%.1f" % v["mc_pct"]).replace(".", ","),
                         ("%.2f" % v["mc"]).replace(".", ",")])
    nome_arq = "vendas_" + str(c["cliente"]).replace(" ", "_") + ".csv"
    return Response(buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=" + nome_arq})
def executar_atualizacao_bg(cid):
    try:
        executar_atualizacao(cid)
    except Exception as e:
        try:
            registrar_erro(cid, "atualizacao", str(e)[:200])
        except Exception:
            pass
    finally:
        with LOCK_ATUALIZACAO:
            ATUALIZANDO.discard(cid)    
@app.route("/diagnostico")
@login_required
def diagnostico():
    with banco() as conn:
        if session.get("tipo") == "admin":
            lojas = consultar(conn, "SELECT id, cliente, status "
                                    "FROM conexoes ORDER BY cliente")
            erros = consultar(conn, "SELECT * FROM erros "
                                    "ORDER BY quando DESC")
        else:
            lojas = consultar(conn, "SELECT id, cliente, status "
                                    "FROM conexoes WHERE id=%s",
                              (session.get("conexao_id"),))
            erros = consultar(conn, "SELECT * FROM erros "
                                    "WHERE conexao_id=%s ORDER BY quando DESC",
                              (session.get("conexao_id"),))
    corpo = ("<p style='margin-bottom:10px'><a class='link' href='/painel'>"
             "← Voltar ao painel</a></p>"
             "<h2 style='margin-bottom:14px'>Diagnóstico</h2>")
    if FILA_ATUALIZACAO:
        fila_txt = str(len(FILA_ATUALIZACAO)) + " na fila"
    else:
        fila_txt = "vazia"
    corpo += ("<div class='grid' style='margin-bottom:18px'>"
              "<div class='stat'><div class='num'>" + fila_txt
              + "</div><div class='lab'>Fila de atualização</div></div>"
              "</div>")
    linhas = ""
    for l in lojas:
        linhas += ("<tr><td><b>" + esc(str(l["cliente"])) + "</b></td>"
                   "<td>" + esc(str(l["status"])) + "</td><td>"
                   + hora_br(ultima_atualizacao(l["id"])) + "</td></tr>")
    corpo += ("<div class='card'><h2>Última atualização por conta</h2>"
              "<table><thead><tr><th>Conta</th><th>Status</th>"
              "<th>Última atualização</th></tr></thead><tbody>"
              + linhas + "</tbody></table></div>")
    linhas_e = ""
    for e in erros:
        linhas_e += ("<tr><td>" + esc(str(e["categoria"])) + "</td>"
                     "<td>" + esc(str(e["mensagem"])) + "</td><td>"
                     + hora_br(e["quando"]) + "</td></tr>")
    if not linhas_e:
        linhas_e = ("<tr><td colspan='3'><span class='alerta ok'>"
                    "Nenhum erro registrado</span></td></tr>")
    corpo += ("<div class='card'><h2>Erros de atualização</h2>"
              "<table><thead><tr><th>Categoria</th><th>Mensagem</th>"
              "<th>Quando</th></tr></thead><tbody>"
              + linhas_e + "</tbody></table></div>")
    return pagina("Diagnóstico", corpo)
FILA_ATUALIZACAO = []
LOCK_FILA = threading.Lock()
WORKER_VIVO = False


def enfileirar_atualizacao(cid):
    global WORKER_VIVO
    with LOCK_FILA:
        if cid in FILA_ATUALIZACAO:
            return False
        FILA_ATUALIZACAO.append(cid)
        if WORKER_VIVO:
            return True
        WORKER_VIVO = True
    threading.Thread(target=processar_fila, daemon=True).start()
    return True


def processar_fila():
    global WORKER_VIVO
    while True:
        with LOCK_FILA:
            if not FILA_ATUALIZACAO:
                WORKER_VIVO = False
                return
            cid = FILA_ATUALIZACAO[0]
        try:
            executar_atualizacao(cid)
        except Exception:
            pass
        with LOCK_FILA:
            try:
                FILA_ATUALIZACAO.remove(cid)
            except Exception:
                pass    
@app.route("/painel")
@login_required
def painel():
    hoje_iso = datetime.date.today().isoformat()
    ontem_iso = (datetime.date.today()
                 - datetime.timedelta(days=1)).isoformat()
    ini7 = (datetime.date.today()
            - datetime.timedelta(days=6)).isoformat()
    with banco() as conn:
        if session.get("tipo") == "admin":
            lojas = consultar(conn, "SELECT id, cliente, status "
                                    "FROM conexoes ORDER BY cliente")
        else:
            lojas = consultar(conn, "SELECT id, cliente, status "
                                    "FROM conexoes WHERE id=%s "
                                    "ORDER BY cliente",
                              (session.get("conexao_id"),))
        disparou = False
    agora = int(time.time())
    for l in lojas:
        ult = ultima_atualizacao(l["id"])
        if ult is None or (agora - ult) > GATILHO_AUTO_SEG:
            if enfileirar_atualizacao(l["id"]):
                disparou = True
    if not lojas:
        corpo = ("<div class='card' style='text-align:center;padding:50px'>"
                 "<h2>Nenhuma loja conectada ainda</h2>"
                 "<div class='sub'>Comece conectando a primeira loja</div>"
                 "<p><a class='link' href='/'>Conectar loja</a></p></div>")
        return pagina("Painel", corpo)
    ids = [l["id"] for l in lojas]
    fat_hoje = fat_ontem = 0.0
    vendas_hoje = vendas_ontem = 0
    visitas_total = 0
    gasto_hoje = None
    gasto_total = 0.0
    fat_geral = 0.0
    g_fat = []
    g_vis = []
    if ids:
        ph = ",".join(["%s"] * len(ids))
        with banco() as conn:
            r = consultar(conn, "SELECT COALESCE(SUM(total),0) AS t, "
                                "COUNT(*) AS n FROM pedidos "
                                "WHERE conexao_id IN (" + ph + ") "
                                "AND fechado_em IS NOT NULL "
                                "AND SUBSTRING(fechado_em,1,10)=%s",
                          (*ids, hoje_iso))
            fat_hoje = r[0]["t"] or 0
            vendas_hoje = r[0]["n"] or 0
            r = consultar(conn, "SELECT COALESCE(SUM(total),0) AS t, "
                                "COUNT(*) AS n FROM pedidos "
                                "WHERE conexao_id IN (" + ph + ") "
                                "AND fechado_em IS NOT NULL "
                                "AND SUBSTRING(fechado_em,1,10)=%s",
                          (*ids, ontem_iso))
            fat_ontem = r[0]["t"] or 0
            vendas_ontem = r[0]["n"] or 0
            r = consultar(conn, "SELECT COALESCE(SUM(visitas),0) AS v "
                                "FROM metricas "
                                "WHERE conexao_id IN (" + ph + ")", ids)
            visitas_total = r[0]["v"] or 0
            r = consultar(conn, "SELECT COALESCE(SUM(gasto),0) AS g "
                                "FROM ads_dia "
                                "WHERE conexao_id IN (" + ph + ") "
                                "AND data=%s", (*ids, hoje_iso))
            gasto_hoje = r[0]["g"]
            r = consultar(conn, "SELECT COALESCE(SUM(gasto),0) AS g "
                                "FROM ads_dia "
                                "WHERE conexao_id IN (" + ph + ")", ids)
            gasto_total = r[0]["g"] or 0
            r = consultar(conn, "SELECT COALESCE(SUM(total),0) AS t "
                                "FROM pedidos "
                                "WHERE conexao_id IN (" + ph + ") "
                                "AND fechado_em IS NOT NULL", ids)
            fat_geral = r[0]["t"] or 0
            g_fat = consultar(conn, "SELECT SUBSTRING(fechado_em,1,10) AS dia, "
                                    "COALESCE(SUM(total),0) AS t "
                                    "FROM pedidos "
                                    "WHERE conexao_id IN (" + ph + ") "
                                    "AND fechado_em IS NOT NULL "
                                    "AND SUBSTRING(fechado_em,1,10) >= %s "
                                    "GROUP BY SUBSTRING(fechado_em,1,10)",
                              (*ids, ini7))
            g_vis = consultar(conn, "SELECT data, "
                                    "COALESCE(SUM(visitas),0) AS v "
                                    "FROM desempenho_historico "
                                    "WHERE conexao_id IN (" + ph + ") "
                                    "AND data >= %s GROUP BY data",
                              (*ids, ini7))
    fat_map = {r["dia"]: r["t"] for r in g_fat}
    vis_map = {r["data"]: r["v"] for r in g_vis}
    rotulos, serie_fat, serie_vis = [], [], []
    d = datetime.date.today() - datetime.timedelta(days=6)
    while d <= datetime.date.today():
        iso = d.isoformat()
        rotulos.append(d.strftime("%d/%m"))
        serie_fat.append(round(fat_map.get(iso, 0), 2))
        serie_vis.append(vis_map.get(iso, 0))
        d += datetime.timedelta(days=1)
    tacos = None
    if fat_geral and fat_geral > 0:
        tacos = round(gasto_total * 100.0 / fat_geral, 1)
    lista = "<div class='menu-lateral' style='width:250px'>"
    lista += "<div class='voltar'>Contas conectadas</div>"
    for l in lojas:
        if str(l["status"]) == "ativa":
            cor = "#1a9d5c"
        else:
            cor = "#d64545"
        lista += ("<div style='display:flex;align-items:center'>"
                  "<a class='item' style='flex:1' href='/painel/"
                  + str(l["id"]) + "'>"
                  "<span style='display:inline-block;width:8px;height:8px;"
                  "border-radius:50%;background:" + cor
                  + ";margin-right:8px'></span>"
                  + esc(str(l["cliente"])) + "</a>"
                  "<a class='icon-link' href='#' onclick='editarNome("
                  + str(l["id"]) + "); return false;'>✏️</a></div>")
    if session.get("tipo") == "admin":
        lista += ("<div style='border-top:1px solid #eef1f5;"
                  "margin-top:10px;padding-top:8px'></div>")
        lista += "<a class='item' href='/usuarios'>👥 Usuários</a>"
        lista += "<a class='item' href='/diagnostico'>🔍 Diagnóstico</a>"
    lista += "</div>"
    corpo = "<h2 style='margin-bottom:14px'>Visão geral</h2>"
    corpo += "<div class='grid' style='margin-bottom:18px'>"
    corpo += ("<div class='stat'><div class='num'>R$ " + br(fat_hoje)
              + "</div><div class='lab'>Faturamento hoje (todas as contas)</div>"
              + var_html(fat_hoje, fat_ontem) + "</div>")
    corpo += ("<div class='stat'><div class='num'>" + br(vendas_hoje, 0)
              + "</div><div class='lab'>Vendas hoje</div>"
              + "<div class='var estavel'>ontem: "
              + br(vendas_ontem, 0) + "</div></div>")
    corpo += ("<div class='stat'><div class='num'>" + br(visitas_total, 0)
              + "</div><div class='lab'>Visitas totais (todas as contas)"
              + "</div></div>")
    if gasto_hoje is not None:
        gasto_txt = "R$ " + br(gasto_hoje)
    else:
        gasto_txt = "<span class='tag sem'>—</span>"
    corpo += ("<div class='stat'><div class='num'>" + gasto_txt
              + "</div><div class='lab'>Gasto Ads hoje</div></div>")
    corpo += ("<div class='stat'><div class='num'>R$ " + br(gasto_total)
              + "</div><div class='lab'>Investimento total em Ads</div></div>")
    if tacos is not None:
        tacos_txt = br(tacos, 1) + "%"
    else:
        tacos_txt = "<span class='tag sem'>—</span>"
    corpo += ("<div class='stat'><div class='num'>" + tacos_txt
              + "</div><div class='lab'>TACOS geral (Ads ÷ faturamento)"
              + "</div></div>")
    corpo += "</div>"
    corpo += ("<div class='card'><h2>Evolução dos últimos 7 dias</h2>"
              "<div class='sub'>Faturamento e visitas somando todas as contas"
              "</div><div class='grafico-box'>"
              "<canvas id='graficoGeral'></canvas></div></div>")
    corpo += ("<script src='https://cdn.jsdelivr.net/npm/"
              "chart.js@4.4.1/dist/chart.umd.min.js'></script>")
    corpo += ("<script>var rot = " + json.dumps(rotulos) + ";"
              "var sf = " + json.dumps(serie_fat) + ";"
              "var sv = " + json.dumps(serie_vis) + ";"
              "new Chart(document.getElementById('graficoGeral'), {"
              "type:'line',"
              "data:{labels:rot,datasets:["
              "{label:'Faturamento (R$)',data:sf,borderColor:'#3483FA',"
              "backgroundColor:'rgba(52,131,250,0.12)',yAxisID:'y',"
              "tension:0.3,fill:true},"
              "{label:'Visitas',data:sv,borderColor:'#f59e0b',"
              "backgroundColor:'rgba(245,158,11,0.12)',yAxisID:'y1',"
              "tension:0.3,fill:true}]},"
              "options:{responsive:true,maintainAspectRatio:false,"
              "plugins:{legend:{position:'top'}},"
              "scales:{y:{type:'linear',position:'left',"
              "title:{display:true,text:'R$'},beginAtZero:true},"
              "y1:{type:'linear',position:'right',"
              "title:{display:true,text:'Visitas'},"
              "beginAtZero:true,grid:{drawOnChartArea:false}}}}});</script>")
    try:
        tenta_r = int(request.args.get("r", 0))
    except Exception:
        tenta_r = 0
    if disparou:
         if tenta_r < 10:
            corpo += ("<div class='aviso'>Atualizando contas em segundo plano "
                      "(restam " + str(len(FILA_ATUALIZACAO))
                      + " na fila) — a página recarrega sozinha.</div>")
            corpo += ("<script>setTimeout(function(){ location.href = "
                      "'/painel?r=" + str(tenta_r + 1) + "'; }, 60000);</script>")
         else:
            corpo += ("<div class='aviso'>A atualização ainda está rodando em "
                      "segundo plano. Recarregue a página em instantes.</div>")
    corpo += ("<div class='muted'>TACOS = investimento em Ads dividido pelo "
              "faturamento total. Clique em uma conta na lista à esquerda "
              "para abrir o Resumo dela.</div>")
    corpo_final = ("<div class='layout'>" + lista
                   + "<div class='conteudo'>" + corpo + "</div></div>")
    return pagina("Painel", corpo_final)


@app.route("/usuarios")
@admin_required
def usuarios():
    with banco() as conn:
        us = consultar(conn, """SELECT u.id, u.username, u.nome, u.email,
                                u.tipo, u.conexao_id, c.cliente
                                FROM usuarios u
                                LEFT JOIN conexoes c ON c.id=u.conexao_id
                                ORDER BY u.id""")
        lojas = consultar(conn, "SELECT id, cliente FROM conexoes ORDER BY id")
    msg = request.args.get("msg", "")
    corpo = ("<p style='margin-bottom:10px'><a class='link' href='/painel'>"
             "← Voltar ao painel</a></p>"
             "<h2 style='margin-bottom:14px'>Gerenciar usuários</h2>")
    if msg:
        corpo += "<div class='sucesso'>" + esc(msg) + "</div>"
    corpo += ("<div class='card'><h2>Novo usuário</h2>"
              "<div class='sub'>Crie um acesso. Cliente vê apenas a loja "
              "vinculada; admin vê tudo. Se preencher o e-mail, o usuário "
              "poderá recuperar a senha sozinho.</div>"
              "<form method='post' action='/usuarios/criar' "
              "style='display:flex;flex-wrap:wrap;gap:10px;align-items:center'>"
              "<input name='username' required placeholder='Usuário' class='filtro'>"
              "<input type='password' name='senha' id='campo-senha' "
              "required placeholder='Senha' class='filtro'>"
              "<button type='button' class='filtro-btn' onclick='gerarSenha()' "
              "style='background:#6b7280'>🎲 Gerar senha</button>"
              "<input name='nome' placeholder='Nome (opcional)' class='filtro'>"
              "<input name='email' type='email' "
              "placeholder='E-mail (p/ recuperação)' class='filtro'>"
              "<select name='tipo' class='filtro'>"
              "<option value='cliente'>Cliente</option>"
              "<option value='admin'>Admin</option></select>"
              "<select name='conexao_id' class='filtro'>"
              "<option value=''>— sem loja —</option>"
              + "".join("<option value='" + str(l["id"]) + "'>"
                        + esc(str(l["cliente"])) + "</option>" for l in lojas)
              + "</select>"
              "<button class='filtro-btn'>Criar</button>"
              "</form></div>")
    linhas_html = ""
    for u in us:
        if u["tipo"] == "admin":
            tipo_txt = "Admin"
            tag = "tag ativa"
        else:
            tipo_txt = "Cliente"
            tag = "tag pendente"
        if u["cliente"]:
            loja_txt = esc(str(u["cliente"]))
        else:
            loja_txt = "<span class='tag sem'>—</span>"
        if u["email"]:
            email_txt = esc(str(u["email"]))
        else:
            email_txt = "<span class='tag sem'>—</span>"
        linhas_html += ("<tr><td><b>" + esc(str(u["username"])) + "</b></td>"
                        "<td>" + esc(str(u["nome"] or "-")) + "</td>"
                        "<td>" + email_txt + "</td>"
                        "<td><span class='" + tag + "'>" + tipo_txt + "</span></td>"
                        "<td>" + loja_txt + "</td>"
                        "<td><a class='btn-acoes cinza' href='/usuarios/editar/"
                        + str(u["id"]) + "'>Editar</a>"
                        " <a class='btn-danger' href='/usuarios/excluir/"
                        + str(u["id"]) + "'>Excluir</a></td></tr>")
    corpo += ("<div class='card'><h2>Usuários <span class='badge'>"
              + str(len(us)) + "</span></h2>"
              "<table><thead><tr><th>Usuário</th><th>Nome</th><th>E-mail</th>"
              "<th>Tipo</th><th>Loja</th><th>Ações</th></tr></thead>"
              "<tbody>" + linhas_html + "</tbody></table></div>")
    return pagina("Usuários", corpo)


@app.route("/usuarios/criar", methods=["POST"])
@admin_required
def usuarios_criar():
    username = (request.form.get("username") or "").strip()
    senha = request.form.get("senha") or ""
    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").strip()
    tipo = request.form.get("tipo") or "cliente"
    conexao_id = request.form.get("conexao_id") or None
    if not username or not senha:
        return redirect("/usuarios?msg=Preencha usuário e senha")
    try:
        conexao_id = int(conexao_id) if conexao_id else None
    except Exception:
        conexao_id = None
    with banco() as conn:
        executar(conn, "INSERT INTO usuarios "
                       "(username, senha_hash, nome, email, tipo, conexao_id, criado_em) "
                       "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                 (username, generate_password_hash(senha), nome, email,
                  tipo, conexao_id, int(time.time())))
    return redirect("/usuarios?msg=Usuário criado com sucesso")


@app.route("/usuarios/editar/<int:uid>", methods=["GET", "POST"])
@admin_required
def usuarios_editar(uid):
    with banco() as conn:
        u = consultar(conn, "SELECT * FROM usuarios WHERE id=%s", (uid,))
        u = u[0] if u else None
        lojas = consultar(conn, "SELECT id, cliente FROM conexoes ORDER BY id")
    if not u:
        return pagina("Não encontrado",
                      "<div class='card'><h2>Usuário não encontrado</h2></div>")
    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        email = (request.form.get("email") or "").strip()
        tipo = request.form.get("tipo") or "cliente"
        conexao_id = request.form.get("conexao_id") or None
        nova_senha = request.form.get("senha") or ""
        try:
            conexao_id = int(conexao_id) if conexao_id else None
        except Exception:
            conexao_id = None
        with banco() as conn:
            if nova_senha:
                executar(conn, "UPDATE usuarios SET nome=%s, email=%s, tipo=%s, "
                               "conexao_id=%s, senha_hash=%s WHERE id=%s",
                         (nome, email, tipo, conexao_id,
                          generate_password_hash(nova_senha), uid))
            else:
                executar(conn, "UPDATE usuarios SET nome=%s, email=%s, tipo=%s, "
                               "conexao_id=%s WHERE id=%s",
                         (nome, email, tipo, conexao_id, uid))
        return redirect("/usuarios?msg=Usuário atualizado")
    corpo = ("<h2 style='margin-bottom:14px'>Editar usuário: "
             + esc(str(u["username"])) + "</h2>"
             "<div class='card'><form method='post' action='/usuarios/editar/"
             + str(uid) + "' style='display:flex;flex-wrap:wrap;gap:10px;"
             "align-items:center'>"
             "<input name='nome' placeholder='Nome' value='"
             + esc(str(u["nome"] or "")) + "' class='filtro'>"
             "<input name='email' type='email' "
             "placeholder='E-mail (p/ recuperação)' value='"
             + esc(str(u["email"] or "")) + "' class='filtro'>"
             "<input type='password' name='senha' id='campo-senha' "
             "placeholder='Nova senha (vazio p/ manter)' class='filtro'>"
             "<button type='button' class='filtro-btn' onclick='gerarSenha()' "
             "style='background:#6b7280'>🎲 Gerar senha</button>"
             "<select name='tipo' class='filtro'>"
             "<option value='cliente'"
             + (" selected" if u["tipo"] != "admin" else "")
             + ">Cliente</option>"
             "<option value='admin'"
             + (" selected" if u["tipo"] == "admin" else "")
             + ">Admin</option></select>"
             "<select name='conexao_id' class='filtro'>"
             "<option value=''>— sem loja —</option>"
             + "".join("<option value='" + str(l["id"]) + "'"
                       + (" selected" if u["conexao_id"] == l["id"] else "")
                       + ">" + esc(str(l["cliente"])) + "</option>" for l in lojas)
             + "</select>"
             "<button class='filtro-btn'>Salvar</button>"
             "</form></div>"
             "<p><a class='link' href='/usuarios'>← Voltar</a></p>")
    return pagina("Editar usuário", corpo)


@app.route("/usuarios/excluir/<int:uid>")
@admin_required
def usuarios_excluir(uid):
    with banco() as conn:
        u = consultar(conn, "SELECT * FROM usuarios WHERE id=%s", (uid,))
        u = u[0] if u else None
    if u and u["username"] == "admin":
        return redirect("/usuarios?msg=Não é possível excluir o usuário admin")
    if u:
        with banco() as conn:
            executar(conn, "DELETE FROM usuarios WHERE id=%s", (uid,))
    return redirect("/usuarios?msg=Usuário excluído")


@app.route("/excluir/<int:cid>", methods=["GET", "POST"])
@admin_required
def excluir(cid):
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
    if not c:
        return pagina("Não encontrada",
                      "<div class='card'><h2>Loja não encontrada</h2></div>")
    if request.method == "POST":
        with banco() as conn:
            for tabela in ("dados_conta", "anuncios", "pedidos", "pedidos_itens",
                           "metricas", "desempenho_historico", "perguntas",
                           "envios", "promocoes", "promocoes_itens",
                           "ads_campanhas", "ads_metricas", "ads_dia",
                           "ads_campanha_dia", "erros"):
                executar(conn, "DELETE FROM " + tabela + " WHERE conexao_id=%s", (cid,))
            executar(conn, "DELETE FROM conexoes WHERE id=%s", (cid,))
        corpo = ("<div class='card' style='max-width:520px;margin:40px auto;"
                 "text-align:center'>"
                 "<h2>Loja excluída com sucesso!</h2>"
                 "<div class='sub'>Todos os dados dessa loja foram removidos</div>"
                 "<p style='margin-top:16px'><a class='link' href='/painel'>"
                 "Voltar ao painel</a></p></div>")
        return pagina("Excluída", corpo)
    corpo = ("<div class='card' style='max-width:520px;margin:40px auto;"
             "text-align:center'>"
             "<h2>Excluir loja de " + esc(str(c["cliente"])) + "?</h2>"
             "<div class='sub'>Essa ação remove a conexão e todos os dados "
             "da loja. Não pode ser desfeita.</div>"
             "<form method='post' action='/excluir/" + str(cid)
             + "' style='margin-top:16px'>"
             "<button class='btn-danger' style='padding:13px 24px;font-size:15px'>"
             "Sim, excluir</button>"
             "</form>"
             "<p style='margin-top:14px'><a class='link' href='/painel'>"
             "← Cancelar</a></p>"
             "</div>")
    return pagina("Excluir loja", corpo)


@app.route("/campanhas/<int:cid>")
@login_required
def campanhas(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado",
                      "<div class='card'><h2>Acesso restrito</h2></div>")
    hoje = datetime.date.today().isoformat()
    sem_vendas = request.args.get("sem_vendas", type=int, default=0)
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if c:
            campanhas = consultar(conn, "SELECT * FROM ads_campanhas "
                                        "WHERE conexao_id=%s ORDER BY data_inicio DESC", (cid,))
            gastos = consultar(conn, """SELECT campanha_id, COALESCE(SUM(gasto),0) AS gasto
                                        FROM ads_metricas WHERE conexao_id=%s
                                        GROUP BY campanha_id""", (cid,))
            camp_dia = consultar(conn, "SELECT * FROM ads_campanha_dia WHERE conexao_id=%s", (cid,))
            ads_dia = consultar(conn, "SELECT * FROM ads_dia WHERE conexao_id=%s "
                                      "AND data >= %s ORDER BY data",
                                (cid, (datetime.date.today()
                                       - datetime.timedelta(days=6)).isoformat()))
            filtro_ativo = sem_vendas > 0
            if filtro_ativo:
                data_limite = (datetime.date.today()
                               - datetime.timedelta(days=sem_vendas)).isoformat()
                fat_janela = consultar(conn, """SELECT campanha_id,
                    COALESCE(SUM(faturamento),0) AS fat
                    FROM ads_campanha_dia
                    WHERE conexao_id=%s AND data >= %s
                    GROUP BY campanha_id""", (cid, data_limite))
    if not c:
        return pagina("Não encontrada",
                      "<div class='card'><h2>Loja não encontrada</h2></div>")
    ultima = ultima_atualizacao(cid)
    if filtro_ativo:
        fat_por_camp = {r["campanha_id"]: (r["fat"] or 0) for r in fat_janela}
        campanhas = [c2 for c2 in campanhas
                     if str(c2["status"]) in ("active", "ACTIVE", "running")
                     and fat_por_camp.get(c2["campanha_id"], 0) <= 0]
    gasto_por_camp = {g["campanha_id"]: g["gasto"] for g in gastos}
    camp_dia_map = {}
    for r in camp_dia:
        camp_dia_map[(r["campanha_id"], r["data"])] = r
    ads_map = {r["data"]: r for r in ads_dia}
    ad_hoje = ads_map.get(hoje)
    gasto_total = ad_hoje["gasto"] if ad_hoje and ad_hoje["gasto"] is not None else None
    fat_total = ad_hoje["faturamento"] if ad_hoje and ad_hoje["faturamento"] is not None else None
    roas_total = (fat_total / gasto_total) if (gasto_total and fat_total
                                               is not None and gasto_total > 0) else None
    corpo = "<h2 style='margin-bottom:10px'>Campanhas Ads</h2>" \
        + barra_atualizar(cid, ultima, "campanhas")
    filtros = [("", "Todas"), (3, "3 dias sem vender"), (7, "7 dias sem vender"),
               (15, "15 dias sem vender"), (30, "30 dias sem vender")]
    corpo += ("<div class='card no-print'><h2>Filtro: X dias sem vendas</h2>"
              "<div class='sub'>Mostra apenas campanhas <b>ativas</b> sem "
              "faturamento de Ads nos últimos X dias</div>"
              "<div style='display:flex;flex-wrap:wrap;gap:8px'>")
    for val, rotulo in filtros:
        classe = "filtro"
        if (val == 0 and not filtro_ativo) or (val != 0 and sem_vendas == val):
            classe += " filtro-btn"
        if val == 0:
            href = "/campanhas/" + str(cid)
        else:
            href = "/campanhas/" + str(cid) + "?sem_vendas=" + str(val)
        corpo += "<a class='" + classe + "' href='" + href \
            + "' style='text-decoration:none'>" + rotulo + "</a>"
    corpo += "</div></div>"
    if not campanhas:
        if filtro_ativo:
            titulo_v = ("Nenhuma campanha ativa sem vendas nos últimos "
                        + str(sem_vendas) + " dias")
            sub_v = "Nenhuma campanha ativa ficou sem faturamento de Ads nesse período."
        else:
            titulo_v = "Nenhuma campanha carregada ainda"
            sub_v = "Use 'Atualizar agora' acima para buscar as campanhas de Mercado Ads."
        corpo += ("<div class='card' style='text-align:center;padding:40px'>"
                  "<h2>" + titulo_v + "</h2><div class='sub'>" + sub_v + "</div></div>")
        return pagina_loja("Campanhas", cid, c["cliente"], "campanhas", corpo)
    if roas_total is not None:
        roas_html = "<span class='alerta ok'>%.1f</span>" % roas_total
    else:
        roas_html = "<span class='tag sem'>—</span>"
    corpo += ("<div class='grid' style='margin-bottom:18px'>"
              "<div class='stat'><div class='num'>"
              + (("R$ %.2f" % gasto_total) if gasto_total is not None
                 else "<span class='tag sem'>—</span>")
              + "</div><div class='lab'>Gasto Ads hoje</div></div>"
              "<div class='stat'><div class='num'>"
              + (("R$ %.2f" % fat_total) if fat_total is not None
                 else "<span class='tag sem'>—</span>")
              + "</div><div class='lab'>Faturamento Ads hoje</div></div>"
              "<div class='stat'><div class='num'>" + roas_html
              + "</div><div class='lab'>ROAS real (faturamento ÷ gasto)</div></div>"
              "</div>")
    corpo += ("<div class='card'><h2>Campanhas <span class='badge'>"
              + str(len(campanhas)) + "</span></h2>"
              "<div class='sub'>Defina o <b>ROAS objetivo</b> de cada campanha "
              "(clique no valor). O painel alerta quando o orçamento acabou "
              "e compara o ROAS real com o objetivo.</div>")
    for camp in campanhas:
        cid_camp = camp["campanha_id"]
        st = str(camp["status"])
        if st in ("active", "ACTIVE", "running"):
            tag, st_txt = "tag ativa", "ativa"
        elif st in ("paused", "PAUSED"):
            tag, st_txt = "tag expirada", "pausada"
        elif st in ("finished", "FINISHED", "ended"):
            tag, st_txt = "tag normal", "finalizada"
        else:
            tag, st_txt = "tag normal", st
        orcamento = camp["orcamento"]
        gasto = gasto_por_camp.get(cid_camp, 0)
        pct = (gasto * 100.0 / orcamento) if orcamento else 0
        roas_obj = camp["roas_objetivo"]
        camp_hoje = camp_dia_map.get((cid_camp, hoje))
        camp_gasto = camp_hoje["gasto"] if camp_hoje else None
        camp_fat = camp_hoje["faturamento"] if camp_hoje else None
        roas_real = (camp_fat / camp_gasto) if (camp_gasto and camp_fat
                                                is not None and camp_gasto > 0) else None
        if orcamento is not None:
            orc_txt = "R$ %.2f" % orcamento
        else:
            orc_txt = "<span class='tag sem'>—</span>"
        gasto_txt = "R$ %.2f" % gasto
        pct_html = ""
        if orcamento:
            if pct >= 100:
                pct_html = "<span class='alerta urgente'>%.0f%% consumido</span>" % pct
            elif pct >= 80:
                pct_html = "<span class='alerta atencao'>%.0f%% consumido</span>" % pct
            else:
                pct_html = "<span class='alerta ok'>%.0f%% consumido</span>" % pct
        if roas_obj is not None:
            roas_obj_html = ("<span id='roas-" + str(cid) + "-" + str(cid_camp)
                             + "'>%.1f</span>" % roas_obj)
        else:
            roas_obj_html = ("<a class='link' href='#' onclick='editarRoas("
                             + str(cid) + ", \"" + str(cid_camp)
                             + "\"); return false;'>+ definir</a>")
        if roas_real is not None:
            if roas_obj is not None:
                if roas_real < roas_obj:
                    roas_real_html = ("<span class='alerta urgente'>%.1f "
                                      "(abaixo do objetivo)</span>" % roas_real)
                else:
                    roas_real_html = ("<span class='alerta ok'>%.1f "
                                      "(acima do objetivo)</span>" % roas_real)
            else:
                roas_real_html = ("<span class='alerta atencao'>%.1f</span>" % roas_real)
        else:
            roas_real_html = "<span class='tag sem'>sem dados</span>"
        corpo += ("<div class='campanha-item'>"
                  "<div class='titulo'>"
                  + esc(camp["nome"] or ("Campanha " + str(cid_camp)))
                  + " <span class='" + tag + "'>" + st_txt + "</span></div>"
                  "<div class='meta'>Tipo: " + esc(str(camp["tipo"] or "-"))
                  + " · Início: " + esc(str(camp["data_inicio"] or "-")[:10])
                  + " · Fim: " + esc(str(camp["data_fim"] or "-")[:10]) + "</div>"
                  "<table><thead><tr><th>Orçamento</th><th>Gasto</th>"
                  "<th>Consumo</th><th>ROAS objetivo</th><th>ROAS real</th>"
                  "</tr></thead><tbody>"
                  "<tr><td>" + orc_txt + "</td><td>" + gasto_txt + "</td>"
                  "<td>" + pct_html + "</td>"
                  "<td>" + roas_obj_html + "</td><td>" + roas_real_html + "</td>"
                  "</tr></tbody></table>")
        alertas = []
        if orcamento and gasto >= orcamento:
            alertas.append(("urgente",
                            "Orçamento totalmente consumido (gasto R$ %.2f ≥ "
                            "orçamento R$ %.2f). Considere liberar mais verba."
                            % (gasto, orcamento)))
        elif orcamento and pct >= 80:
            alertas.append(("atencao",
                            "Orçamento quase no limite (%.0f%% consumido). "
                            "Avalie se vale liberar mais verba." % pct))
        if roas_real is not None and roas_obj is not None:
            if roas_real < roas_obj:
                alertas.append(("urgente",
                                "ROAS real (%.1f) está ABAIXO do objetivo (%.1f). "
                                "Revise anúncios, lance ou segmentação."
                                % (roas_real, roas_obj)))
            else:
                alertas.append(("ok",
                                "ROAS real (%.1f) está ACIMA do objetivo (%.1f). "
                                "Campanha saudável — pode valer aumentar verba."
                                % (roas_real, roas_obj)))
        for grav, msg in alertas:
            corpo += ("<div class='alerta " + grav
                      + "' style='margin-top:8px;display:block'>" + msg + "</div>")
        corpo += "</div>"
    corpo += ("<div class='muted'>ROAS = retorno sobre o investimento em anúncios "
              "(faturamento gerado ÷ gasto). O ROAS objetivo é uma meta definida "
              "aqui no painel — não altera a campanha no Mercado Livre. Ajustes "
              "reais (orçamento, lance) são feitos na Central de Vendedores.</div>")
    corpo += "</div>"
    return pagina_loja("Campanhas", cid, c["cliente"], "campanhas", corpo)


@app.route("/promocoes/<int:cid>")
@login_required
def promocoes(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado",
                      "<div class='card'><h2>Acesso restrito</h2></div>")
    hoje = datetime.date.today()
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if c:
            promos = consultar(conn, "SELECT * FROM promocoes "
                                     "WHERE conexao_id=%s ORDER BY fim DESC", (cid,))
            itens_promo = consultar(conn, """
                SELECT pi.promocao_id, pi.item_id, pi.preco_promocional,
                       a.titulo, a.preco, a.custo, a.quantidade, a.status
                FROM promocoes_itens pi
                LEFT JOIN anuncios a
                  ON a.conexao_id=pi.conexao_id AND a.item_id=pi.item_id
                WHERE pi.conexao_id=%s
            """, (cid,))
    if not c:
        return pagina("Não encontrada",
                      "<div class='card'><h2>Loja não encontrada</h2></div>")
    ultima = ultima_atualizacao(cid)
    itens_por_promo = {}
    for it in itens_promo:
        itens_por_promo.setdefault(it["promocao_id"], []).append(it)
    corpo = "<h2 style='margin-bottom:10px'>Promoções</h2>" \
        + barra_atualizar(cid, ultima, "promocoes")
    if not promos:
        corpo += ("<div class='card' style='text-align:center;padding:40px'>"
                  "<h2>Nenhuma promoção carregada ainda</h2>"
                  "<div class='sub'>Use 'Atualizar agora' acima para buscar "
                  "as promoções da loja</div></div>")
        return pagina_loja("Promoções", cid, c["cliente"], "promocoes", corpo)
    ativas = sum(1 for p in promos if str(p["status"]) in ("active", "ACTIVE"))
    candidatas = sum(1 for p in promos if str(p["status"]) in ("candidate", "CANDIDATE"))
    finalizadas = len(promos) - ativas - candidatas
    corpo += ("<div class='grid' style='margin-bottom:18px'>"
              "<div class='stat'><div class='num'>" + str(ativas)
              + "</div><div class='lab'>Promoções ativas</div></div>"
              "<div class='stat'><div class='num'>" + str(candidatas)
              + "</div><div class='lab'>Candidatas</div></div>"
              "<div class='stat'><div class='num'>" + str(finalizadas)
              + "</div><div class='lab'>Finalizadas</div></div>"
              "</div>")
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
        corpo += ("<div class='card'><h2>⏰ Alertas de expiração</h2>"
                  "<div class='sub'>Promoções ativas que estão terminando</div>")
        for nome, dias, grav in alertas:
            if dias <= 0:
                txt = "expira hoje"
            else:
                txt = "expira em " + str(dias) + " dia(s)"
            corpo += ("<div class='alerta " + grav
                      + "' style='margin-bottom:6px'>" + esc(nome) + " — " + txt + "</div>")
        corpo += "</div>"
    else:
        corpo += ("<div class='card'><h2>⏰ Alertas de expiração</h2>"
                  "<div class='sub'>Nenhuma promoção ativa perto de expirar</div>"
                  "<span class='alerta ok'>OK</span></div>")
    for p in promos:
        st = str(p["status"])
        if st in ("active", "ACTIVE"):
            classe, st_txt = "ativa", "ATIVA"
        elif st in ("candidate", "CANDIDATE"):
            classe, st_txt = "candidata", "CANDIDATA"
        else:
            classe, st_txt = "finalizada", "FINALIZADA"
        itens = itens_por_promo.get(p["promocao_id"], [])
        corpo += ("<div class='promo-item " + classe + "'>"
                  "<div class='titulo'>"
                  + esc(p["nome"] or ("Promoção " + str(p["promocao_id"])))
                  + " <span class='badge'>" + st_txt + "</span></div>"
                  "<div class='meta'>Tipo: " + esc(str(p["tipo"] or "-"))
                  + " · Início: " + esc(str(p["inicio"] or "-")[:10])
                  + " · Fim: " + esc(str(p["fim"] or "-")[:10])
                  + " · Itens: " + str(len(itens)) + "</div>")
        if itens:
            corpo += ("<table><thead><tr><th>Anúncio</th><th>Preço normal</th>"
                      "<th>Preço promo</th><th>Desconto</th><th>Custo</th>"
                      "<th>Margem na promo</th></tr></thead><tbody>")
            for it in itens:
                preco = it["preco"] or 0
                preco_promo = it["preco_promocional"]
                custo = it["custo"]
                if preco and preco_promo is not None:
                    desc = round((preco - preco_promo) * 100.0 / preco, 1)
                    desc_html = "<span class='alerta atencao'>-" + str(desc) + "%</span>"
                else:
                    desc_html = "<span class='tag sem'>—</span>"
                if custo is not None and preco_promo is not None:
                    if preco_promo:
                        margem = round((preco_promo - custo) * 100.0 / preco_promo, 1)
                    else:
                        margem = 0
                    if margem <= 0:
                        margem_html = ("<span class='alerta urgente'>%.1f%% "
                                       "(come a margem)</span>" % margem)
                    elif margem < 20:
                        margem_html = ("<span class='alerta atencao'>%.1f%%"
                                       "</span>" % margem)
                    else:
                        margem_html = ("<span class='alerta ok'>%.1f%%</span>" % margem)
                elif custo is None:
                    margem_html = ("<a class='link' href='/custos/"
                                   + str(cid) + "'>+ custo</a>")
                else:
                    margem_html = "<span class='tag sem'>sem preço promo</span>"
                if custo is not None:
                    custo_html = "R$ %.2f" % custo
                else:
                    custo_html = ("<a class='link' href='/custos/"
                                  + str(cid) + "'>+ definir</a>")
                if preco_promo is not None:
                    preco_promo_html = "R$ %.2f" % preco_promo
                else:
                    preco_promo_html = "<span class='tag sem'>—</span>"
                corpo += ("<tr><td>"
                          + esc(str(it["titulo"] or it["item_id"]))
                          + "<br><small class='muted'>" + str(it["item_id"])
                          + "</small></td>"
                          "<td>R$ %.2f" % preco + "</td><td>"
                          + preco_promo_html + "</td><td>" + desc_html
                          + "</td><td>" + custo_html + "</td><td>"
                          + margem_html + "</td></tr>")
            corpo += "</tbody></table>"
        else:
            corpo += "<div class='muted'>Sem itens associados a esta promoção.</div>"
        corpo += "</div>"
    corpo += ("<div class='muted'>Para o comparativo de margem, cadastre o "
              "<b>custo</b> dos anúncios na <a class='link' href='/custos/"
              + str(cid) + "'>tela de Custos</a> (individual ou por planilha). "
              "O painel calcula o desconto aplicado e se a promoção ainda "
              "deixa margem.</div>")
    return pagina_loja("Promoções", cid, c["cliente"], "promocoes", corpo)


@app.route("/exportar_demandas/<int:cid>")
@login_required
def exportar_demandas(cid):
    if not pode_ver_loja(cid):
        return "Acesso negado", 403
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if c:
            anuncios = consultar(conn, "SELECT * FROM anuncios WHERE conexao_id=%s", (cid,))
            metricas = consultar(conn, "SELECT item_id, visitas, conversao "
                                       "FROM metricas WHERE conexao_id=%s", (cid,))
            promos_ativas = consultar(conn, """SELECT DISTINCT pi.item_id
                FROM promocoes_itens pi
                JOIN promocoes p ON p.conexao_id=pi.conexao_id
                  AND p.promocao_id=pi.promocao_id
                WHERE pi.conexao_id=%s AND p.status IN ('active','ACTIVE')""", (cid,))
    if not c:
        return "Loja não encontrada", 404
    itens_promocao = {r["item_id"] for r in promos_ativas}
    visitas_por_item = {m["item_id"]: (m["visitas"] or 0) for m in metricas}
    conv_por_item = {m["item_id"]: (m["conversao"] or 0) for m in metricas}
    linhas = []
    for a in anuncios:
        a["visitas"] = visitas_por_item.get(a["item_id"], 0)
        demandas_lista = montar_demandas_anuncio(
            a, a["item_id"] in itens_promocao, conv_por_item.get(a["item_id"]))
        for acao, grav in demandas_lista:
            linhas.append([c["cliente"], a["item_id"], a["titulo"], grav, acao])
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Cliente", "Item", "Anúncio", "Gravidade", "Demanda"])
    for l in linhas:
        writer.writerow(l)
    nome_arq = "demandas_" + str(c["cliente"]).replace(" ", "_") + ".csv"
    return Response(buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=" + nome_arq})


@app.route("/demandas/<int:cid>")
@login_required
def demandas(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado",
                      "<div class='card'><h2>Acesso restrito</h2></div>")
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
            metricas = consultar(conn, "SELECT item_id, visitas, conversao "
                                       "FROM metricas WHERE conexao_id=%s", (cid,))
            promos_ativas = consultar(conn, """SELECT DISTINCT pi.item_id
                FROM promocoes_itens pi
                JOIN promocoes p ON p.conexao_id=pi.conexao_id
                  AND p.promocao_id=pi.promocao_id
                WHERE pi.conexao_id=%s AND p.status IN ('active','ACTIVE')""", (cid,))
    if not c:
        return pagina("Não encontrada",
                      "<div class='card'><h2>Loja não encontrada</h2></div>")
    ultima = ultima_atualizacao(cid)
    itens_promocao = {r["item_id"] for r in promos_ativas}
    visitas_por_item = {m["item_id"]: (m["visitas"] or 0) for m in metricas}
    conv_por_item = {m["item_id"]: (m["conversao"] or 0) for m in metricas}
    itens_demandas = []
    for a in anuncios:
        a["visitas"] = visitas_por_item.get(a["item_id"], 0)
        demandas_lista = montar_demandas_anuncio(
            a, a["item_id"] in itens_promocao, conv_por_item.get(a["item_id"]))
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
    corpo = ("<div class='barra-topo'><h2>Central de Demandas</h2>"
             "<div style='display:flex;gap:10px;flex-wrap:wrap;align-items:center'>"
             "<a class='btn-acoes cinza' href='/exportar_demandas/"
             + str(cid) + "'>⬇ Exportar CSV</a>"
             "<a class='btn-acoes cinza' href='#' onclick='window.print(); "
             "return false;'>🖨 Imprimir/PDF</a>"
             "</div></div>"
             + barra_atualizar(cid, ultima, "demandas"))
    total_anuncios = len(anuncios)
    com_demanda = len(itens_demandas)
    urgentes_total = sum(i["urgentes"] for i in itens_demandas)
    corpo += ("<div class='grid' style='margin-bottom:18px'>"
              "<div class='stat'><div class='num'>" + str(total_anuncios)
              + "</div><div class='lab'>Total de anúncios</div></div>"
              "<div class='stat'><div class='num'>" + str(com_demanda)
              + "</div><div class='lab'>Precisam de ação</div></div>"
              "<div class='stat'><div class='num'>" + str(urgentes_total)
              + "</div><div class='lab'>Demandas urgentes</div></div>"
              "</div>")
    corpo += ("<div class='card no-print'><h2>Filtros</h2>"
              "<div class='sub'>Principais pontos de alerta por anúncio, "
              "ordenados por prioridade</div>"
              "<form method='get' action='/demandas/" + str(cid)
              + "' style='display:flex;flex-wrap:wrap;align-items:center;gap:8px'>"
              "<label style='font-size:13px;color:#6b7280'>Mostrar:</label>"
              "<input type='number' name='limite' value='" + str(limite)
              + "' min='1' max='200' class='filtro' style='width:90px'>"
              "<span style='color:#6b7280;font-size:13px'>anúncios</span>"
              "<button class='filtro-btn'>Aplicar</button>"
              "</form>"
              "<div style='margin-top:10px'><b style='font-size:13px;"
              "color:#6b7280'>Filtrar por tipo:</b> "
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite="
              + str(limite) + "' style='text-decoration:none'>Todos</a>"
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite="
              + str(limite) + "&filtro=estoque' style='text-decoration:none'>Estoque</a>"
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite="
              + str(limite) + "&filtro=fotos' style='text-decoration:none'>Fotos</a>"
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite="
              + str(limite) + "&filtro=clips' style='text-decoration:none'>Clips</a>"
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite="
              + str(limite) + "&filtro=tag' style='text-decoration:none'>Tags</a>"
              "<a class='filtro' href='/demandas/" + str(cid) + "?limite="
              + str(limite) + "&filtro=conversao' style='text-decoration:none'>Conversão</a>"
              "</div></div>")
    if not itens_demandas:
        corpo += ("<div class='card' style='text-align:center;padding:40px'>"
                  "<h2>Nenhuma demanda encontrada</h2>"
                  "<div class='sub'>Todos os anúncios carregados estão em dia. "
                  "Use 'Atualizar agora' acima para buscar os dados mais recentes."
                  "</div></div>")
        return pagina_loja("Demandas", cid, c["cliente"], "demandas", corpo)
    if filtro:
        filtrados = []
        for i in itens_demandas:
            textos = [d.lower() for d, _ in i["demandas"]]
            if filtro == "estoque" and any("estoque" in t for t in textos):
                filtrados.append(i)
            elif filtro == "fotos" and any("foto" in t for t in textos):
                filtrados.append(i)
            elif filtro == "clips" and any("clip" in t or "vídeo" in t
                                           or "video" in t for t in textos):
                filtrados.append(i)
            elif filtro == "tag" and any("tag" in t for t in textos):
                filtrados.append(i)
            elif filtro == "conversao" and any("conversão" in t for t in textos):
                filtrados.append(i)
        itens_demandas = filtrados
        if not itens_demandas:
            corpo += ("<div class='card' style='text-align:center;padding:30px'>"
                      "<h2>Nenhum anúncio com esse tipo de demanda</h2></div>")
            return pagina_loja("Demandas", cid, c["cliente"], "demandas", corpo)
    itens_demandas = itens_demandas[:limite]
    corpo += ("<div class='card'><h2>Anúncios que precisam de ação "
              "<span class='badge'>" + str(len(itens_demandas)) + "</span></h2>")
    for i in itens_demandas:
        if i["urgentes"] > 0:
            classe = "urgente"
        else:
            classe = "atencao"
        corpo += ("<div class='demanda-item " + classe + "'>"
                  "<div class='titulo'>" + esc(i["titulo"])
                  + " <small class='muted'>(" + str(i["item_id"]) + ")</small>"
                  " <span class='badge'>" + str(i["total"]) + " demandas</span></div>")
        for acao, grav in i["demandas"]:
            if grav == "urgente":
                icone = "🔴 "
            else:
                icone = "🟡 "
            corpo += ("<div class='acao " + grav + "'>" + icone + esc(acao) + "</div>")
        corpo += "</div>"
    corpo += "</div>"
    return pagina_loja("Demandas", cid, c["cliente"], "demandas", corpo)
@app.route("/anuncios/<int:cid>")
@login_required
def anuncios(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado",
                      "<div class='card'><h2>Acesso restrito</h2></div>")
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        anuncios = consultar(conn, "SELECT * FROM anuncios "
                                   "WHERE conexao_id=%s ORDER BY vendidos DESC", (cid,))
        promos_ativas = consultar(conn, """SELECT DISTINCT pi.item_id
            FROM promocoes_itens pi
            JOIN promocoes p ON p.conexao_id=pi.conexao_id
              AND p.promocao_id=pi.promocao_id
            WHERE pi.conexao_id=%s AND p.status IN ('active','ACTIVE')""", (cid,))
        erros = consultar(conn, "SELECT * FROM erros WHERE conexao_id=%s", (cid,))
    if not c:
        return pagina("Não encontrada",
                      "<div class='card'><h2>Loja não encontrada</h2></div>")
    ultima = ultima_atualizacao(cid)
    itens_promocao = {r["item_id"] for r in promos_ativas}
    corpo = "<h2 style='margin-bottom:10px'>Anúncios</h2>" \
        + barra_atualizar(cid, ultima, "anuncios")
    if not anuncios:
        corpo += ("<div class='card' style='text-align:center;padding:40px'>"
                  "<h2>Nenhum anúncio carregado ainda</h2>"
                  "<div class='sub'>Use 'Atualizar agora' acima para buscar "
                  "os anúncios da loja</div></div>")
        return pagina_loja("Anúncios", cid, c["cliente"], "anuncios", corpo)
    total = len(anuncios)
    com_estoque_zero = sum(1 for a in anuncios if (a["quantidade"] or 0) <= 0)
    com_fotos_baixas = sum(1 for a in anuncios if (a["fotos"] or 0) < 10)
    em_promocao = sum(1 for a in anuncios if a["item_id"] in itens_promocao)
    corpo += ("<div class='grid' style='margin-bottom:18px'>"
              "<div class='stat'><div class='num'>" + str(total)
              + "</div><div class='lab'>Total de anúncios</div></div>"
              "<div class='stat'><div class='num'>" + str(com_estoque_zero)
              + "</div><div class='lab'>Estoque zerado</div></div>"
              "<div class='stat'><div class='num'>" + str(com_fotos_baixas)
              + "</div><div class='lab'>Fotos abaixo de 10</div></div>"
              "<div class='stat'><div class='num'>" + str(em_promocao)
              + "</div><div class='lab'>Em promoção</div></div>"
              "</div>")
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
            fotos_html = "<span class='alerta ok'>" + str(fotos) + "/10</span>"
        elif fotos > 0:
            fotos_html = "<span class='alerta atencao'>" + str(fotos) + "/10</span>"
        else:
            fotos_html = "<span class='alerta urgente'>0/10</span>"
        clips = a["clips"]
        if clips is None:
            clips_html = "<span class='tag sem'>não verificado</span>"
        elif clips >= 2:
            clips_html = "<span class='alerta ok'>" + str(clips) + "</span>"
        elif clips > 0:
            clips_html = "<span class='alerta atencao'>" + str(clips) + "</span>"
        else:
            clips_html = "<span class='alerta atencao'>0</span>"
        if em_promo:
            promo_html = "<span class='tag promocao'>Em promoção</span>"
        else:
            promo_html = "<span class='tag sem'>—</span>"
        tags = []
        try:
            tags = json.loads(a["tags"]) if a["tags"] else []
        except Exception:
            tags = []
        tags_html = ""
        for t in tags[:6]:
            if t in TAGS_RUINS:
                tags_html += "<span class='tag ruim'>" + esc(t) + "</span> "
            elif t in TAGS_BOAS:
                tags_html += "<span class='tag boa'>" + esc(t) + "</span> "
            else:
                tags_html += "<span class='tag normal'>" + esc(t) + "</span> "
        if not tags_html:
            tags_html = "<span class='tag sem'>sem tags</span>"
        peso_kg = a["peso"]
        f = frete_esperado(a["preco"], peso_kg)
        if f is not None:
            frete_html = "<span class='alerta ok'>R$ %.2f</span>" % f
            if peso_kg:
                peso_txt = "%.2f kg" % peso_kg
            else:
                peso_txt = "-"
        else:
            frete_html = "<span class='tag sem'>sem peso</span>"
            peso_txt = "-"
        linhas_html += ("<tr>"
                        "<td><b>" + esc(str(a["titulo"])) + "</b><br>"
                        "<small class='muted'>" + str(a["item_id"]) + "</small></td>"
                        "<td>R$ %.2f" % (a["preco"] or 0) + "</td>"
                        "<td>" + str(a["quantidade"] or 0) + "</td>"
                        "<td>" + fotos_html + "</td>"
                        "<td>" + clips_html + "</td>"
                        "<td><span class='" + st_tag + "'>" + st_txt + "</span></td>"
                        "<td>" + promo_html + "</td>"
                        "<td>" + tags_html + "</td>"
                        "<td>" + str(a["vendidos"] or 0) + "</td>"
                        "<td>" + peso_txt + "</td>"
                        "<td>" + frete_html + "</td>"
                        "</tr>")
    corpo += ("<div class='card'><h2>Lista de anúncios <span class='badge'>"
              + str(total) + "</span></h2>"
              "<div class='sub'>Análises por produto — fotos, clips, promoção, "
              "tags e frete esperado</div>"
              "<div style='overflow-x:auto'><table>"
              "<thead><tr><th>Anúncio</th><th>Preço</th><th>Estoque</th>"
              "<th>Fotos</th><th>Clips</th><th>Status</th><th>Promoção</th>"
              "<th>Tags</th><th>Vendidos</th><th>Peso</th>"
              "<th>Frete esperado</th></tr></thead>"
              "<tbody>" + linhas_html + "</tbody></table></div>"
              "<div class='muted'>Frete esperado = custo do Mercado Livre pela "
              "tabela oficial (peso × faixa de preço). Cadastre os custos na "
              "<a class='link' href='/custos/" + str(cid) + "'>tela de Custos</a> "
              "e veja a rentabilidade na <a class='link' href='/vendas/"
              + str(cid) + "'>tela de Vendas</a>.</div></div>")
    if erros:
        avisos = ""
        for e in erros:
            if e["categoria"] in ("financeiro",):
                continue
            avisos += ("<div>" + esc(e["categoria"]) + ": "
                       + esc(e["mensagem"]) + "</div>")
        if avisos:
            corpo += ("<div class='aviso'><b>Avisos:</b> " + avisos + "</div>")
    return pagina_loja("Anúncios", cid, c["cliente"], "anuncios", corpo)


@app.route("/desempenho/<int:cid>")
@login_required
def desempenho(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado",
                      "<div class='card'><h2>Acesso restrito</h2></div>")
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
                  COALESCE(SUM(CASE WHEN h.data BETWEEN %s AND %s
                    THEN h.visitas ELSE 0 END),0) AS visitas,
                  COALESCE(SUM(CASE WHEN h.data BETWEEN %s AND %s
                    THEN h.vendidos ELSE 0 END),0) AS vendidos,
                  COALESCE(SUM(CASE WHEN h.data BETWEEN %s AND %s
                    THEN h.visitas ELSE 0 END),0) AS visitas_ant,
                  COALESCE(SUM(CASE WHEN h.data BETWEEN %s AND %s
                    THEN h.vendidos ELSE 0 END),0) AS vendidos_ant
                FROM anuncios a
                LEFT JOIN desempenho_historico h
                  ON h.conexao_id=a.conexao_id AND h.item_id=a.item_id
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
                SELECT SUBSTRING(fechado_em,1,10) AS dia,
                       COALESCE(SUM(total),0) AS total
                FROM pedidos
                WHERE conexao_id=%s AND fechado_em IS NOT NULL
                  AND SUBSTRING(fechado_em,1,10) BETWEEN %s AND %s
                GROUP BY SUBSTRING(fechado_em,1,10)
            """, (cid, d_inicio.isoformat(), d_fim.isoformat()))
    if not c:
        return pagina("Não encontrada",
                      "<div class='card'><h2>Loja não encontrada</h2></div>")
    ultima = ultima_atualizacao(cid)
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
    corpo = "<h2 style='margin-bottom:10px'>Desempenho</h2>" \
        + barra_atualizar(cid, ultima, "desempenho")
    corpo += ("<div class='card'><h2>Período de análise</h2>"
              "<div class='sub'>Escolha o período para comparar visitas, "
              "vendas e faturamento</div>"
              "<form method='get' action='/desempenho/" + str(cid)
              + "' style='display:flex;flex-wrap:wrap;align-items:center;gap:8px'>"
              "<a class='filtro' href='/desempenho/" + str(cid)
              + "?dias=7' style='text-decoration:none'>7 dias</a>"
              "<a class='filtro' href='/desempenho/" + str(cid)
              + "?dias=30' style='text-decoration:none'>30 dias</a>"
              "<a class='filtro' href='/desempenho/" + str(cid)
              + "?dias=90' style='text-decoration:none'>90 dias</a>"
              "<input type='date' name='de' value='" + de
              + "' class='filtro' style='margin-left:10px'>"
              "<span style='color:#6b7280;font-size:13px'>até</span>"
              "<input type='date' name='ate' value='" + ate + "' class='filtro'>"
              "<button class='filtro-btn'>Aplicar</button>"
              "</form>"
              "<div class='muted'>Período selecionado: "
              + d_inicio.strftime("%d/%m/%Y") + " a "
              + d_fim.strftime("%d/%m/%Y") + " (comparado com "
              + p_inicio.strftime("%d/%m/%Y") + " a "
              + p_fim.strftime("%d/%m/%Y") + ")</div></div>")
    if not linhas:
        corpo += ("<div class='card' style='text-align:center;padding:40px'>"
                  "<h2>Sem dados de desempenho ainda</h2>"
                  "<div class='sub'>O histórico é gravado a cada atualização. "
                  "Use 'Atualizar agora' acima para começar a acumular.</div></div>")
        return pagina_loja("Desempenho", cid, c["cliente"], "desempenho", corpo)
    tot_visitas = sum(r["visitas"] or 0 for r in linhas)
    tot_vendas = sum(r["vendidos"] or 0 for r in linhas)
    if tot_visitas:
        tot_conv = round((tot_vendas * 100.0 / tot_visitas), 2)
    else:
        tot_conv = 0
    tot_fat = round(sum(fat_serie), 2)
    corpo += ("<div class='grid' style='margin-bottom:18px'>"
              "<div class='stat'><div class='num'>" + str(tot_visitas)
              + "</div><div class='lab'>Visitas no período</div></div>"
              "<div class='stat'><div class='num'>" + str(tot_vendas)
              + "</div><div class='lab'>Vendas no período</div></div>"
              "<div class='stat'><div class='num'>R$ %.2f" % tot_fat
              + "</div><div class='lab'>Faturamento no período</div></div>"
              "<div class='stat'><div class='num'>" + ("%.2f%%" % tot_conv)
              + "</div><div class='lab'>Conversão</div></div>"
              "</div>")
    corpo += ("<div class='card'><h2>Evolução diária</h2>"
              "<div class='sub'>Faturamento diário (R$) e visitas no período</div>"
              "<div class='grafico-box'>"
              "<canvas id='graficoDesempenho'></canvas></div></div>")
    corpo += ("<script src='https://cdn.jsdelivr.net/npm/"
              "chart.js@4.4.1/dist/chart.umd.min.js'></script>")
    corpo += ("<script>var rotulos = " + json.dumps(rotulos) + ";"
              "var visitas = " + json.dumps(visitas_serie) + ";"
              "var faturamento = " + json.dumps(fat_serie) + ";"
              "new Chart(document.getElementById('graficoDesempenho'), {"
              "type:'line',"
              "data:{labels:rotulos,datasets:["
              "{label:'Visitas',data:visitas,borderColor:'#3483FA',"
              "backgroundColor:'rgba(52,131,250,0.12)',yAxisID:'y',"
              "tension:0.3,fill:true},"
              "{label:'Faturamento (R$)',data:faturamento,"
              "borderColor:'#FFE600',"
              "backgroundColor:'rgba(255,230,0,0.25)',yAxisID:'y1',"
              "tension:0.3,fill:true}]},"
              "options:{responsive:true,maintainAspectRatio:false,"
              "plugins:{legend:{position:'top'}},"
              "scales:{y:{type:'linear',position:'left',"
              "title:{display:true,text:'Visitas'},beginAtZero:true},"
              "y1:{type:'linear',position:'right',"
              "title:{display:true,text:'Faturamento (R$)'},"
              "beginAtZero:true,grid:{drawOnChartArea:false}}}}});</script>")
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
        if visitas:
            conv = round((vendidos * 100.0 / visitas), 2)
            conv_txt = "%.2f%%" % conv
        else:
            conv_txt = "-"
        v_ant = r["visitas_ant"] or 0
        if v_ant > 0:
            delta_v = round(((visitas - v_ant) * 100.0 / v_ant), 1)
            if delta_v > 0:
                tend_v = "<span class='alerta subiu'>▲ +" + str(delta_v) + "%</span>"
            elif delta_v < 0:
                tend_v = "<span class='alerta caiu'>▼ " + str(delta_v) + "%</span>"
            else:
                tend_v = "<span class='alerta estavel'>— 0%</span>"
        else:
            tend_v = "<span class='tag sem'>sem base</span>"
        s_ant = r["vendidos_ant"] or 0
        if s_ant > 0:
            delta_s = round(((vendidos - s_ant) * 100.0 / s_ant), 1)
            if delta_s > 0:
                tend_s = "<span class='alerta subiu'>▲ +" + str(delta_s) + "%</span>"
            elif delta_s < 0:
                tend_s = "<span class='alerta caiu'>▼ " + str(delta_s) + "%</span>"
            else:
                tend_s = "<span class='alerta estavel'>— 0%</span>"
        else:
            tend_s = "<span class='tag sem'>sem base</span>"
        linhas_html += ("<tr>"
                        "<td><b>" + esc(str(r["titulo"])) + "</b><br>"
                        "<small class='muted'>" + str(r["item_id"]) + "</small></td>"
                        "<td><span class='" + st_tag + "'>" + st_txt + "</span></td>"
                        "<td>R$ %.2f" % (r["preco"] or 0) + "</td>"
                        "<td>" + str(visitas) + " " + tend_v + "</td>"
                        "<td>" + str(vendidos) + " " + tend_s + "</td>"
                        "<td>" + conv_txt + "</td>"
                        "</tr>")
    corpo += ("<div class='card'><h2>Desempenho por anúncio "
              "<span class='badge'>" + str(len(linhas)) + "</span></h2>"
              "<div class='sub'>Visitas, vendas e conversão no período, "
              "com tendência vs período anterior</div>"
              "<div style='overflow-x:auto'><table>"
              "<thead><tr><th>Anúncio</th><th>Status</th><th>Preço</th>"
              "<th>Visitas</th><th>Vendas</th><th>Conversão</th></tr></thead>"
              "<tbody>" + linhas_html + "</tbody></table></div>"
              "<div class='muted'>▲/▼ compara com o período anterior de "
              "mesma duração. O histórico acumula a cada atualização.</div></div>")
    return pagina_loja("Desempenho", cid, c["cliente"], "desempenho", corpo)


def br(v, decimais=2):
    if v is None:
        return None
    s = format(float(v), ",." + str(decimais) + "f")
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def var_html(hoje, ontem, fmt="R$"):
    if ontem is None or ontem == 0:
        return "<div class='var estavel'>— sem base anterior</div>"
    delta = hoje - ontem
    pct = (delta * 100.0 / ontem) if ontem else 0
    if fmt == "n":
        un = ""
        dec = 0
    else:
        un = "R$ "
        dec = 2
    if delta > 0:
        return ("<div class='var subiu'>▲ +" + un + br(delta, dec)
                + " (+" + br(pct, 1) + "%)</div>")
    elif delta < 0:
        return ("<div class='var caiu'>▼ " + un + br(abs(delta), dec)
                + " (" + br(pct, 1) + "%)</div>")
    return "<div class='var estavel'>— 0%</div>"

@app.route("/painel/<int:cid>")
@login_required
def painel_detalhe(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado",
                      "<div class='card'><h2>Acesso restrito</h2></div>")
    hoje_iso = datetime.date.today().isoformat()
    ontem_iso = (datetime.date.today()
                 - datetime.timedelta(days=1)).isoformat()
    c, vendas = calcular_vendas(cid)
    if not c:
        return pagina("Não encontrada",
                      "<div class='card'><h2>Loja não encontrada</h2></div>")
    with banco() as conn:
        conta = consultar(conn, "SELECT * FROM dados_conta WHERE conexao_id=%s", (cid,))
        conta = conta[0] if conta else None
        ads_dias = consultar(conn, "SELECT * FROM ads_dia WHERE conexao_id=%s "
                                   "AND data >= %s ORDER BY data",
                             (cid, (datetime.date.today()
                                    - datetime.timedelta(days=6)).isoformat()))
        perg_pend = consultar(conn, "SELECT COUNT(*) AS n FROM perguntas "
                                    "WHERE conexao_id=%s AND status != 'ANSWERED'", (cid,))
        envios_hoje = consultar(conn, "SELECT COUNT(*) AS n FROM envios "
                                      "WHERE conexao_id=%s AND SUBSTRING(data,1,10)=%s",
                                (cid, hoje_iso))
        ult = consultar(conn, "SELECT MAX(atualizado_em) AS ult FROM anuncios "
                              "WHERE conexao_id=%s", (cid,))
    ultima = ult[0]["ult"] if ult and ult[0]["ult"] else None
    perguntas_pendentes = perg_pend[0]["n"] if perg_pend else 0
    envios_dia = envios_hoje[0]["n"] if envios_hoje else 0
    atualizando = False
    if (ultima is None or (int(time.time()) - ultima) > GATILHO_AUTO_SEG) \
            and c["user_id"]:
        with LOCK_ATUALIZACAO:
            if cid not in ATUALIZANDO:
                ATUALIZANDO.add(cid)
                threading.Thread(target=executar_atualizacao_bg,
                                 args=(cid,), daemon=True).start()
            atualizando = True
    por_dia = {}
    for v in vendas:
        dia = v["data"][:10]
        d = por_dia.setdefault(dia, {"fat": 0.0, "qtd": 0,
                                     "lucro": 0.0, "pendente": False})
        d["fat"] += v["receita"]
        d["qtd"] += 1
        if v["sem_itens"] or v["sem_custo"]:
            d["pendente"] = True
        else:
            d["lucro"] += v["mc"]
    hoje_info = por_dia.get(hoje_iso, {"fat": 0.0, "qtd": 0,
                                       "lucro": 0.0, "pendente": False})
    ontem_info = por_dia.get(ontem_iso, {"fat": 0.0, "qtd": 0,
                                         "lucro": 0.0, "pendente": False})
    fat_dia = hoje_info["fat"]
    qtd_dia = hoje_info["qtd"]
    lucro_dia = hoje_info["lucro"]
    tem_pendente_hoje = hoje_info["pendente"]
    ad_hoje = None
    ad_ontem = None
    for r in ads_dias:
        if r["data"] == hoje_iso:
            ad_hoje = r
        if r["data"] == ontem_iso:
            ad_ontem = r
    gasto_ads = ad_hoje["gasto"] if ad_hoje and ad_hoje["gasto"] is not None else None
    fat_ads = ad_hoje["faturamento"] if ad_hoje and ad_hoje["faturamento"] is not None else None
    gasto_ads_ontem = ad_ontem["gasto"] if ad_ontem and ad_ontem["gasto"] is not None else None
    fat_ads_ontem = ad_ontem["faturamento"] if ad_ontem and ad_ontem["faturamento"] is not None else None
    ult_txt = hora_br(ultima)
    corpo = "<h2 style='margin-bottom:14px'>Resumo do dia</h2>"
    corpo += ("<div style='display:flex;gap:12px;align-items:center;"
              "flex-wrap:wrap;margin-bottom:14px'>"
              "<a class='btn-acoes' href='/atualizar/resumo/"
              + str(cid) + "'>🔄 Atualizar agora</a>"
              "<span style='color:#6b7280;font-size:13px'>"
              "Última atualização: " + ult_txt + "</span></div>")
    if atualizando:
        corpo += ("<div class='aviso'>Atualização automática em andamento — "
                  "os dados de hoje e de Ads aparecem em instantes. "
                  "A página vai recarregar sozinha.</div>")
    if perguntas_pendentes > 0:
        corpo += ("<div class='aviso'>💬 Você tem <b>"
                  + str(perguntas_pendentes)
                  + " pergunta(s) pendente(s)</b> para responder nos anúncios. "
                  "Responder rápido aumenta a chance de fechar a venda.</div>")
    if lucro_dia <= 0:
        lucro_html = "<span class='alerta urgente'>R$ %.2f</span>" % lucro_dia
    else:
        lucro_html = "R$ %.2f" % lucro_dia
    gasto_ads_var = ""
    if gasto_ads is not None:
        gasto_ads_var = var_html(gasto_ads, gasto_ads_ontem)
    fat_ads_var = ""
    if fat_ads is not None:
        fat_ads_var = var_html(fat_ads, fat_ads_ontem)
    corpo += ("<div class='grid' style='margin-bottom:18px'>"
              "<div class='stat'><div class='num'>R$ %.2f" % fat_dia
              + "</div><div class='lab'>Faturamento do dia</div>"
              + var_html(fat_dia, ontem_info["fat"]) + "</div>"
              "<div class='stat'><div class='num'>" + str(qtd_dia)
              + "</div><div class='lab'>Vendas do dia</div>"
              + var_html(qtd_dia, ontem_info["qtd"], "n") + "</div>"
              "<div class='stat'><div class='num'>" + lucro_html
              + "</div><div class='lab'>Lucro do dia (MC)</div>"
              + var_html(lucro_dia, ontem_info["lucro"]) + "</div>"
              "<div class='stat'><div class='num'>" + str(envios_dia)
              + "</div><div class='lab'>Envios do dia</div></div>"
              "<div class='stat'><div class='num'>"
              + (("R$ %.2f" % gasto_ads) if gasto_ads is not None
                 else "<span class='tag sem'>—</span>")
              + "</div><div class='lab'>Gasto Ads do dia</div>"
              + gasto_ads_var + "</div>"
              "<div class='stat'><div class='num'>"
              + (("R$ %.2f" % fat_ads) if fat_ads is not None
                 else "<span class='tag sem'>—</span>")
              + "</div><div class='lab'>Faturamento Ads do dia</div>"
              + fat_ads_var + "</div>"
              "</div>")
    if tem_pendente_hoje:
        corpo += ("<div class='aviso'>Há vendas de hoje sem custo cadastrado — "
                  "o lucro do dia pode estar incompleto. "
                  "<a class='link' href='/custos/" + str(cid)
                  + "'>Cadastrar custos</a>.</div>")
    rotulos7, fat7, lucro7 = [], [], []
    d = datetime.date.today() - datetime.timedelta(days=6)
    while d <= datetime.date.today():
        iso = d.isoformat()
        info = por_dia.get(iso, {"fat": 0.0, "qtd": 0,
                                 "lucro": 0.0, "pendente": False})
        rotulos7.append(d.strftime("%d/%m"))
        fat7.append(round(info["fat"], 2))
        lucro7.append(round(info["lucro"], 2))
        d += datetime.timedelta(days=1)
    corpo += ("<div class='card'><h2>Evolução dos últimos 7 dias</h2>"
              "<div class='sub'>Faturamento e lucro (MC) por dia</div>"
              "<div class='grafico-box'>"
              "<canvas id='graficoResumo'></canvas></div></div>")
    corpo += ("<script src='https://cdn.jsdelivr.net/npm/"
              "chart.js@4.4.1/dist/chart.umd.min.js'></script>")
    corpo += ("<script>var r7 = " + json.dumps(rotulos7) + ";"
              "var f7 = " + json.dumps(fat7) + ";"
              "var l7 = " + json.dumps(lucro7) + ";"
              "new Chart(document.getElementById('graficoResumo'), {"
              "type:'line',"
              "data:{labels:r7,datasets:["
              "{label:'Faturamento (R$)',data:f7,borderColor:'#3483FA',"
              "backgroundColor:'rgba(52,131,250,0.12)',tension:0.3,fill:true},"
              "{label:'Lucro (MC R$)',data:l7,borderColor:'#1a9d5c',"
              "backgroundColor:'rgba(26,157,92,0.12)',tension:0.3,fill:true}]},"
              "options:{responsive:true,maintainAspectRatio:false,"
              "plugins:{legend:{position:'top'}},"
              "scales:{y:{type:'linear',beginAtZero:true,"
              "title:{display:true,text:'R$'}}}}});</script>")
    ads_map = {r["data"]: r for r in ads_dias}
    linhas_html = ""
    d = datetime.date.today() - datetime.timedelta(days=6)
    while d <= datetime.date.today():
        iso = d.isoformat()
        info = por_dia.get(iso, {"fat": 0.0, "qtd": 0,
                                 "lucro": 0.0, "pendente": False})
        ad = ads_map.get(iso)
        if ad and ad["gasto"] is not None:
            gasto_txt = "R$ %.2f" % ad["gasto"]
        else:
            gasto_txt = "<span class='tag sem'>—</span>"
        if ad and ad["faturamento"] is not None:
            fatads_txt = "R$ %.2f" % ad["faturamento"]
        else:
            fatads_txt = "<span class='tag sem'>—</span>"
        if info["pendente"]:
            lucro_txt = "<span class='tag sem'>custo pendente</span>"
        else:
            lucro_txt = "R$ %.2f" % info["lucro"]
        badge = ""
        if iso == hoje_iso:
            badge = " <span class='badge'>hoje</span>"
        linhas_html += ("<tr><td><b>" + d.strftime("%d/%m") + "</b>"
                        + badge + "</td>"
                        "<td>R$ %.2f" % info["fat"] + "</td><td>"
                        + str(info["qtd"]) + "</td><td>" + lucro_txt
                        + "</td><td>" + gasto_txt + "</td><td>"
                        + fatads_txt + "</td></tr>")
        d += datetime.timedelta(days=1)
    corpo += ("<div class='card'><h2>Últimos 7 dias</h2>"
              "<div class='sub'>Faturamento, vendas, lucro (MC) e Ads por dia</div>"
              "<div style='overflow-x:auto'><table>"
              "<thead><tr><th>Dia</th><th>Faturamento</th><th>Vendas</th>"
              "<th>Lucro (MC)</th><th>Gasto Ads</th>"
              "<th>Faturamento Ads</th></tr></thead>"
              "<tbody>" + linhas_html + "</tbody></table></div>"
              "<div class='muted'>Lucro (MC) = Receita − Custo − Imposto − "
              "Comissão − Frete, calculado por venda. Vendas sem custo "
              "cadastrado aparecem como 'custo pendente'.</div></div>")
    if conta:
        corpo += ("<div class='card'><h2>Conta</h2>"
                  "<div class='sub'>Informações do vendedor</div>"
                  "<div class='grid'>"
                  "<div class='stat'><div class='num'>"
                  + esc(str(conta["nickname"]))
                  + "</div><div class='lab'>Nickname</div></div>"
                  "<div class='stat'><div class='num'>"
                  + esc(str(conta["reputacao"]))
                  + "</div><div class='lab'>Reputação</div></div>"
                  "<div class='stat'><div class='num'>"
                  + str(conta["pontos"])
                  + "</div><div class='lab'>Vendas concluídas</div></div>"
                  "</div></div>")
    if atualizando:
        corpo += ("<script>setTimeout(function(){ location.reload(); }, "
                  "90000);</script>")
    return pagina_loja("Resumo", cid, c["cliente"], "resumo", corpo)
@app.route("/atualizar/<tipo>/<int:cid>")
@login_required
def atualizar_tipo(tipo, cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado",
                      "<div class='card'><h2>Acesso restrito</h2></div>")
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
    if not c:
        return pagina("Sem loja",
                      "<div class='card'><h2>Nenhuma loja conectada</h2></div>")
    token = token_atual(c)
    if not token:
        return pagina("Erro",
                      "<div class='card'><h2>Falha ao renovar o token</h2></div>")
    user_id = c["user_id"]
    if user_id:
        if tipo in ("resumo", "vendas"):
            puxar_pedidos(c["id"], token, user_id)
            puxar_envios(c["id"], token, user_id)
        if tipo in ("resumo", "anuncios", "desempenho",
                    "demandas", "custos"):
            puxar_anuncios(c["id"], token, user_id)
            puxar_metricas(c["id"], token)
        if tipo == "resumo":
            puxar_perguntas(c["id"], token, user_id)
            try:
                puxar_ads_dia(c["id"], token, user_id)
            except Exception:
                pass
        if tipo == "promocoes":
            puxar_promocoes(c["id"], token, user_id)
        if tipo == "campanhas":
            try:
                puxar_ads(c["id"], token, user_id)
                puxar_ads_dia(c["id"], token, user_id)
            except Exception:
                pass
    if tipo in ("resumo", "desempenho"):
        gravar_historico(c["id"])
    if tipo == "resumo":
        destino = "/painel/" + str(cid)
    else:
        destino = "/" + tipo + "/" + str(cid)
    return redirect(destino)


@app.route("/atualizar")
@login_required
def atualizar():
    cid = request.args.get("cid", type=int)
    with banco() as conn:
        if cid:
            c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        else:
            c = consultar(conn, "SELECT * FROM conexoes "
                                "WHERE status='ativa' ORDER BY id LIMIT 1")
        c = c[0] if c else None
    if not c:
        return pagina("Sem loja",
                      "<div class='card'><h2>Nenhuma loja conectada</h2>"
                      "<p><a class='link' href='/'>Conectar</a></p></div>")
    if not pode_ver_loja(c["id"]):
        return pagina("Acesso negado",
                      "<div class='card'><h2>Acesso restrito</h2></div>")
    ok = executar_atualizacao(c["id"])
    if not ok:
        return pagina("Erro",
                      "<div class='card'><h2>Falha ao renovar o token</h2>"
                      "<p>Tente conectar a loja novamente.</p></div>")
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
        executar(conn, "UPDATE conexoes SET access_token=%s, "
                       "refresh_token=%s, expires_at=%s, status='ativa' "
                       "WHERE id=%s",
                 (dados["access_token"], dados["refresh_token"],
                  agora + dados["expires_in"], c["id"]))
    return dados["access_token"]


def job_refresh():
    agora = int(time.time())
    with banco() as conn:
        conexoes = consultar(conn, "SELECT * FROM conexoes "
                                   "WHERE status='ativa' AND expires_at < %s",
                             (agora + 1800,))
        for c in conexoes:
            try:
                dados = renovar(c["refresh_token"])
                executar(conn, "UPDATE conexoes SET access_token=%s, "
                               "refresh_token=%s, expires_at=%s, "
                               "status='ativa' WHERE id=%s",
                         (dados["access_token"], dados["refresh_token"],
                          agora + dados["expires_in"], c["id"]))
            except Exception:
                executar(conn, "UPDATE conexoes SET status='expirada' "
                               "WHERE id=%s", (c["id"],))


# ---------- PUXAR DADOS ----------

def api_get(token, path, params=None):
    try:
        r = requests.get(API + path,
                         headers={"Authorization": "Bearer " + (token or "")},
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
                        DO UPDATE SET mensagem=EXCLUDED.mensagem,
                          quando=EXCLUDED.quando""",
                 (conexao_id, categoria, (mensagem or "")[:300],
                  int(time.time())))


def gravar_historico(conexao_id):
    hoje = datetime.date.today().isoformat()
    agora = int(time.time())
    with banco() as conn:
        linhas = consultar(conn, "SELECT item_id, vendidos FROM anuncios "
                                 "WHERE conexao_id=%s", (conexao_id,))
        metricas = consultar(conn, "SELECT item_id, visitas FROM metricas "
                                   "WHERE conexao_id=%s", (conexao_id,))
    visitas_por_item = {m["item_id"]: (m["visitas"] or 0) for m in metricas}
    for l in linhas:
        item_id = l["item_id"]
        visitas = visitas_por_item.get(item_id, 0)
        vendidos = l["vendidos"] or 0
        with banco() as conn:
            executar(conn, """INSERT INTO desempenho_historico
                            (conexao_id, item_id, data, visitas, vendidos, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, item_id, data) DO UPDATE SET
                              visitas=EXCLUDED.visitas,
                              vendidos=EXCLUDED.vendidos,
                              atualizado_em=EXCLUDED.atualizado_em""",
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
        executar(conn, """INSERT INTO dados_conta
                        (conexao_id, user_id, nickname, nome, sobrenome,
                         reputacao, pontos, atualizado_em)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (conexao_id) DO UPDATE SET
                          user_id=EXCLUDED.user_id,
                          nickname=EXCLUDED.nickname, nome=EXCLUDED.nome,
                          sobrenome=EXCLUDED.sobrenome,
                          reputacao=EXCLUDED.reputacao,
                          pontos=EXCLUDED.pontos,
                          atualizado_em=EXCLUDED.atualizado_em""",
                 (conexao_id, dados.get("id"), dados.get("nickname"),
                  dados.get("first_name"), dados.get("last_name"),
                  rep.get("level_id"), pontos, int(time.time())))


def puxar_anuncios(conexao_id, token, user_id):
    ids = []
    offset = 0
    total = 50
    while offset < 200 and offset <= total:
        dados, erro = api_get(token,
                              "/users/" + str(user_id) + "/items/search",
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
        atuais = set(ids)
        velhos = [r["item_id"] for r in
                  consultar(conn, "SELECT item_id FROM anuncios "
                                  "WHERE conexao_id=%s", (conexao_id,))]
        for v in velhos:
            if v not in atuais:
                executar(conn, "DELETE FROM anuncios WHERE conexao_id=%s "
                               "AND item_id=%s", (conexao_id, v))
    linhas = []
    for i in range(0, len(ids), 20):
        lote = ids[i:i + 20]
        dados, erro = api_get(token, "/items",
                              {"ids": ",".join(lote)})
        if erro or not isinstance(dados, list):
            registrar_erro(conexao_id, "anuncios",
                           erro or "lote sem resposta")
            continue
        for r in dados:
            if not isinstance(r, dict):
                continue
            det = r.get("body")
            if not isinstance(det, dict) or not det.get("id"):
                continue
            fotos = 0
            pics = det.get("pictures")
            if isinstance(pics, list):
                fotos = len(pics)
            vid = det.get("video_id")
            if vid is None:
                clips = None
            elif vid:
                clips = 1
            else:
                clips = 0
            tags = det.get("tags") or []
            peso = None
            shipping = det.get("shipping") or {}
            dims = shipping.get("dimensions") or ""
            if isinstance(dims, str) and "," in dims:
                try:
                    peso = float(dims.split(",")[-1].strip()) / 1000.0
                except Exception:
                    peso = None
            linhas.append((conexao_id, det.get("id"), det.get("title"),
                           det.get("price"), det.get("available_quantity"),
                           det.get("status"), det.get("sold_quantity"),
                           agora, fotos, clips,
                           json.dumps(tags, ensure_ascii=False),
                           peso, det.get("seller_custom_field")))
    with banco() as conn:
        for t in linhas:
            executar(conn, """INSERT INTO anuncios
                            (conexao_id, item_id, titulo, preco, quantidade,
                             status, vendidos, atualizado_em, fotos, clips,
                             tags, peso, sku)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, item_id) DO UPDATE SET
                              titulo=EXCLUDED.titulo, preco=EXCLUDED.preco,
                              quantidade=EXCLUDED.quantidade,
                              status=EXCLUDED.status,
                              vendidos=EXCLUDED.vendidos,
                              atualizado_em=EXCLUDED.atualizado_em,
                              fotos=EXCLUDED.fotos, clips=EXCLUDED.clips,
                              tags=EXCLUDED.tags, peso=EXCLUDED.peso,
                              sku=EXCLUDED.sku""", t)


def puxar_metricas(conexao_id, token):
    with banco() as conn:
        linhas = consultar(conn, "SELECT item_id, vendidos FROM anuncios "
                                 "WHERE conexao_id=%s", (conexao_id,))
    itens = [l["item_id"] for l in linhas]
    if not itens:
        return
    vendidos_por_item = {l["item_id"]: (l["vendidos"] or 0) for l in linhas}
    agora = int(time.time())
    total_puxado = 0
    for i in range(0, len(itens), 100):
        lote = itens[i:i + 100]
        dados, erro = api_get(token, "/visits/items",
                              {"ids": ",".join(lote)})
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
            if visitas:
                conversao = round((vendidos * 100.0 / visitas), 2)
            else:
                conversao = 0
            with banco() as conn:
                executar(conn, """INSERT INTO metricas
                                (conexao_id, item_id, vendidos, visitas,
                                 conversao, atualizado_em)
                                VALUES (%s,%s,%s,%s,%s,%s)
                                ON CONFLICT (conexao_id, item_id) DO UPDATE SET
                                  vendidos=EXCLUDED.vendidos,
                                  visitas=EXCLUDED.visitas,
                                  conversao=EXCLUDED.conversao,
                                  atualizado_em=EXCLUDED.atualizado_em""",
                         (conexao_id, item_id, vendidos, visitas,
                          conversao, agora))
            total_puxado += 1
    if total_puxado == 0:
        registrar_erro(conexao_id, "metricas",
                       "nenhum dado de visita retornado")


def puxar_perguntas(conexao_id, token, user_id):
    dados, erro = api_get(token, "/questions/search",
                          {"seller_id": user_id, "api_version": 4,
                           "limit": 50})
    if erro or not dados:
        registrar_erro(conexao_id, "perguntas", erro or "sem resposta")
        return
    perguntas = dados.get("questions") or []
    agora = int(time.time())
    with banco() as conn:
        executar(conn, "DELETE FROM perguntas WHERE conexao_id=%s",
                 (conexao_id,))
    for q in perguntas:
        resp = q.get("answer") or {}
        with banco() as conn:
            executar(conn, """INSERT INTO perguntas
                            (conexao_id, pergunta_id, item_id, texto,
                             status, resposta, data, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, pergunta_id) DO UPDATE SET
                              item_id=EXCLUDED.item_id,
                              texto=EXCLUDED.texto, status=EXCLUDED.status,
                              resposta=EXCLUDED.resposta,
                              data=EXCLUDED.data,
                              atualizado_em=EXCLUDED.atualizado_em""",
                     (conexao_id, str(q.get("id")), q.get("item_id"),
                      q.get("text"), q.get("status"), resp.get("text"),
                      q.get("date_created"), agora))


def puxar_envios(conexao_id, token, user_id):
    dados, erro = api_get(token, "/shipments/search",
                          {"seller_id": user_id, "limit": 50})
    if erro or not dados:
        registrar_erro(conexao_id, "envios", erro or "sem resposta")
        return
    resultados = dados.get("results") or []
    agora = int(time.time())
    with banco() as conn:
        executar(conn, "DELETE FROM envios WHERE conexao_id=%s",
                 (conexao_id,))
    for s in resultados[:20]:
        sid = str(s.get("id"))
        custo_frete = None
        det, det_erro = api_get(token, "/shipments/" + sid)
        if not det_erro and det:
            custo_frete = det.get("cost_to_seller")
        with banco() as conn:
            executar(conn, """INSERT INTO envios
                            (conexao_id, envio_id, status, tracking,
                             pedido_id, data, custo_frete, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, envio_id) DO UPDATE SET
                              status=EXCLUDED.status,
                              tracking=EXCLUDED.tracking,
                              pedido_id=EXCLUDED.pedido_id,
                              data=EXCLUDED.data,
                              custo_frete=EXCLUDED.custo_frete,
                              atualizado_em=EXCLUDED.atualizado_em""",
                     (conexao_id, sid, s.get("status"),
                      s.get("tracking_number"), s.get("order_id"),
                      s.get("date_created"), custo_frete, agora))


def puxar_promocoes(conexao_id, token, user_id):
    promos = []
    viu_erro = None
    for st in ("active", "candidate", "paused", "finished"):
        dados, erro = api_get(token,
                              "/sellers/" + str(user_id) + "/promotions",
                              {"promotion_type": "PRICE_DISCOUNT",
                               "status": st, "limit": 50})
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
        executar(conn, "DELETE FROM promocoes WHERE conexao_id=%s",
                 (conexao_id,))
        executar(conn, "DELETE FROM promocoes_itens WHERE conexao_id=%s",
                 (conexao_id,))
        for p in promos:
            itens = p.get("items")
            if isinstance(itens, list):
                qtd = len(itens)
            else:
                qtd = None
            executar(conn, """INSERT INTO promocoes
                            (conexao_id, promocao_id, tipo, nome, status,
                             inicio, fim, qtd_itens, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, promocao_id) DO UPDATE SET
                              tipo=EXCLUDED.tipo, nome=EXCLUDED.nome,
                              status=EXCLUDED.status,
                              inicio=EXCLUDED.inicio, fim=EXCLUDED.fim,
                              qtd_itens=EXCLUDED.qtd_itens,
                              atualizado_em=EXCLUDED.atualizado_em""",
                     (conexao_id, str(p.get("id")),
                      p.get("type") or p.get("promotion_type"),
                      p.get("name"), p.get("status"),
                      p.get("start_date"), p.get("end_date"), qtd, agora))
            if isinstance(itens, list):
                for it in itens:
                    if isinstance(it, dict):
                        item_id = it.get("id")
                        preco_promo = it.get("price") or it.get("sale_price")
                    else:
                        item_id = it
                        preco_promo = None
                    if item_id:
                        executar(conn, """INSERT INTO promocoes_itens
                            (conexao_id, item_id, promocao_id,
                             preco_promocional, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, item_id, promocao_id)
                            DO UPDATE SET
                              preco_promocional=EXCLUDED.preco_promocional,
                              atualizado_em=EXCLUDED.atualizado_em""",
                                 (conexao_id, str(item_id),
                                  str(p.get("id")), preco_promo, agora))


def puxar_ads(conexao_id, token, user_id):
    cab = {"Authorization": "Bearer " + (token or ""), "Api-Version": "2"}
    base = "/advertising/advertisers/" + str(user_id) + "/product_ads"
    agora = int(time.time())
    campanhas = []
    offset = 0
    while offset < 200:
        try:
            r = requests.get(API + base + "/campaigns/search",
                             headers=cab,
                             params={"limit": 50, "offset": offset},
                             timeout=25)
            if r.status_code != 200:
                registrar_erro(conexao_id, "ads",
                               "campanhas HTTP " + str(r.status_code)
                               + ": " + r.text[:180])
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
        executar(conn, "DELETE FROM ads_campanhas WHERE conexao_id=%s",
                 (conexao_id,))
        for c in campanhas:
            executar(conn, """INSERT INTO ads_campanhas
                            (conexao_id, campanha_id, nome, status, tipo,
                             data_inicio, data_fim, orcamento, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, campanha_id) DO UPDATE SET
                              nome=EXCLUDED.nome, status=EXCLUDED.status,
                              tipo=EXCLUDED.tipo,
                              data_inicio=EXCLUDED.data_inicio,
                              data_fim=EXCLUDED.data_fim,
                              orcamento=EXCLUDED.orcamento,
                              atualizado_em=EXCLUDED.atualizado_em""",
                     (conexao_id, str(c.get("id")), c.get("name"),
                      c.get("status"), c.get("type") or c.get("campaign_type"),
                      c.get("start_date"), c.get("end_date"),
                      c.get("budget") or c.get("daily_budget"), agora))
    ads = []
    offset = 0
    while offset < 200:
        try:
            r = requests.get(API + base + "/ads/search", headers=cab,
                             params={"limit": 50, "offset": offset},
                             timeout=25)
            if r.status_code != 200:
                registrar_erro(conexao_id, "ads",
                               "anuncios HTTP " + str(r.status_code)
                               + ": " + r.text[:180])
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
        executar(conn, "DELETE FROM ads_metricas WHERE conexao_id=%s",
                 (conexao_id,))
        for ad in ads:
            met = ad.get("metrics") or {}
            executar(conn, """INSERT INTO ads_metricas
                            (conexao_id, ad_id, campanha_id, item_id,
                             impressoes, cliques, ctr, gasto, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, ad_id) DO UPDATE SET
                              campanha_id=EXCLUDED.campanha_id,
                              item_id=EXCLUDED.item_id,
                              impressoes=EXCLUDED.impressoes,
                              cliques=EXCLUDED.cliques, ctr=EXCLUDED.ctr,
                              gasto=EXCLUDED.gasto,
                              atualizado_em=EXCLUDED.atualizado_em""",
                     (conexao_id, str(ad.get("id")),
                      ad.get("campaign_id") or ad.get("ad_group_id"),
                      ad.get("item_id"), met.get("impressions"),
                      met.get("clicks"), met.get("ctr"),
                      met.get("total_spend"), agora))


def puxar_ads_dia(conexao_id, token, user_id):
    hoje = datetime.date.today().isoformat()
    cab = {"Authorization": "Bearer " + (token or ""), "Api-Version": "2"}
    url = (API + "/advertising/advertisers/" + str(user_id)
           + "/product_ads/metrics")
    try:
        r = requests.get(url, headers=cab,
                         params={"date_from": hoje, "date_to": hoje},
                         timeout=25)
        if r.status_code != 200:
            registrar_erro(conexao_id, "ads_dia",
                           "HTTP " + str(r.status_code) + ": " + r.text[:180])
            return
        dados = r.json()
    except Exception as e:
        registrar_erro(conexao_id, "ads_dia", str(e))
        return
    if isinstance(dados, dict) and isinstance(dados.get("results"), list) \
            and dados["results"]:
        dados = dados["results"][0]
    if not isinstance(dados, dict):
        registrar_erro(conexao_id, "ads_dia",
                       "resposta inesperada da API de Ads")
        return
    gasto = None
    for k in ("total_spend", "cost", "spend", "total_cost"):
        if dados.get(k) is not None:
            try:
                gasto = float(dados[k])
                break
            except Exception:
                pass
    fat = None
    for k in ("total_revenue", "revenue", "sales", "total_sales",
              "net_revenue"):
        if dados.get(k) is not None:
            try:
                fat = float(dados[k])
                break
            except Exception:
                pass
    imp = dados.get("impressions")
    cli = dados.get("clicks")
    with banco() as conn:
        executar(conn, """INSERT INTO ads_dia
                        (conexao_id, data, gasto, faturamento, impressoes,
                         cliques, atualizado_em)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (conexao_id, data) DO UPDATE SET
                          gasto=EXCLUDED.gasto,
                          faturamento=EXCLUDED.faturamento,
                          impressoes=EXCLUDED.impressoes,
                          cliques=EXCLUDED.cliques,
                          atualizado_em=EXCLUDED.atualizado_em""",
                 (conexao_id, hoje, gasto, fat, imp, cli, int(time.time())))
    try:
        r = requests.get(API + "/advertising/advertisers/" + str(user_id)
                         + "/product_ads/campaigns/metrics",
                         headers=cab,
                         params={"date_from": hoje, "date_to": hoje},
                         timeout=25)
        if r.status_code == 200:
            cj = r.json()
            if isinstance(cj, dict):
                resultados = cj.get("results")
            else:
                resultados = None
            if isinstance(resultados, list):
                with banco() as conn:
                    for item in resultados:
                        cid_camp = item.get("campaign_id") or item.get("id")
                        if not cid_camp:
                            continue
                        cg = (item.get("total_spend")
                              or item.get("cost") or item.get("spend"))
                        cf = (item.get("total_revenue")
                              or item.get("revenue") or item.get("sales"))
                        try:
                            if cg is not None:
                                cg = float(cg)
                        except Exception:
                            cg = None
                        try:
                            if cf is not None:
                                cf = float(cf)
                        except Exception:
                            cf = None
                        executar(conn, """INSERT INTO ads_campanha_dia
                            (conexao_id, campanha_id, data, gasto,
                             faturamento, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, campanha_id, data)
                            DO UPDATE SET gasto=EXCLUDED.gasto,
                              faturamento=EXCLUDED.faturamento,
                              atualizado_em=EXCLUDED.atualizado_em""",
                                 (conexao_id, str(cid_camp), hoje, cg, cf,
                                  int(time.time())))
    except Exception:
        pass


def puxar_pedidos(conexao_id, token, user_id):
    lista = []
    ids_fechados = []
    offset = 0
    total = 50
    agora = int(time.time())
    while offset < 300 and offset <= total:
        dados, erro = api_get(token, "/orders/search",
                              {"seller": user_id, "sort": "date_desc",
                               "limit": 50, "offset": offset})
        if erro or not dados:
            registrar_erro(conexao_id, "pedidos", erro or "sem resposta")
            break
        resultados = dados.get("results") or []
        for o in resultados:
            oid = str(o.get("id"))
            lista.append((conexao_id, oid, o.get("status"),
                          o.get("total_amount"), o.get("currency_id"),
                          o.get("date_closed") or o.get("date_created"),
                          agora))
            if o.get("date_closed"):
                ids_fechados.append(oid)
        total = (dados.get("paging") or {}).get("total") or len(resultados)
        offset += len(resultados)
        if len(resultados) < 50:
            break
    with banco() as conn:
        executar(conn, "DELETE FROM pedidos WHERE conexao_id=%s",
                 (conexao_id,))
        cur = conn.cursor()
        cur.executemany("""INSERT INTO pedidos
                            (conexao_id, pedido_id, status, total, moeda,
                             fechado_em, atualizado_em)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (conexao_id, pedido_id) DO UPDATE SET
                              status=EXCLUDED.status, total=EXCLUDED.total,
                              moeda=EXCLUDED.moeda,
                              fechado_em=EXCLUDED.fechado_em,
                              atualizado_em=EXCLUDED.atualizado_em""", lista)
        ja_tem = {r["pedido_id"] for r in
                  consultar(conn, "SELECT DISTINCT pedido_id "
                                  "FROM pedidos_itens WHERE conexao_id=%s",
                            (conexao_id,))}
    faltantes = [i for i in ids_fechados[:50] if i not in ja_tem]
    for oid in faltantes:
        det, det_erro = api_get(token, "/orders/" + oid)
        if det_erro or not det:
            continue
        itens = det.get("order_items") or []
        if not isinstance(itens, list):
            continue
        with banco() as conn:
            for it in itens:
                item = it.get("item") or {}
                iid = item.get("id")
                if not iid:
                    continue
                executar(conn, """INSERT INTO pedidos_itens
                                (conexao_id, pedido_id, item_id,
                                 quantidade, preco_unitario, atualizado_em)
                                VALUES (%s,%s,%s,%s,%s,%s)
                                ON CONFLICT (conexao_id, pedido_id, item_id)
                                DO UPDATE SET
                                  quantidade=EXCLUDED.quantidade,
                                  preco_unitario=EXCLUDED.preco_unitario,
                                  atualizado_em=EXCLUDED.atualizado_em""",
                         (conexao_id, oid, str(iid), it.get("quantity"),
                          it.get("unit_price"), agora))


def executar_atualizacao(cid):
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
    if not c:
        return False
    token = token_atual(c)
    if not token:
        return False
    user_id = c["user_id"]
    puxar_conta(c["id"], token)
    if user_id:
        puxar_anuncios(c["id"], token, user_id)
        puxar_pedidos(c["id"], token, user_id)
        puxar_metricas(c["id"], token)
        puxar_perguntas(c["id"], token, user_id)
        puxar_envios(c["id"], token, user_id)
        puxar_promocoes(c["id"], token, user_id)
        try:
            puxar_ads(c["id"], token, user_id)
            puxar_ads_dia(c["id"], token, user_id)
        except Exception:
            pass
    gravar_historico(c["id"])
    return True


def executar_atualizacao_bg(cid):
    try:
        executar_atualizacao(cid)
    except Exception as e:
        try:
            registrar_erro(cid, "atualizacao", str(e)[:200])
        except Exception:
            pass
    finally:
        with LOCK_ATUALIZACAO:
            ATUALIZANDO.discard(cid)


def job_dados():
    with banco() as conn:
        conexoes = consultar(conn, "SELECT * FROM conexoes "
                                   "WHERE status='ativa'")
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
            try:
                puxar_ads(c["id"], token, c["user_id"])
                puxar_ads_dia(c["id"], token, c["user_id"])
            except Exception:
                pass
        gravar_historico(c["id"])


iniciar_banco()

scheduler = BackgroundScheduler()
scheduler.add_job(job_refresh, "interval", minutes=30)
scheduler.add_job(job_dados, "interval", minutes=60)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
