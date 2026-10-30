"""Audit observed campaign configuration changes; no fabricated historical events."""
from decimal import Decimal, InvalidOperation
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo

CREATE_SQL = """CREATE TABLE IF NOT EXISTS ads_campanha_alteracoes (
    id BIGSERIAL PRIMARY KEY,
    conexao_id INTEGER NOT NULL,
    campanha_id TEXT NOT NULL,
    campo TEXT NOT NULL CHECK (campo IN ('orcamento','roas_objetivo')),
    valor_anterior REAL NOT NULL,
    valor_novo REAL NOT NULL,
    observado_em BIGINT NOT NULL,
    origem TEXT NOT NULL CHECK (origem IN ('api','painel'))
)"""
INDEX_SQL = """CREATE INDEX IF NOT EXISTS idx_ads_campanha_alteracoes_loja
    ON ads_campanha_alteracoes(conexao_id,campanha_id,observado_em DESC,id DESC)"""

def number(value):
    if value is None or isinstance(value,bool):
        return None
    try:
        n=Decimal(str(value))
        return n if n.is_finite() and n >= 0 else None
    except (ValueError, TypeError, InvalidOperation):
        return None

def differences(previous, observed):
    """Only compare known, validated values; first snapshot is not a change."""
    if not previous:
        return []
    result=[]
    for field in ("orcamento","roas_objetivo"):
        old=number(previous.get(field))
        new=number(observed.get(field))
        if old is not None and new is not None and abs(old-new)>Decimal("0.0001"):
            result.append((field,float(old),float(new)))
    return result

def record_changes(conn, executar, cid, camp_id, previous, observed, timestamp, source):
    if source not in ("api","painel"):
        raise ValueError("Invalid audit source")
    for field,old,new in differences(previous,observed):
        executar(conn, """INSERT INTO ads_campanha_alteracoes
            (conexao_id,campanha_id,campo,valor_anterior,valor_novo,observado_em,origem)
            VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (cid,str(camp_id),field,old,new,int(timestamp),source))

def display_history(changes):
    out="<section class='kc-section kc-history'><h3>Histórico de alterações</h3>"
    out+="<p class='kc-sub'>Mudanças de orçamento e meta de ROAS observadas desde a ativação deste registro. A data é quando o sistema detectou a alteração, não necessariamente quando ela foi feita no Mercado Livre.</p>"
    if not changes:
        return out+"<div class='kc-stale'>Ainda não foi detectada nenhuma alteração desde o início do monitoramento. Não existe histórico retroativo.</div></section>"
    out+="<div class='kc-change-list'>"
    for row in changes:
        field=str(row.get("campo"))
        label="Orçamento diário" if field=="orcamento" else "Meta de ROAS"
        old=number(row.get("valor_anterior"))
        new=number(row.get("valor_novo"))
        if old is None or new is None:
            continue
        if field=="orcamento":
            from ads_campaign_detail import money
            old_label,new_label=money(float(old)),money(float(new))
        else:
            old_label,new_label=("%.2fx"%float(old)),("%.2fx"%float(new))
        when=datetime.fromtimestamp(int(row["observado_em"]),ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
        source="Sincronização ML" if row.get("origem")=="api" else "Ajuste no painel Keiper (local)"
        out+=("<article class='kc-change'><span class='kc-change-type'>"
              +escape(label)+"</span><strong>"+escape(old_label)+" → "+escape(new_label)
              +"</strong><small>"+escape(when)+" · "+escape(source)+"</small></article>")
    return out+"</div><p class='kc-sub'>Esses eventos mostram mudanças observadas, não comprovam ganho de vendas. A análise de efeito exige janelas completas de dados antes e depois.</p></section>"
