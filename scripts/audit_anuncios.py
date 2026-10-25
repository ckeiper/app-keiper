"""Validate the known-capability ledger and render its reviewable report."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'ANUNCIOS_CONTROLE_ENTREGAS.md'


def report():
    model = json.loads((ROOT / 'anuncios_capacidades_auditadas.json').read_text())
    assert re.fullmatch('[0-9a-f]{40}', model['base_sha']), 'Base de código inválida'
    if not model['lista_original_completa']:
        assert model['contagem_das_90'] is None, 'Não contar as 90 sem a lista original'
    rows = model['capacidades']
    assert len({r['id'] for r in rows}) == len(rows), 'Capacidade duplicada'
    numbers = [r['numero_original'] for r in rows if r['numero_original'] is not None]
    assert len(set(numbers)) == len(numbers), 'Número original duplicado'
    assert all(type(n) is int and 1 <= n <= 90 for n in numbers), 'Número original inválido'
    for row in rows:
        state = row['estado']
        assert state in ('concluida', 'parcial', 'pendente'), row['id']
        assert row['implementado'] if state != 'pendente' else not row['implementado'], row['id']
        assert not row['falta'] if state == 'concluida' else row['falta'], row['id']
        if state != 'pendente':
            assert row['fontes'], row['id']
        for name in row['fontes'] + row['testes']:
            path = (ROOT / name).resolve()
            assert path.is_relative_to(ROOT) and path.is_file(), 'Referência ausente: ' + name
        assert all(type(n) is int and n > 0 for n in row['prs']), row['id']
    counts = Counter(r['estado'] for r in rows)
    text = '# Anúncios 2.0 — controle de capacidades e lacunas\n\n'
    text += 'Auditoria de ' + model['data_auditoria'] + ', sobre a base `' + model['base_sha'] + '` (PR #271).\n\n'
    text += '**A contagem de concluídas entre as 90 continua indeterminada.** A lista literal integral não foi recuperada. Este inventário agrupa capacidades conhecidas e não recria os itens originais nem permite calcular percentual de conclusão.\n\n'
    text += '## Resultado do inventário conhecido\n\n'
    text += '| Capacidades agrupadas | Concluídas no escopo descrito | Parciais | Pendentes |\n|---|---|---|---|\n'
    text += f"| {len(rows)} | {counts['concluida']} | {counts['parcial']} | {counts['pendente']} |\n\n"
    text += 'Esses números são do inventário abaixo, **não são X de 90**. Os grupos podem reunir vários requisitos originais. Somente o item 90 tem sua posição original confirmada pelo texto preservado: ranking de prioridades com diagnóstico e plano de ação. Ele está concluído no escopo de revisão baseado em evidências. Os demais números originais permanecem sem associação.\n\n'
    text += 'Concluída significa fluxo integrado na base auditada, com escopo e limites explícitos; não significa cobertura de todas as contas reais. Parcial significa implementação útil existente e lacuna concreta. Pendente significa que o fluxo específico não foi identificado na base inspecionada; presença de palavras em textos ou de campos genéricos não comprova entrega.\n\n'
    text += '## Evidência comum da base publicada\n\n'
    text += '- Deploy Render `' + model['deploy_base']['id'] + '`, confirmado ativo em 25/10/2026 às 16:52:11 (Brasília).\n'
    text += '- 903 testes aprovados sem skips com PostgreSQL nas versões Python 3.12 e 3.14; workflows de navegador aprovados. Runs: ' + ', '.join(str(n) for n in model['validacao_base']['workflow_runs']) + '.\n'
    text += '- Login público verificado com HTTP 200; ranking protegido com redirecionamento ao login, `no-store` e `DENY`. Isso não valida dados financeiros reais de cada loja.\n\n'
    labels = dict(concluida='Concluída', parcial='Parcial', pendente='Pendente')
    for area in dict.fromkeys(r['area'] for r in rows):
        text += '## ' + area + '\n\n| Capacidade | Estado | Implementação comprovada | Lacuna para encerrar o escopo | Evidências |\n|---|---|---|---|---|\n'
        for row in rows:
            if row['area'] != area:
                continue
            evidence = ['[' + name + '](' + name + ')' for name in row['fontes'] + row['testes']]
            evidence += ['[#' + str(n) + '](https://github.com/ckeiper/app-keiper/pull/' + str(n) + ')' for n in row['prs']]
            name = row['capacidade'] + (' (original nº 90)' if row['numero_original'] == 90 else '')
            fields = [name, labels[row['estado']], row['implementado'] or '—', row['falta'] or '—', '; '.join(evidence) or 'Busca no inventário e nas rotas da base auditada; fluxo não localizado.']
            text += '| ' + ' | '.join(value.replace('|', '\\|').replace('\n', ' ') for value in fields) + ' |\n'
        text += '\n'
    text += '## Critério para continuar\n\n'
    text += '1. Reutilizar o inventário, o código e os testes existentes; não iniciar novamente capacidades concluídas.\n'
    text += '2. Priorizar lacunas parciais dos anúncios antes de criar fontes financeiras, previsões ou inferências sem validação. Toda promoção de estado exige evidência de implementação e validação.\n'
    text += '3. Vincular os números originais somente ao recuperar o texto aprovado. Até lá, manter `contagem_das_90` nula. Não preencher por subtração nem equiparar PRs a requisitos.\n'
    text += '4. Mercado Pago e conciliação bancária permanecem adiados na [issue #201](https://github.com/ckeiper/app-keiper/issues/201), fora deste lote.\n\n'
    text += '## Manutenção\n\n'
    text += 'Fonte estruturada: [anuncios_capacidades_auditadas.json](anuncios_capacidades_auditadas.json). Atualizar estado, implementação, lacuna e evidências juntos. Gerar com `python scripts/audit_anuncios.py`; validar referências e relatório sincronizado com `python scripts/audit_anuncios.py --check`. A validação automática confere a integridade do registro, não decide se um requisito de negócio está concluído.\n'
    return text, len(rows), counts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    text, size, counts = report()
    if args.check:
        assert REPORT.read_text() == text, 'Relatório desatualizado: gere novamente'
    else:
        REPORT.write_text(text)
    print(f"Inventário íntegro: {size} capacidades; {dict(counts)}; contagem das 90 indeterminada.")
