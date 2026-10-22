"""Build a reviewable visual backlog from the complete route inventory."""
from pathlib import Path
from screen_inventory import collect

NAMES={
'login':'Login','mfa_verify':'Verificação em duas etapas','recuperar':'Recuperar senha','redefinir':'Redefinir senha','primeiro_acesso':'Configuração do primeiro acesso','account_security':'Segurança da conta',
'painel':'Minhas lojas / página inicial','painel_analise':'Visão geral consolidada','painel_legado':'Painel legado','central_prioridades':'Central de prioridades global','status':'Status das conexões',
'store_management':'Resumo e gestão da loja','painel_detalhe':'Resumo operacional da loja','prioridades_loja':'Minhas prioridades da loja','anuncios':'Catálogo de anúncios','ranking_anuncios':'Ranking e fila de anúncios','listing_interventions':'Histórico de ações do anúncio','competitor_list':'Monitor de concorrência','competitor_history':'Histórico de um concorrente','desempenho':'Desempenho da loja','vendas':'Vendas da loja','full_choose_store':'Full — seleção de loja','full_report':'Full e vendas da loja','custos':'Custos e margens','demandas':'Demandas da loja','promocoes':'Promoções da loja','promocoes_candidatos':'Anúncios candidatos à promoção','participar_deal':'Análise, confirmação e resultado de participação em promoção','painel_ads':'Publicidade / Product Ads da loja','painel_ads_campanha':'Detalhe de uma campanha Ads','campanhas':'Lista e gestão de campanhas Ads','auditoria_frete':'Auditoria de frete','excluir':'Confirmação de exclusão de loja',
'crm_index':'CRM — lista de leads','crm_edit':'CRM — cadastro / detalhe do lead','crm_import':'CRM — importar transcrição','crm_review':'CRM — revisar importação','crm_settings':'CRM — configuração da integração',
'usuarios':'Gestão de usuários','usuarios_editar':'Editar usuário','usuarios_excluir':'Excluir usuário','diagnostico':'Diagnóstico geral','diagnostico_saude_anuncio':'Diagnóstico de um anúncio','coleta_visitas_copas':'Coleta piloto de visitas Copas','progresso_visitas_todas':'Progresso da coleta de visitas',
}
GROUPS={
'Acesso e segurança':{'login','mfa_verify','recuperar','redefinir','primeiro_acesso','account_security'},
'Painéis globais':{'painel','painel_analise','painel_legado','central_prioridades','status'},
'Loja, anúncios e operação':{'store_management','painel_detalhe','prioridades_loja','anuncios','ranking_anuncios','listing_interventions','competitor_list','competitor_history','desempenho','vendas','full_choose_store','full_report','custos','demandas','promocoes','promocoes_candidatos','participar_deal','painel_ads','painel_ads_campanha','campanhas','auditoria_frete','excluir'},
'CRM':{'crm_index','crm_edit','crm_import','crm_review','crm_settings'},
'Administração e diagnóstico':{'usuarios','usuarios_editar','usuarios_excluir','diagnostico','diagnostico_saude_anuncio','coleta_visitas_copas','progresso_visitas_todas'},
}


def build():
    root=Path(__file__).resolve().parents[1];routes=collect(root);screens=[r for r in routes if r['kind']=='Tela']
    assert len(screens)==45, 'Review additions or removals before updating the visual plan.'
    out=['# Inventário de telas e plano de melhoria visual — Keiper Consultoria','',
         f'Levantamento do código em 22/10/2026: **{len(screens)} rotas de tela e {len(routes)} rotas no total**. Uma rota com parâmetros representa uma família de telas, não uma entrada por loja ou campanha. Abas, modais e estados da mesma página aparecem após a lista. Este documento cobre o código versionado, sem acessar dados de produção.','',
         '## Entrega atual','',
         '- Publicidade é a única lista de campanhas: clique em uma campanha para abrir a análise individual. A rota antiga de Campanhas redireciona à Publicidade.\n- Menu recolhível compartilhado aplicado a todas as páginas que usam pagina_loja, com o contexto e os links da loja atual.','- Publicidade da loja redesenhada: cabeçalho, filtros, indicadores, alertas compactos, tabela e gráfico.','- Minhas lojas e gráfico da campanha Ads já receberam melhorias na entrega anterior.','- As demais linhas abaixo são um backlog; receber o novo menu não significa que o conteúdo de cada tela já foi redesenhado.','',
         '## Todas as telas','']
    number=0
    for group,handlers in GROUPS.items():
        out+=['### '+group,'','| # | Tela | Rota | Próximo passo |','|---|---|---|---|']
        for r in sorted((r for r in screens if r['handler'] in handlers),key=lambda r:(NAMES[r['handler']],r['path'])):
            number+=1;name=NAMES[r['handler']]
            if r['path']=='/crm/novo':name='CRM — novo lead'
            elif r['path']=='/crm/<int:lead_id>':name='CRM — detalhe e edição do lead'
            status='Revisar visual'
            if r['handler']=='painel_ads':status='Redesenhada nesta entrega'
            elif r['handler']=='painel':status='Atualizada na entrega anterior'
            elif r['handler']=='painel_ads_campanha':status='Gráfico atualizado; revisar restante da página'
            elif r['handler']=='painel_legado':status='Decidir manutenção ou descontinuação antes de redesenhar'
            out.append(f"| {number} | {name} | `{r['path']}` | {status} |")
        out.append('')
    assert number==len(screens)
    out+=['## Subtelas e estados dentro dessas páginas','',
          '- Resumo da loja: abas Visão geral, Oportunidades e Análise por anúncio; detalhe de produto em modal.','- Catálogo de anúncios: abas Meus anúncios e Concorrência; detalhes técnicos expansíveis; busca, filtros e paginação.','- Diagnóstico do anúncio: evidências, fatores, linha do tempo, troca de métrica, paginação e histórico de ações.','- Promoções: candidatos, análise de preço e margem, confirmação e resultado de participação.','- Publicidade: período padrão ou personalizado, busca/situação/ordenação de campanhas, paginação, alertas expandidos e recolhidos, detalhamento diário e estado sem dados.','- Campanha Ads: períodos de 7/15/30/60/90 dias, cobertura parcial, histórico de mudanças e comparação de períodos.','- Auditoria de frete: upload, progresso, prévia, importação, histórico, consolidação e comparação com vendas.','- Custos: configuração, edição por anúncio e importação de planilha.','- CRM: filtros por etapa e prazo, cadastro, edição, histórico de contatos, importação, revisão e vínculo ao cadastro existente.','- Segurança: ativação, QR code, confirmação, códigos de recuperação e desativação do segundo fator.','- Todas: loading, sem dados, falha, acesso negado, feedback de formulário, foco de teclado e versão para celular devem entrar na revisão visual.','',
          '## Ordem sugerida — uma tela por vez','',
          '1. Publicidade da loja — entrega atual.','2. Revisar o detalhe individual de cada campanha, acessado pela Publicidade.','3. Aprimorar os controles e as explicações da análise individual de Ads.','4. Resumo e gestão da loja, incluindo as três abas.','5. Catálogo de anúncios e detalhes.','6. Desempenho, diagnóstico do anúncio e ranking.','7. Vendas e Full.','8. Promoções, candidatos e confirmação de participação.','9. Custos e auditoria de frete.','10. Demandas e prioridades.','11. Visão geral consolidada e status.','12. CRM, uma rota de cada vez.','13. Usuários, login, recuperação de senha e segurança.','14. Diagnósticos administrativos e decisão sobre telas legadas.','',
          'Para cada tela: revisar desktop e celular, preservar regras e permissões, testar ações existentes e validar estados vazio/erro. Não alterar automaticamente todas as telas do backlog nesta entrega.','',
          '## Demais rotas — inventário completo','',
          'Estas rotas complementam o sistema, mas não são telas independentes de navegação. Fluxos auxiliares podem renderizar confirmações ou mensagens de erro.','']
    for kind in sorted({r['kind'] for r in routes if r['kind']!='Tela'}):
        out+=['### '+kind,'','| Rota | Métodos | Função |','|---|---|---|']
        out += [f"| `{r['path']}` | {', '.join(r['methods'])} | `{r['handler']}` |" for r in routes if r['kind']==kind]
        out.append('')
    out+=['## Manutenção do inventário','',
          'Gerado por scripts/build_screen_plan.py a partir da inspeção AST de todas as rotas Flask dos módulos Python. scripts/screen_inventory.py também gera visual-qa/routes.json com arquivo, linha e função de origem. Novas rotas exigem revisão da contagem e da classificação; os caminhos de ação, arquivos e fragmentos não foram omitidos.','']
    destination=root/'TELAS_E_PLANO_VISUAL.md';destination.write_text('\n'.join(out),encoding='utf-8');print(f'{len(screens)} telas, {len(routes)} rotas: {destination.name}')


if __name__=='__main__':build()
