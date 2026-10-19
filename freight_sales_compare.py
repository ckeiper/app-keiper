"""Compare report charges to the same freight calculation used by Vendas.

Identifiers stay in memory. Only aggregate comparison results leave this module.
Multiple movements per order are left unresolved rather than added or deduplicated.
"""
import io
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from freight_reconciliation import schema_columns, normalize, _amount
from freight_comparison import compare_freight, format_brl, money


def compare_sales_rows(rows, columns, references, payment_links, shipment_links):
    links = defaultdict(set)
    for link in payment_links:
        links[('operation', str(link['operation_id']))].add(str(link['pedido_id']))
    for link in shipment_links:
        links[('shipment', str(link['envio_id']))].add(str(link['pedido_id']))
    grouped = defaultdict(list)
    result = dict(candidate_rows=0, unmatched_rows=0, ambiguous_rows=0,
                  ambiguous_orders=0, unavailable_orders=0, invalid_orders=0,
                  compared_orders=0, real_orders=0, estimated_orders=0,
                  above=0, below=0, within=0)
    paid = expected = excess = Decimal('0.00')
    for row in rows:
        if normalize(row[columns['operation_type']]) not in ('venda', 'envio'):
            continue
        result['candidate_rows'] += 1
        operation = row[columns['operation_id']]
        shipment = row[columns['shipment_id']]
        candidates = (links.get(('operation', str(operation)), set())
                      | links.get(('shipment', str(shipment)), set())
                      | ({str(operation)} if str(operation) in references else set()))
        if not candidates:
            result['unmatched_rows'] += 1
            continue
        if len(candidates) != 1:
            result['ambiguous_rows'] += 1
            # Poison every candidate: a different singleton row cannot make this safe.
            for order_id in candidates:
                grouped[order_id].extend([None, None])
            continue
        grouped[next(iter(candidates))].append(row)
    for order_id, movements in grouped.items():
        if len(movements) != 1:
            result['ambiguous_orders'] += 1
            continue
        reference = references.get(order_id)
        if (not reference or not reference.get('frete_verificavel') or
                reference.get('frete_fonte') not in ('real', 'estimado')):
            result['unavailable_orders'] += 1
            continue
        row = movements[0]
        try:
            gross, discount, charged = [_amount(row[columns[key]]) for key in
                ('gross_shipping','shipping_discount','seller_shipping')]
            baseline = money(reference['frete'])
            if discount > gross or abs(gross - discount - charged) > Decimal('.01'):
                raise ValueError
        except (ValueError, InvalidOperation, KeyError):
            result['invalid_orders'] += 1
            continue
        comparison = compare_freight(charged, baseline)
        status = {'acima':'above','abaixo':'below','dentro_tolerancia':'within'}[comparison['status']]
        result[status] += 1
        result['compared_orders'] += 1
        result['real_orders' if reference['frete_fonte'] == 'real' else 'estimated_orders'] += 1
        paid += charged
        expected += baseline
        if comparison['status'] == 'acima':
            excess += charged - baseline
    result.update(charged_total=str(paid),sales_total=str(expected),above_total=str(excess))
    return result


def audit_against_sales(cid, filename, payload, summary, banco, query, calculate):
    if not summary.get('period_start'):
        return compare_sales_rows([],{}, {},[],[])
    _, sales = calculate(cid, inicio=summary['period_start'])
    refs = {str(row['pedido_id']): row for row in sales}
    payments, shipments = [], []
    if refs:
        with banco() as conn:
            payments = query(conn, '''SELECT pedido_id,payment->>'id' AS operation_id
                FROM pedidos CROSS JOIN LATERAL jsonb_array_elements(
                    CASE WHEN jsonb_typeof(pagamentos_json)='array' THEN pagamentos_json
                    ELSE '[]'::jsonb END) AS payment
                WHERE conexao_id=%s AND pedido_id=ANY(%s) AND payment->>'id' IS NOT NULL''',
                (cid,list(refs)))
            shipments = query(conn, '''SELECT pedido_id,envio_id FROM envios
                WHERE conexao_id=%s AND pedido_id=ANY(%s)''',(cid,list(refs)))
    per_order = defaultdict(set)
    for link in shipments:
        per_order[str(link['pedido_id'])].add(str(link['envio_id']))
    for order_id, identifiers in per_order.items():
        if len(identifiers) > 1 and order_id in refs:
            refs[order_id]['frete_verificavel'] = False
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(payload),read_only=True,data_only=False,keep_links=False)
    try:
        ws = wb.active
        columns = schema_columns(next(ws.iter_rows(min_row=3,max_row=3,max_col=45,values_only=True)))
        return compare_sales_rows(ws.iter_rows(min_row=4,max_col=45,values_only=True),
                                  columns,refs,payments,shipments)
    finally:
        wb.close()


def render_sales_comparison(result):
    labels = [('compared_orders','Pedidos comparados'),('real_orders','Referência real em Vendas'),
              ('estimated_orders','Referência estimada em Vendas'),('above','Planilha acima de Vendas'),
              ('below','Planilha abaixo de Vendas'),('within','Dentro da tolerância'),
              ('unmatched_rows','Lançamentos sem vínculo na base de Vendas'),
              ('ambiguous_orders','Pedidos com múltiplos lançamentos ou vínculo ambíguo'),
              ('unavailable_orders','Pedidos sem frete verificável em Vendas'),
              ('invalid_orders','Pedidos com valores de frete inválidos')]
    return ('<section class="card"><h3>Planilha × frete da página de Vendas</h3><ul>'
            + ''.join('<li>'+label+': '+str(int(result[key]))+'</li>' for key,label in labels)
            + '</ul><p>Frete da planilha nos pedidos comparados: '+format_brl(result['charged_total'])
            + ' · Frete de Vendas nesses mesmos pedidos: '+format_brl(result['sales_total'])
            + ' · Diferenças positivas: '+format_brl(result['above_total'])
            + '</p><p>Vínculo exato por pedido, pagamento ou envio, dentro desta loja. '
            'Somente um lançamento por pedido é comparado; múltiplos movimentos exigem revisão. '
            'Vendas usa custo real do envio quando disponível; caso contrário, estimativa por preço/peso. '
            'Estimativas sem todos os pesos ficam indisponíveis. Tolerância R$ 0,01. '
            'Diferenças entre as fontes não comprovam cobrança indevida.</p></section>')
