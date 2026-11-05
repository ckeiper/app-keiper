"""Read explicit Gemini note structure without guessing facts from dialogue."""
import datetime as dt
import re


def extract_notes(text):
    lines = text.lstrip('\ufeff').replace('\r', '').splitlines()
    # Only read the notes, not spoken instructions or speaker-labelled dialogue.
    end = next((i for i, line in enumerate(lines)
                if re.search(r'^Reunião .+ - Transcrição$|^\d\d:\d\d:\d\d$', line.strip())), len(lines))
    notes = '\n'.join(lines[:end])
    title = re.search(r'(?im)^Reunião[ \t]+([^\n:]+)$', notes)
    if not title:
        return {}, ''
    data = {'nome': title.group(1).strip()}
    invited = re.search(r'(?im)^convidad[oa]s?\s+(.+)$', notes)
    if invited:
        emails = re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', invited.group(1))
        emails = [e for e in emails if not e.lower().endswith('@keiperconsultoria.com.br')]
        if len(set(emails)) == 1:
            data['email'] = emails[0]
    months = {'jan':1,'fev':2,'mar':3,'abr':4,'mai':5,'jun':6,
              'jul':7,'ago':8,'set':9,'out':10,'nov':11,'dez':12}
    date = re.search(r'(?im)^(\w{3})\.?\s+(\d{1,2}),\s+(\d{4})$', notes)
    if date and date[1].lower() in months:
        try:
            data['data_reuniao'] = dt.date(int(date[3]), months[date[1].lower()], int(date[2])).isoformat()
        except ValueError:
            pass
    sections = re.split(r'(?im)^(Resumo|Decisões|Próximas etapas|Detalhes)\s*$', notes)
    blocks = dict(zip(sections[1::2], sections[2::2]))
    summary = blocks.get('Resumo', '').strip()
    actions = blocks.get('Próximas etapas', '').strip()
    if actions:
        data['proxima_acao'] = actions[:5000]
    # Retain the original wording and heading: this is extraction, not interpretation.
    patterns = {
        'dificuldades': r'problema|dificuldade|desafio|sazonalidade',
        'objetivos': r'objetivo|meta|expansão|novos produtos',
        'estrutura': r'equipe|logística|erp|estrutura|operação',
        'interesse': r'interesse|necessidade',
        'objecoes': r'objeç|impedimento|aprovação|decisão|contrato anterior',
        'valor_proposto': r'condições da consultoria|proposta comercial|valor da consultoria',
    }
    detail = blocks.get('Detalhes', '')
    for paragraph in re.split(r'\n\s*\n|_{3,}', summary + '\n\n' + detail):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        heading = paragraph.split(':', 1)[0].split('\n', 1)[0]
        for field, pattern in patterns.items():
            if re.search(pattern, heading, re.I):
                limit = 300 if field == 'valor_proposto' else 5000
                # Do not truncate a financial statement and accidentally omit its qualifier.
                if field == 'valor_proposto' and len(paragraph) > limit:
                    continue
                data[field] = (data.get(field, '') + '\n\n' + paragraph).strip()[:limit]
    if summary:
        data['observacoes'] = 'Resumo original do Gemini (sem interpretação por IA):\n' + summary[:4900]
    return data, summary[:8000]
