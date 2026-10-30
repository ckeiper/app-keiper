"""Conservative cross-reading of listing signals, never causal attribution."""
from decimal import Decimal
from html import escape


def assess(evidence, sales, days=7):
    """Separate traffic and paid-orders/visit declines with verified inputs."""
    if not evidence.get('sales_verified') or not sales:
        return dict(state='incompleto', title='Validar os dados de vendas',
                    detail='Sem cobertura verificada, não há queda confirmada para classificar.',
                    check='Revisar a sincronização e a cobertura dos dois períodos.',
                    facts=[])
    if not evidence.get('declining'):
        return dict(state='sem_queda', title='Sem queda de faturamento confirmada',
                    detail='O faturamento bruto dos itens não diminuiu nos períodos comparados.',
                    check='Acompanhar alterações observadas e a evolução de pedidos e visitas.',
                    facts=[])
    traffic = evidence['traffic']
    efficiency = evidence['conversion']
    if not traffic['complete'] or not efficiency['complete']:
        return dict(state='lacunas', title='Queda confirmada; mecanismo ainda desconhecido',
                    detail='A cobertura de visitas ou a base para pedidos pagos por visita é insuficiente.',
                    check='Completar as leituras de visitas dos '+str(2*days)+' dias e conferir pedidos pagos, antes de sugerir mudanças.',
                    facts=[])
    previous_visits = traffic['previous']['totals']['visitas']
    previous_orders = sales.get('previous_orders')
    if previous_visits is None or previous_visits < 30 or previous_orders is None or previous_orders < 5:
        return dict(state='amostra', title='Queda confirmada; amostra pequena',
                    detail='A base anterior precisa ter pelo menos 30 visitas e 5 pedidos pagos para esta triagem.',
                    check='Verificar Full, preço e conteúdo, mas evitar concluir qual indicador explica a queda.',
                    facts=[])
    t, e = traffic['delta'], efficiency['delta']
    if t is None or e is None:
        return dict(state='lacunas', title='Queda confirmada; comparativo inconclusivo',
                    detail='Uma das taxas não possui base percentual anterior positiva.',
                    check='Conferir períodos completos e denominadores antes de interpretar o movimento.',
                    facts=[])
    traffic_drop = t <= Decimal('-20')
    efficiency_drop = e <= Decimal('-20')
    facts = [('Visitas', t), ('Pedidos pagos por visita', e)]
    if traffic_drop and efficiency_drop:
        return dict(state='dupla', title='Dois sinais simultâneos de queda',
                    detail='As visitas e os pedidos pagos por visita caíram pelo menos 20% entre períodos completos.',
                    check='Investigar exposição e tráfego primeiro; em paralelo revisar preço, Full, frete, prazo e concorrência.',
                    facts=facts)
    if traffic_drop:
        return dict(state='trafego', title='Sinal predominante: redução de visitas',
                    detail='As visitas recuaram pelo menos 20%; a eficiência não atingiu esse mesmo limite.',
                    check='Revisar posicionamento, disponibilidade, catálogo e publicidade vinculada ao anúncio.',
                    facts=facts)
    if efficiency_drop:
        return dict(state='eficiencia', title='Sinal predominante: eficiência das visitas',
                    detail='Pedidos pagos por visita recuaram pelo menos 20%; visitas não atingiram esse limite.',
                    check='Conferir preço final, concorrência, variações, reputação, frete, prazo e Full.',
                    facts=facts)
    return dict(state='outros', title='Queda sem recuo expressivo nos dois indicadores',
                detail='Nem visitas nem pedidos pagos por visita atingiram queda de 20%. Quantidades por pedido e valor dos itens podem influenciar o faturamento.',
                check='Conferir unidades, valor bruto por pedido, mudanças de oferta e o detalhamento matemático abaixo.',
                facts=facts)


def render(result, days=7):
    tone = ' alert' if result['state'] in ('dupla','trafego','eficiencia') else ''
    out = '<section class="cross-reading'+tone+'" aria-label="Leitura cruzada da queda">'
    out += '<span class="cross-label">LEITURA CRUZADA · '+str(days)+' DIAS VS. '+str(days)+' DIAS</span>'
    out += '<h4>'+escape(result['title'])+'</h4>'
    if result['facts']:
        out += '<div class="cross-facts">'
        for label, delta in result['facts']:
            number = ('%+.1f%%' % delta).replace('.', ',')
            out += '<span><b>'+escape(label)+'</b> '+escape(number)+'</span>'
        out += '</div>'
    out += '<p>'+escape(result['detail'])+'</p>'
    out += '<p><b>Próxima verificação:</b> '+escape(result['check'])+'</p>'
    out += '<small>Triagem observacional, não estabelece causa. Pedidos pagos/visitas não é a conversão oficial do Mercado Livre; os limites são regras operacionais, não testes estatísticos.</small></section>'
    return out


CSS = """<style>
.cross-reading{background:#fff;border:1px solid #dce5f1;border-radius:14px;padding:19px;margin:15px 0;box-shadow:0 4px 20px #18335108;color:#243651}
.cross-reading.alert{border-left:4px solid #e3a254}
.cross-reading .cross-label{font-size:10px;font-weight:800;color:#607fb4;letter-spacing:1.1px}
.cross-reading h4{font-size:17px;color:#203a5d;margin:9px 0 11px}
.cross-reading p{font-size:12px;line-height:1.65;margin:9px 0}
.cross-reading small{display:block;font-size:11px;line-height:1.6;color:#6b7e95;margin-top:10px}
.cross-facts{display:flex;flex-wrap:wrap;gap:9px}
.cross-facts span{border:1px solid #e4eaf3;border-radius:8px;background:#f3f7fc;font-size:12px;padding:8px 10px}
.cross-facts b{margin-right:7px;color:#526784}
@media(max-width:600px){.cross-reading{padding:15px}}
</style>"""
