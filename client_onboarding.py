"""Client financial onboarding: explicit tax confirmation and real cost coverage.

Never infer completion from a default tax value or a zero-row import.
"""
from html import escape
from math import isfinite


def validate_tax(raw):
    try:
        value=float(str(raw).strip().replace(',', '.'))
    except (ValueError,TypeError):
        raise ValueError('Informe a alíquota de imposto.')
    if not isfinite(value) or value<0 or value>100:
        raise ValueError('O imposto deve estar entre 0% e 100%.')
    return round(value,4)


def status(record, total_active, active_with_cost):
    tax=bool(record and record.get('imposto_confirmado_em'))
    uploaded=bool(record and record.get('custos_importados_em'))
    covered=total_active>0 and active_with_cost==total_active
    return {'tax':tax,'uploaded':uploaded,'covered':covered,
            'done':tax and uploaded and covered,
            'total':total_active,'with_cost':active_with_cost}


def onboarding_page(cid, shop, progress, current_tax, message=''):
    cid=int(cid)
    name=escape(str(shop))
    error='<div class="on-error" role="alert">'+escape(message)+'</div>' if message else ''
    step1='Concluído' if progress['tax'] else 'Pendente'
    step2='Concluído' if progress['uploaded'] else 'Pendente'
    step3='Concluído' if progress['covered'] else 'Pendente'
    return """<style>
    .on-wrap{max-width:820px;margin:26px auto 60px;padding:0 16px;color:#213754}
    .on-hero{background:linear-gradient(125deg,#0d203a,#245181);padding:26px;color:#fff;border-radius:18px}
    .on-hero small{font-size:11px;letter-spacing:1.3px;color:#9dd6ff;font-weight:800}
    .on-hero h2{color:#fff;font-size:26px;margin:9px 0}.on-hero p{font-size:13px;line-height:1.7;color:#dbe8f7}
    .on-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-top:16px}
    .on-card{padding:20px;background:#fff;border:1px solid #dce6f1;border-radius:14px}
    .on-card h3{font-size:17px;margin-bottom:8px}.on-card p{font-size:12px;line-height:1.6;color:#667994}
    .on-status{font-size:11px;font-weight:800;color:#365f96;margin-bottom:8px;display:block}
    .on-card input{max-width:180px;margin:10px 0;display:block;padding:10px;border:1px solid #bacce2;border-radius:8px}
    .on-card button{background:#215b9c;color:#fff;padding:11px 15px;border:0;border-radius:9px;font-weight:700;cursor:pointer}
    .on-card a{color:#225a99;font-weight:700}.on-error{margin:14px 0;padding:12px;border:1px solid #e8acac;background:#fff0f0;color:#8d3434;border-radius:10px}
    .on-foot{font-size:12px;line-height:1.7;color:#677c96;margin-top:16px}
    </style><main class="on-wrap"><header class="on-hero"><small>KEIPER · CONFIGURAÇÃO INICIAL</small>
    <h2>Prepare sua loja para analisar promoções</h2><p>"""+name+""" · Antes de liberar o painel, confirme o imposto e importe os custos de seus produtos.
    Os cálculos dependem desses dados. Você só precisa concluir este processo uma vez.</p></header>"""+error+"""
    <div class="on-grid"><section class="on-card"><span class="on-status">1 · Imposto — """+step1+"""</span>
    <h3>Confirme a alíquota</h3><p>Informe a alíquota efetiva de imposto sobre as vendas.
    Zero é permitido somente quando realmente aplicável. Consulte seu contador em caso de dúvida.</p>
    <form method="post" action="/primeiro-acesso/imposto"><label for="on-tax">Imposto sobre vendas (%)</label>
    <input id="on-tax" type="number" name="aliquota" min="0" max="100" step="0.01" required value=\'"""+escape(str(current_tax),quote=True)+"""\'>
    <button type="submit">Confirmar imposto</button></form></section>
    <section class="on-card"><span class="on-status">2 · Planilha de custos — """+step2+"""</span>
    <h3>Importe seus custos</h3><p>Use a planilha modelo com os SKUs da sua loja e o custo de aquisição por produto.
    Só arquivos .xlsx com custos válidos são aceitos.</p>
    <p><a href="/modelo_custos/"""+str(cid)+"""">Baixar planilha modelo</a></p>
    <form method="post" action="/upload_custos/"""+str(cid)+""""
       enctype="multipart/form-data"><input type="file" name="arquivo" accept=".xlsx" required>
       <button type="submit">Enviar planilha</button></form></section>
    <section class="on-card"><span class="on-status">3 · Cobertura de custos — """+step3+"""</span>
    <h3>Produtos com custo</h3><p>"""+str(progress['with_cost'])+""" de """+str(progress['total'])+""" anúncios ativos possuem custo cadastrado.
    Para liberar a Central, todos os anúncios ativos precisam estar cobertos.</p>
    <p>Se surgirem novos anúncios depois, o sistema sinalizará os custos ausentes sem apagar sua configuração.</p></section></div>
    <p class="on-foot">A análise de promoções usa custos, impostos e comissões informadas. Frete, tarifas fixas e outras despesas podem afetar a margem final; nenhuma participação é enviada ao Mercado Livre automaticamente.</p>
    </main>"""


def parse_cost(value):
    try:
        amount=float(str(value).replace('R$','').replace(' ','').replace(',','.'))
    except (TypeError,ValueError):
        return None
    if not isfinite(amount) or amount<0 or amount>1_000_000_000:
        return None
    return amount
