"""Presentation-only diagnostic layout; all evidence comes from existing checks."""
from html import escape

CSS = """<style>
.listing-diag{--dink:#eaf2ff;--dmuted:#bdcce1;--dline:#34516e;color:var(--dink)}
.listing-diag .diag-hero{background:linear-gradient(115deg,#1b2647,#343b78);color:white;border-radius:18px;padding:26px;margin:0 0 20px}
.listing-diag .diag-eyebrow{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1.7px;color:#bdc9ee}
.listing-diag .diag-hero h2{font-size:23px;line-height:1.4;color:white;margin:10px 0}
.listing-diag .diag-hero p{font-size:12px;color:#d8e0f5;max-width:800px}
.listing-diag .diag-hero .diag-code{font-size:11px;color:#c4caee}
.listing-diag .diag-nav{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
.listing-diag .diag-nav a{border:1px solid #ffffff45;border-radius:9px;color:white;text-decoration:none;font-size:11px;padding:9px 13px;font-weight:700}
.listing-diag .diag-nav a:hover,.listing-diag .diag-nav a:focus-visible{background:#ffffff24;outline-offset:3px}
.listing-diag .diag-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px;margin:0 0 19px}
.listing-diag .diag-summary>a{display:block;text-decoration:none;color:inherit;border-radius:14px;background:white;border:1px solid var(--dline);padding:19px;transition:transform .16s,border-color .16s,box-shadow .16s}
.listing-diag .diag-summary>a:hover{transform:translateY(-3px);border-color:#7a72dd;box-shadow:0 10px 26px #4c53a318}
.listing-diag .diag-summary>a:focus-visible{outline:3px solid #6561d9;outline-offset:2px}
.listing-diag .diag-summary strong{display:block;font-size:26px;line-height:1.3;font-variant-numeric:tabular-nums}
.listing-diag .diag-summary span{display:block;font-size:11px;color:var(--dmuted);margin-top:5px}
.listing-diag .diag-actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin:16px 0 22px}
.listing-diag .diag-action{border:1px solid var(--dline);border-left:4px solid #c2c7d7;border-radius:14px;background:white;padding:20px;box-shadow:0 3px 15px #23355708}
.listing-diag .diag-action.alta{border-left-color:#d95d5d}.listing-diag .diag-action.media,.listing-diag .diag-action.revisar{border-left-color:#e3a64d}
.listing-diag .diag-action.baixa{border-left-color:#48a78a}
.listing-diag .diag-action .diag-priority{font-size:10px;text-transform:uppercase;letter-spacing:.8px;font-weight:800;color:#73819c}
.listing-diag .diag-action h3{font-size:15px;margin:11px 0;color:#26354f}
.listing-diag .diag-action p{font-size:12px;line-height:1.65;color:#65748f;margin:10px 0}
.listing-diag .diag-action .diag-next{padding:12px;border-radius:9px;background:#f3f5fc;color:#35436d}
.listing-diag .diag-actions-empty{padding:20px;background:white;border:1px solid var(--dline);border-radius:13px}
.listing-diag .diag-hint{margin:0 0 18px;color:#8290a5;font-size:11px}
@media(max-width:650px){.listing-diag .diag-summary{grid-template-columns:1fr 1fr}.listing-diag .diag-summary>a{padding:13px}.listing-diag .diag-hero{padding:20px}.listing-diag .diag-hero h2{font-size:19px}}
@media(prefers-reduced-motion:reduce){.listing-diag .diag-summary>a{transition:none}.listing-diag .diag-summary>a:hover{transform:none}}
body .conteudo .listing-diag .diag-summary>a,body .conteudo .listing-diag .diag-action,body .conteudo .listing-diag .diag-actions-empty{background:#142940;color:#eaf2ff}
body .conteudo .listing-diag #diag-acoes{background:#102238;padding:20px;border:1px solid #34516e;border-radius:14px}body .conteudo .listing-diag h2,body .conteudo .listing-diag h3,body .conteudo .listing-diag strong{color:#eaf2ff}
body .conteudo .listing-diag .diag-action p,body .conteudo .listing-diag .diag-priority,body .conteudo .listing-diag .diag-hint{color:#bdcce1}
body .conteudo .listing-diag .diag-next{background:#1c3552;color:#dcecff}
body .conteudo .listing-diag .diag-hint>a{background:#1c3552!important;color:#b9e5ff!important;border-color:#426184!important}
body .conteudo .listing-diag a:focus-visible{outline:3px solid #91d9fa;outline-offset:3px}
</style>"""

def hero(item, cid, item_id, results):
    title=escape(str(item.get("titulo") or "Anúncio sem título"))
    code=escape(str(item_id))
    high=sum(str(a.get("priority") or "").lower()=="alta" for a in results)
    review=sum(str(a.get("priority") or "").lower() in ("media","revisar") for a in results)
    total=len(results)
    out=CSS+"<div class='listing-diag'><header class='diag-hero'><div class='diag-eyebrow'>Saúde e desempenho do anúncio</div><h2>"+title+"</h2>"
    out+="<div class='diag-code'>"+code+"</div><p>Indicadores de vendas verificados, situação do anúncio e próximos pontos de atenção. Não atribuímos causas de queda sem evidências.</p>"
    out+="<nav class='diag-nav' aria-label='Navegação do diagnóstico'><a href='/desempenho/"+str(cid)+"'>← Desempenho</a>"
    out+="<a href='/anuncios/"+str(cid)+"'>Catálogo</a><a href='/anuncios/"+str(int(cid))+"/"+escape(str(item_id),quote=True)+"/rentabilidade'>Rentabilidade</a><a href='/anuncios/"+str(int(cid))+"/"+escape(str(item_id),quote=True)+"/conteudo'>Revisar conteúdo</a><a href='/anuncios/"+str(int(cid))+"/"+escape(str(item_id),quote=True)+"/perguntas'>Perguntas</a><a href='#diag-acoes'>Ver prioridades ↓</a></nav></header>"
    out+="<p class='diag-hint'><a href='/anuncios/"+str(cid)+"/"+escape(str(item_id),quote=True)+"/acoes' style='display:inline-block;padding:10px 14px;background:#eef3ff;border:1px solid #cbd9ef;border-radius:9px;text-decoration:none;color:#31598b;font-weight:650'>Histórico automático de alterações</a></p>"
    out+="<section class='diag-summary' aria-label='Resumo de prioridades'>"
    for value,label in ((high,"Prioridade alta"),(review,"Para revisar"),(total,"Verificações")):
        out+="<a href='#diag-acoes' aria-label='"+escape(label,quote=True)+", ver recomendações'><strong>"+str(value)+"</strong><span>"+label+" ↗</span></a>"
    out+="</section>"
    return out

def priorities(results):
    rank={"alta":0,"media":1,"revisar":2,"baixa":3}
    ordered=sorted(results,key=lambda a:rank.get(str(a.get("priority") or "").lower(),4))
    out="<section id='diag-acoes'><h2>Prioridades para otimizar</h2><p class='diag-hint'>Recomendações baseadas nos registros disponíveis; confirme as condições atuais antes de alterar um anúncio.</p>"
    out+="<div class='diag-actions'>"
    for a in ordered:
        level=str(a.get("priority") or "revisar").lower()
        cls=level if level in ("alta","media","revisar","baixa") else "revisar"
        out+="<article class='diag-action "+cls+"'><span class='diag-priority'>Prioridade: "+escape(level)+"</span>"
        out+="<h3>"+escape(str(a.get("title") or "Verificação"))+"</h3>"
        out+="<p><strong>Evidência:</strong> "+escape(str(a.get("evidence") or "Não informada"))+"</p>"
        out+="<p class='diag-next'><strong>Próxima ação:</strong> "+escape(str(a.get("action") or "Revisar"))+"</p></article>"
    if not ordered:
        out+="<div class='diag-actions-empty'>Nenhuma recomendação registrada nesta análise.</div>"
    return out+"</div></section></div>"
