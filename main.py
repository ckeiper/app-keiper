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
AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo_Keiper_Consultoria.png")

app = Flask(__name__)
app.secret_key = SECRET_KEY
esc = html.escape

ATUALIZANDO = set()
LOCK_ATUALIZACAO = threading.Lock()
GATILHO_AUTO_SEG = 1800  # 30 minutos

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
        return ("<img src='/logo.png' alt='Keiper Consultoria' style='height:" + str(altura) +
                "px;vertical-align:middle;margin-right:10px;border-radius:8px'>")
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
    if session.get("tipo") == "admin":
        links += "<a class='btn' href='/usuarios' style='background:#fff;color:#3483FA;margin-right:8px'>👥 Usuários</a>"
    links += "<a class='btn' href='/'>+ Conectar loja</a></div>"
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>" + esc(titulo) + "</title>" + CSS + "</head><body>"
            + topo + marca + links +
            "<div class='wrap'>" + corpo + "</div>" + SCRIPT + "</body></html>")


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
    menu = "<div class='menu-lateral'><a class='voltar' href='/painel'>← Todas as lojas</a>"
    for chave, rotulo, href in itens:
        classe = "item" + (" atual" if secao == chave else "")
        menu += "<a class='" + classe + "' href='" + href + "'>" + rotulo + "</a>"
    menu += ("<a class='item' href='/atualizar?cid=" + str(cid) + "'>🔄 Atualizar dados</a>"
             "<a class='item perigo' href='/excluir/" + str(cid) + "'>🗑️ Excluir loja</a></div>")
    links = ""
    if session.get("tipo") == "admin":
        links += "<a class='btn' href='/usuarios' style='background:#fff;color:#3483FA;margin-right:8px'>👥 Usuários</a>"
    links += "<a class='btn sair' href='/logout'>Sair</a></div>"
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>" + esc(titulo) + "</title>" + CSS + "</head><body>"
            "<div class='top'><div><h1>" + img_logo(34) + "Keiper Consultoria</h1>"
            "<div class='brand'>" + esc(str(cliente)) + "</div></div>"
            + links +
            "<div class='wrap'><div class='layout'>" + menu +
            "<div class='conteudo'>" + corpo + "</div></div></div>" + SCRIPT + "</body></html>")


def barra_atualizar(cid, ultima):
    ult_txt = time.strftime("%d/%m/%Y %H:%M", time.localtime(ultima)) if ultima else "nunca"
    return ("<div style='display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:14px'>"
            "<a class='btn-acoes' href='/atualizar?cid=" + str(cid) + "'>🔄 Atualizar agora</a>"
            "<span style='color:#6b7280;font-size:13px'>Última atualização: " + ult_txt + "</span>"
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
            return pagina("Acesso negado", "<div class='card'><h2>Acesso restrito</h2><div class='sub'>Você não tem permissão para acessar esta área.</div></div>")
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
                 + img_logo(64) + "<h2>Login</h2><div class='aviso'>Usuário ou senha incorretos.</div>"
                 + form_login() + "</div>")
        return pagina("Login", corpo)
    corpo = ("<div class='card' style='max-width:420px;margin:60px auto;text-align:center'>"
             + img_logo(64) + "<h2>Login</h2><div class='sub'>Acesse o painel Keiper Consultoria</div>"
             + form_login() + "</div>")
    return pagina("Login", corpo)


def form_login():
    return ("<form method='post' action='/login' style='margin-top:12px'>"
            "<input name='username' required placeholder='Usuário' class='input' autocomplete='username'>"
            "<input type='password' name='senha' required placeholder='Senha' class='input' autocomplete='current-password'>"
            "<button class='btn-salvar' style='width:100%'>Entrar</button></form>"
            "<p style='margin-top:12px'><a class='link' href='/recuperar'>Esqueci minha senha</a></p>")


@app.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if request.method == "POST":
        ident = (request.form.get("ident") or "").strip()
        if not smtp_configurado():
            corpo = ("<div class='card' style='max-width:460px;margin:60px auto;text-align:center'>"
                     "<h2>Recuperar senha</h2>"
                     "<div class='aviso'>A recuperação por e-mail <b>não está configurada</b> no servidor. "
                     "Peça ao administrador para redefinir sua senha na tela de Usuários.</div>"
                     "<p><a class='link' href='/login'>← Voltar ao login</a></p></div>")
            return pagina("Recuperar senha", corpo)
        with banco() as conn:
            u = consultar(conn, "SELECT * FROM usuarios WHERE email=%s OR username=%s", (ident, ident))
        u = u[0] if u else None
        if u and u["email"]:
            token = criar_token_reset(u["id"])
            link = request.url_root.rstrip("/") + "/redefinir/" + token
            texto = ("Olá " + (u["nome"] or u["username"]) + ",\n\n"
                     "Recebemos um pedido de redefinição de senha do painel Keiper Consultoria.\n"
                     "Use o link abaixo para criar uma nova senha (válido por 30 minutos):\n\n"
                     + link + "\n\nSe não foi você quem pediu, ignore este e-mail.")
            enviar_email(u["email"], "Redefinição de senha — Keiper Consultoria", texto)
        corpo = ("<div class='card' style='max-width:460px;margin:60px auto;text-align:center'>"
                 "<h2>Recuperar senha</h2>"
                 "<div class='sucesso'>Se este e-mail estiver cadastrado, você receberá o link de redefinição em instantes. "
                 "Verifique também a caixa de spam.</div>"
                 "<p><a class='link' href='/login'>← Voltar ao login</a></p></div>")
        return pagina("Recuperar senha", corpo)
    corpo = ("<div class='card' style='max-width:460px;margin:60px auto;text-align:center'>"
             "<h2>Recuperar senha</h2>"
             "<div class='sub'>Digite seu usuário ou e-mail cadastrado. Enviaremos um link para criar uma nova senha.</div>"
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
                 "<div class='aviso'>Este link de redefinição é inválido ou expirou. Solicite um novo.</div>"
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
             "<input type='password' name='senha' required placeholder='Nova senha (mín. 6 caracteres)' class='input'>"
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
            linhas = consultar(conn, "SELECT cliente, user_id, status, expires_at FROM conexoes WHERE id=%s", (session.get("conexao_id"),))
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
        executar(conn, "UPDATE anuncios SET custo=%s WHERE conexao_id=%s AND item_id=%s", (custo, cid, item_id))
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
        executar(conn, "UPDATE ads_campanhas SET roas_objetivo=%s WHERE conexao_id=%s AND campanha_id=%s", (roas, cid, campanha_id))
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
        executar(conn, "UPDATE conexoes SET aliquota_imposto=%s, comissao_pct=%s WHERE id=%s", (aliquota, comissao, cid))
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
                executar(conn, "UPDATE anuncios SET custo=%s WHERE conexao_id=%s AND item_id=%s", (custo_v, cid, item_id))
            atualizados += 1
        else:
            nao_achados.append(str(sku))
    try:
        wb.close()
    except Exception:
        pass
    return redirect("/custos/" + str(cid) + "?ok=" + str(atualizados) + "&faltam=" + str(len(nao_achados)))


@app.route("/modelo_custos/<int:cid>")
@login_required
def modelo_custos(cid):
    if not pode_ver_loja(cid):
        return pagina("Acesso negado", "<div class='card'><h2>Acesso restrito</h2></div>")
    if openpyxl is None:
        return pagina("Erro", "<div class='card'><h2>Biblioteca de Excel não instalada</h2>"
                     "<div class='sub'>Adicione 'openpyxl' no requirements.txt e faça o deploy de novo.</div></div>")
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if not c:
            return "Loja não encontrada", 404
        anuncios = consultar(conn, "SELECT item_id, sku, titulo FROM anuncios WHERE conexao_id=%s ORDER BY titulo", (cid,))
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
            anuncios = consultar(conn, "SELECT * FROM anuncios WHERE conexao_id=%s ORDER BY titulo", (cid,))
    if not c:
        return pagina("Não encontrada", "<div class='card'><h2>Loja não encontrada</h2></div>")

    ok = request.args.get("ok")
    faltam = request.args.get("faltam")
    erro = request.args.get("erro")
    aliquota = c["aliquota_imposto"] if c["aliquota_imposto"] is not None else 0
    comissao = c["comissao_pct"] if c["comissao_pct"] is not None else 12
    ultima = ultima_atualizacao(cid)

    corpo = "<h2 style='margin-bottom:10px'>Custos</h2>" + barra_atualizar(cid, ultima)

    if erro == "sem_arquivo":
        corpo += "<div class='aviso'>Nenhum arquivo selecionado. Escolha a planilha e clique em Importar.</div>"
    elif erro == "arquivo_invalido":
        corpo += "<div class='aviso'>Não consegui ler o arquivo. Use um Excel no formato .xlsx.</div>"
    elif erro == "biblioteca":
        corpo += "<div class='aviso'>A biblioteca de Excel não está instalada no servidor. Adicione 'openpyxl' no requirements.txt e faça o deploy de novo.</div>"
    if ok is not None:
        msg = "<b>Importação concluída:</b> " + ok + " custo(s) atualizado(s)."
        if faltam and faltam != "0":
            msg += " " + faltam + " SKU(s) não encontrados nos anúncios desta loja (confira a grafia ou use o código MLB)."
        corpo += "<div class='sucesso'>" + msg + "</div>"

    com_custo = sum(1 for a in anuncios if a["custo"] is not None)
    corpo += ("<div class='grid' style='margin-bottom:18px'>"
              "<div class='stat'><div class='num'>" + str(len(anuncios)) + "</div><div class='lab'>Anúncios na loja</div></div>"
              "<div class='stat'><div class='num'>" + str(com_custo) + "</div><div class='lab'>Com custo cadastrado</div></div>"
              "<div class='stat'><div class='num'>" + str(len(anuncios) - com_custo) + "</div><div class='lab'>Falta cadastrar custo</div></div>"
              "</div>")

    corpo += ("<div class='card'><h2>Configuração da loja</h2>"
              "<div class='sub'>Usadas no cálculo da Margem de Contribuição na tela de Vendas</div>"
              "<form method='post' action='/salvar_config/" + str(cid) + "' style='display:flex;flex-wrap:wrap;gap:10px;align-items:center'>"
              "<label style='font-size:13px'>Alíquota de imposto (%):</label>"
              "<input type='number' step='0.01' min='0' name='aliquota' value='" + str(aliquota) + "' class='filtro' style='width:100px'>"
              "<label style='font-size:13px'>Comissão ML (%):</label>"
              "<input type='number' step='0.01' min='0' name='comissao' value='" + str(comissao) + "' class='filtro' style='width:100px'>"
              "<button class='filtro-btn'>Salvar</button>"
              "</form></div>")

    corpo += ("<div class='card'><h2>Importar custos em massa (Excel)</h2>"
              "<div class='sub'>Planilha com a <b>1ª coluna = SKU</b> e a <b>2ª coluna = custo (R$)</b>. "
              "Pode usar o SKU cadastrado no anúncio (campo personalizado do ML) ou o código MLB do item. "
              "A primeira linha é o cabeçalho e é ignorada.</div>"
              "<form method='post' action='/upload_custos/" + str(cid) + "' enctype='multipart/form-data' style='display:flex;flex-wrap:wrap;gap:10px;align-items:center'>"
              "<input type='file' name='arquivo' accept='.xlsx' required class='filtro' style='padding:6px'>"
              "<button class='filtro-btn'>Importar</button>"
              "</form>"
              "<div style='margin-top:10px'><a class='link' href='/modelo_custos/" + str(cid) + "'>⬇ Baixar modelo (Excel) já com os SKUs da loja — preencha a coluna Custo e suba de volta</a></div>"
              "</div>")

    if not anuncios:
        corpo += ("<div class='card' style='text-align:center;padding:40px'>"
                  "<h2>Nenhum anúncio carregado ainda</h2>"
                  "<div class='sub'>Use 'Atualizar dados' no menu lateral para buscar os anúncios da loja</div></div>")
        return pagina_loja("Custos", cid, c["cliente"], "custos", corpo)

    linhas_html = ""
    for a in anuncios:
        sku_txt = esc(str(a["sku"])) if a["sku"] else "<span class='tag sem'>—</span>"
        if a["custo"] is not None:
            custo_html = "<span id='custo-" + str(cid) + "-" + str(a["item_id"]) + "'>R$ %.2f</span>" % a["custo"]
        else:
            custo_html = "<span id='custo-" + str(cid) + "-" + str(a["item_id"]) + "'><a class='link' href='#' onclick='editarCusto(" + str(cid) + ", \"" + str(a["item_id"]) + "\"); return false;'>+ definir</a></span>"
        linhas_html += ("<tr><td>" + sku_txt + "</td>"
                        "<td><b>" + esc(str(a["titulo"])) + "</b><br><small class='muted'>" + str(a["item_id"]) + "</small></td>"
                        "<td>R$ %.2f" % (a["preco"] or 0) + "</td>"
                        "<td>" + custo_html + "</td></tr>")

    corpo += ("<div class='card'><h2>Custos por anúncio <span class='badge'>" + str(len(anuncios)) + "</span></h2>"
              "<div class='sub'>Clique em '+ definir' ou no valor para editar o custo de cada anúncio</div>"
              "<div style='overflow-x:auto'><table>"
              "<thead><tr><th>SKU</th><th>Anúncio</th><th>Preço</th><th>Custo</th></tr></thead>"
              "<tbody>" + linhas_html + "</tbody></table></div>"
              "<div class='muted'>O custo é usado no cálculo da Margem de Contribuição (tela de Vendas) e na análise de promoções.</div></div>")

    return pagina_loja("Custos", cid, c["cliente"], "custos", corpo)


def calcular_vendas(cid):
    with banco() as conn:
        c = consultar(conn, "SELECT * FROM conexoes WHERE id=%s", (cid,))
        c = c[0] if c else None
        if not c:
            return None, []
        pedidos = consultar(conn, "SELECT * FROM pedidos WHERE conexao_id=%s AND fechado_em IS NOT NULL ORDER BY fechado_em DESC LIMIT 100", (cid,))
        itens = consultar(conn, """SELECT pi.pedido_id, pi.quantidade, pi.preco_unitario,
                                          a.custo, a.peso
                                   FROM pedidos_itens pi
                                   LEFT JOIN anuncios a ON a.conexao_id=pi.conexao_id AND a.item_id=pi.item_id
                                   WHERE pi.conexao_id=%s""", (cid,))
        envios = consultar(conn, "SELECT pedido_id, custo_frete FROM envios WHERE conexao_id=%s AND custo_frete IS NOT NULL", (cid,))
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
             "<a class='btn-acoes cinza' href='/exportar_vendas/" + str(cid) + "'>
