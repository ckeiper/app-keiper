"""Authenticated, idempotent import from the owner's Google Workspace script."""
import datetime as dt
import hashlib
import json
import re
import secrets
import unicodedata

from flask import jsonify, request

ENDPOINT = 'crm_meet_ingest'
TOKEN_KEY = 'meet_ingest_sha256'
MAX_BODY = 520_000
DOC_ID = re.compile(r'[A-Za-z0-9_-]{20,120}')
EMAIL = re.compile(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', re.I)


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                   if not unicodedata.combining(c)).strip()


def parse_meeting(payload, today):
    if not isinstance(payload, dict):
        raise ValueError('invalid_payload')
    doc, title, text = (payload.get(k) for k in ('document_id', 'title', 'text'))
    if not all(isinstance(x, str) and '\x00' not in x for x in (doc, title, text)):
        raise ValueError('invalid_fields')
    if not DOC_ID.fullmatch(doc) or len(title) > 300 or not 50 <= len(text) <= 120_000:
        raise ValueError('invalid_fields')
    match = re.fullmatch(r'reuniao\s+(.+?)\s+-\s+(\d{4}/\d{2}/\d{2}).*anotacoes do gemini', fold(title))
    if not match:
        raise ValueError('not_lead_meeting')
    day = dt.date.fromisoformat(match[2].replace('/', '-'))
    if day > today:
        raise ValueError('future_meeting')
    # Only invitee metadata, not arbitrary addresses said during the call.
    header = text.lstrip('\ufeff').splitlines()[:10]
    emails = {email.lower() for line in header if re.match(r'^(convidados?|guests?)\b', fold(line))
              for email in EMAIL.findall(line)}
    if not emails:
        raise ValueError('missing_invitees')
    first_name = re.search(r'\w+', match[1])
    if not first_name:
        raise ValueError('missing_name')
    return doc, day, first_name[0], sorted(emails), text


def register_meet_ingest(app, bank, query, execute, history, today):
    @app.post('/crm/integracao/meet', endpoint=ENDPOINT)
    def ingest():
        # This route never accepts cookie-based authentication.
        scheme, _, token = request.headers.get('Authorization', '').partition(' ')
        if scheme.lower() != 'bearer' or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            return jsonify(status='unauthorized'), 401
        digest = hashlib.sha256(token.encode()).hexdigest()
        if not request.is_json:
            return jsonify(status='json_required'), 415
        if request.content_length and request.content_length > MAX_BODY:
            return jsonify(status='payload_too_large'), 413
        with bank() as conn:
            key = query(conn, 'SELECT valor FROM crm_config WHERE chave=%s', (TOKEN_KEY,))
            if not key or not secrets.compare_digest(key[0]['valor'], digest):
                return jsonify(status='unauthorized'), 401
            raw = request.stream.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                return jsonify(status='payload_too_large'), 413
            try:
                doc, day, first, emails, transcript = parse_meeting(json.loads(raw), today())
            except (ValueError, UnicodeError):
                return jsonify(status='invalid_meeting'), 422
            execute(conn, 'SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', ('crm-meet:' + doc,))
            if query(conn, 'SELECT lead_id FROM crm_meet_imports WHERE document_id=%s', (doc,)):
                return jsonify(status='already_imported')
            # Include previously imported meetings whose document URL was stored manually.
            known = query(conn, """SELECT DISTINCT l.id FROM crm_leads l
                WHERE strpos(COALESCE(l.dados->>'observacoes',''),%s)>0
                OR EXISTS (SELECT 1 FROM crm_historico h WHERE h.lead_id=l.id AND strpos(h.texto,%s)>0)""", (doc,doc))
            if known:
                return jsonify(status='already_imported')
            matches = query(conn, """SELECT id,nome,etapa,dados FROM crm_leads
                WHERE lower(trim(dados->>'email'))=ANY(%s) ORDER BY id FOR UPDATE""", (emails,))
            matches = [l for l in matches if re.match(r'^\w+', fold(l['nome']))
                       and re.match(r'^\w+', fold(l['nome']))[0] == first]
            if len(matches) != 1:
                return jsonify(status='lead_not_identified'), 409
            lead = matches[0]
            if lead['etapa'] in ('Perdido', 'Cliente fechado'):
                return jsonify(status='lead_closed')
            if query(conn, """SELECT id FROM crm_historico WHERE lead_id=%s
                       AND data_reuniao=%s AND tipo='Reunião importada' LIMIT 1""", (lead['id'],day)):
                return jsonify(status='meeting_already_recorded')
            source = 'https://docs.google.com/document/d/' + doc + '/edit'
            history(conn, lead['id'], 'Reunião importada',
                    'Google Meet · importação automática\nFonte: ' + source, transcript, day)
            execute(conn, 'INSERT INTO crm_meet_imports(document_id,lead_id) VALUES(%s,%s)', (doc,lead['id']))
            data = dict(lead['dados'])
            if (data.get('data_reuniao') or '') <= day.isoformat():
                data['data_reuniao'] = day.isoformat()
            stage = lead['etapa']
            if stage in ('Novo', 'Reunião agendada'):
                stage = 'Reunião realizada'
            execute(conn, """UPDATE crm_leads SET etapa=%s,dados=%s::jsonb,
                ultima_interacao=GREATEST(ultima_interacao,%s::date::timestamp AT TIME ZONE 'America/Sao_Paulo'),
                atualizado_em=NOW(),versao=versao+1 WHERE id=%s""",
                    (stage,json.dumps(data,ensure_ascii=False),day,lead['id']))
            return jsonify(status='imported')
