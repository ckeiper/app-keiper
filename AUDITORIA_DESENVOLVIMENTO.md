# Dashboard Keiper — auditoria e execução

Auditoria em 24/10/2026. Base: `main` em `09f056dccc63334778ba79621dc6267d3e65ad3d`.
Render confirmado nessa revisão: serviço `app-keiper`, commit base `live`, deploy automático por commit na `main`.

## Escopo e critério de conclusão

A lista literal numerada das 90 melhorias não está versionada no repositório e não foi recuperada pela busca de contexto. Não foi recriada a partir de suposições. Consequentemente, **não há contagem verificável de concluídas entre as 90**. A matriz abaixo audita capacidades concretas e limitações, sem equivaler cada arquivo ou PR a uma melhoria aprovada.

“Implementado” significa código integrado na base auditada e cobertura automatizada identificada. “Parcial” significa que existe implementação, mas falta uma fonte, integração ou parte do fluxo. Não significa validação de todas as contas e dados reais em produção.

## Matriz do código existente

| Área | Implementado na base | Parcial ou pendente | Evidências principais |
|---|---|---|---|
| Navegação e visual | Menu lateral, submenus, navegação mobile, página inicial azul-marinho, cards e setas de tendência | Uniformização de todas as telas legadas | `home_sidebar.py`, `store_sidebar.py`, `navigation_shell.py`, `home_theme.py`, `test_home_sidebar.py`, `test_visual_theme.py`; PRs #189, #209, #232, #233 |
| Catálogo e diagnóstico | Catálogo paginado, estado do anúncio, fotos, vídeos, peso e promoções; diagnóstico individual | Indicadores dependem da cobertura e qualidade dos dados coletados | `listing_catalog.py`, `listing_health.py`, `listing_details.py`, `test_listing_catalog.py`, `test_listing_details.py` |
| Vendas e desempenho | Pedidos pagos/aprovados, cobertura diária, ranking, períodos comparáveis e investigação de quedas | Dados faltantes continuam indisponíveis; sem inferir conversão de contadores históricos | `sales_metrics.py`, `listing_sales.py`, `listing_ranking.py`, `investigation_evidence.py`, `sales_drivers.py`, testes correspondentes |
| Estoque e Full | Observações de Full na linha do tempo e sinais de estoque recente no ranking | Margem histórica não é inferida de custo atual; cobertura de estoque não equivale a previsão garantida | `full_monitor.py`, `listing_full_sales_chart.py`, `listing_priority_sources.py`, `test_full.py`, `test_listing_priority_evidence.py`; #234 |
| Concorrência | Cadastro por loja, observações de preço final/Full e histórico de ofertas | Histórico limitado ao que foi observado; não reconstitui períodos anteriores à coleta | `competitor_monitor.py`, `competitor_routes.py`, `offer_history.py`, `test_competitors.py`, `test_offer_history.py` |
| Otimização e prioridades | Fila por perda verificada, contexto de alterações, evidências, ações recomendadas | Recuperação de margem e priorização financeira dependem de margem histórica documentada | `listing_priority_queue.py`, `listing_priority_evidence.py`, `investigation_triage.py`, testes correspondentes |
| Histórico e ações | Histórico automático, observações manuais, comparação antes/depois, acompanhamento de recuperação | Associação temporal não comprova causalidade | `automatic_history.py`, `intervention_routes.py`, `intervention_followup.py`, testes correspondentes; #173, #175, #190, #191 |
| Ads | Campanhas individuais, vendas atribuídas oficiais, TACOS com ressalvas, orçamento e consumo, comparação semanal, histórico de alterações | Atribuição de Ads por campanha não é custo financeiro verificado de cada anúncio; não fazer rateio arbitrário | `ads_campaign_detail.py`, `ads_official_metrics.py`, `ads_coverage.py`, `ads_weekly_comparison.py`, testes correspondentes; #212–#219 |
| Rentabilidade por anúncio | Onboarding de imposto/custos e estimativa promocional existem | #235 tinha apenas calculadora isolada. Faltava tela, fonte histórica e rastreabilidade dos custos. Coleta automática de todos os componentes continua pendente | `client_onboarding.py`, `listing_profitability.py`, `test_listing_profitability.py` |
| Conciliação de vendas/frete | Importação, prévia, resumo por dia/loja, histórico e comparação com vendas | Conciliação bancária completa com extrato, repasses e ajustes é escopo distinto, pendente na issue #201 | `freight_import.py`, `freight_reconciliation.py`, `freight_store.py`, `freight_sales_compare.py`, `AUDITORIA_FRETE.md`, testes correspondentes |
| CRM | Leads, etapas, contatos, follow-up e importação/revisão de transcrição; card na página inicial | Ingestão periódica a partir do Gmail não está implementada em `crm.py`; não declarar automação de e-mail concluída com base na importação manual | `crm.py`, `crm_home.py`, `test_crm.py`; #186 |
| KEVIA | Regras diárias, evidências, central, histórico, revisão manual e controle de orçamento opcional de API | Parte da interface ainda se chama KYRA; #228 está aberto. API paga depende de configuração explícita; nenhum treinamento personalizado foi presumido | `keiper_ai.py`, `keiper_ai_store.py`, `keiper_ai_budget.py`, `kyra_*.py`, `test_keiper_ai*.py`, `IA_KEIPER.md` |
| Segurança e desempenho | Sessões revogáveis, CSRF/origem, permissões por loja, MFA opcional, suporte à criptografia de tokens, locks e sincronização incremental, caches/índices | Presença de código não comprova ativação de segredos/MFA em produção; nenhuma configuração secreta foi lida nesta auditoria | `web_security.py`, `session_security.py`, `account_mfa.py`, `ml_token_crypto.py`, `overview_read.py`, `sync_runner.py`, testes correspondentes |

## PRs abertos e reaproveitamento

- #235: continuar neste PR; transformar a calculadora em fluxo utilizável com fontes explícitas e sem lucro presumido.
- #228: identidade pública KEVIA; aproveitar o PR existente após testes na base atual. Identificadores internos/URLs/tabelas permanecem compatíveis.
- #205: histórico de participação em promoções; revisar o diff contra a base atual antes de integrar.
- PRs antigos #179, #151, #137, #40, #31, #30, #20, #19, #18, #17, #16, #15 e #13 aparecem abertos. Várias capacidades correspondentes já existem na `main`. Não mesclar branches antigas em bloco nem fechar sem comparar o conteúdo remanescente.

## Entrega no #235

- Página administrativa de rentabilidade acessível pelo diagnóstico do anúncio.
- Período encerrado, limitado a 90 dias dentro dos últimos 366; padrão: última semana encerrada.
- Receita de referência é **valor bruto dos itens**, obtido das vendas verificadas existentes; nunca informado manualmente ou substituído por faturamento de Ads.
- Registro manual de totais do período: produtos, tarifas, frete do vendedor, impostos, publicidade exclusiva do anúncio e descontos/devoluções/ajustes adicionais não refletidos no preço. Cada componente exige referência documental, inclusive zero.
- A aplicação não confere automaticamente o documento citado. Resultado é **contribuição documentada pelo administrador**, não lucro líquido, valor bancário ou conclusão da IA.
- Sem preencher custo histórico com custo atual, sem alíquota padrão e sem ratear gasto da conta. Automação dessas fontes permanece pendente.
- Tabela nova independente, migração idempotente, versões acrescentadas sem sobrescrever anteriores, chave de reenvio e isolamento por loja/anúncio/período. A remoção explícita futura de uma conexão não apaga o histórico financeiro.
- Alteração na base de vendas invalida o cálculo até revisão dos custos; versões antigas permanecem rastreáveis.
- Nenhuma alteração de preço, campanha, pedido, importação ou saldo em produção.

## Próximas etapas verificáveis

1. Finalizar #235 com suíte completa, integração PostgreSQL e QA visual desktop/mobile; integrar apenas com CI aprovado e confirmar commit `live` no Render.
2. Aproveitar #228 para concluir o nome público KEVIA e #205 para o histórico de promoções, após validar seus diffs contra a `main` atual.
3. Recuperar o documento integral dos 90 requisitos para ligar cada requisito a código/teste/deploy. Isso bloqueia somente a contagem exata e o encerramento da lista, não os trabalhos conhecidos.
4. Automatizar fontes financeiras por anúncio/período somente quando houver mapeamento comprovado; conciliação bancária da issue #201 exige especificar o extrato e o vínculo com repasses.

## Validação inicial

- Base #235 antes desta implementação: 649 testes locais, sucesso, 90 integrações ignoradas sem PostgreSQL isolado.
- Após integração inicial da rentabilidade: 663 testes locais, sucesso, 91 integrações ignoradas sem PostgreSQL isolado.
- CI existente executa PostgreSQL 16 isolado. Resultados finais de CI e deploy devem ser conferidos no PR/Render; não inferidos destes resultados locais.

## Registro de execução — 24/10/2026

- #235 integrado em `f79dcf7`. CI: **664 testes aprovados sem skips**, PostgreSQL 16, configuração Gunicorn e dois workflows de navegador aprovados. Capturas desktop/mobile revisadas; corrigidos contraste e datas. Deploy `dep-dbeameajnfac73djmjeg` confirmado `live`. Verificação HTTP: login 200; nova rota sem sessão 302 para login; `DENY` e `no-store` presentes. Nenhum erro de aplicação retornado pela consulta de logs do intervalo da publicação. Não foi criada nem alterada informação financeira real para testar.
- #228 atualizado sobre #235, com teste da identidade renderizada, três workflows aprovados e integração em `335930c`. Mantém histórico e URLs anteriores.
- #205 recuperado e atualizado sobre #228: histórico das últimas 100 solicitações de participação, estados e atalho de reconciliação sem reenviar adesões. Acrescentados testes para autorização/escopo SQL, XSS, URL encoding, datas brasileiras, números ausentes/não finitos e limitação do resumo à janela exibida. Estimativa de MC identificada como histórica e incompleta para lucro líquido. Nenhuma chamada ao marketplace no carregamento do histórico. Publicação condicionada ao CI desta revisão.

Permanecem pendentes a lista literal dos 90 requisitos, a coleta automática completa de custos por anúncio/período, a conciliação bancária integral da issue #201 e a ingestão periódica de transcrições via Gmail. A importação manual de relatórios/transcrições já existente não foi renomeada como automação bancária ou de e-mail.

### Falha real de deploy diagnosticada antes de liberar o lote seguinte

O deploy `dep-dbeao86q1p3s73e1recg` de #228 falhou em `init_competitor_schema`, com `DeadlockDetected` durante `ALTER TABLE competitor_targets ADD COLUMN IF NOT EXISTS own_item_id`. A versão de #235 continuou `live`. Não foi atribuído esse erro aos textos da KEVIA.

Correção incluída na revisão de #205: consultar o catálogo do PostgreSQL antes de executar ADD COLUMN já existente, evitando lock exclusivo sem alteração real; remover seis blocos que ocultavam exceções de ALTER e deixavam a transação abortada; repetir a transação completa de inicialização somente para SQLSTATE transitório (deadlock, lock indisponível ou falha de serialização), com quatro tentativas e espera limitada. Falhas permanentes continuam impedindo uma inicialização incompleta. Nenhum processo de produção foi encerrado e nenhuma coleta/dado foi apagado.

Regressão PostgreSQL isolada: manter uma leitura concorrente, provocar lock timeout após INSERT, liberar o bloqueio e verificar que a transação foi revertida e repetida inteira, sem perder a linha original nem duplicar a inserção. Verificar também que coluna já existente não solicita lock exclusivo. Suíte local desta revisão: 674 testes, sucesso, 92 integrações reservadas ao CI.

Os logs do Render também mostraram Python 3.14 em produção, enquanto o CI cobria apenas 3.12. O workflow de testes passa a validar ambas as versões, cada uma com PostgreSQL isolado, antes do merge deste lote.

## Continuação — comparação histórica de rentabilidade

Lote sobre `ac991cd`: evolução da contribuição e margem por anúncio, composição aritmética da diferença, participação dos componentes e pontos de conferência com fontes. Leitura das duas janelas em lote, snapshot consistente e sem escrita em GET. Sem dados completos nos dois períodos, a comparação é indisponível; custo atual não substitui histórico. Especificação e limites em `RENTABILIDADE_HISTORICA.md`. Integração e publicação condicionadas ao CI desta revisão.

## Continuação — evidências financeiras nas prioridades

#236 integrado em `36df005`, com 688 testes aprovados em Python 3.12/3.14 e QA de navegador. Deploy `dep-dbeb7115efls73ar0go0` confirmado `live`.

Próximo lote liga custos documentados aos cards existentes de anúncios com perda bruta. Para o administrador, acrescenta contribuição atual negativa e comparação de margem, inclusive quando negativa, sem mudar a ordem bruta ou os critérios de acesso dos clientes. Uma leitura financeira adicional por loja, com reaproveitamento das vendas e fingerprint compartilhado; sem chamada ao marketplace e sem nova migração. Especificação em `PRIORIDADES_FINANCEIRAS.md`. Publicação condicionada aos testes desta revisão.


## Continuação — KEVIA com evidências financeiras privadas

Base `8e738e4` (#237), publicada com 700 testes aprovados em Python 3.12/3.14. A rotina diária passa a salvar um retrato financeiro privado com fonte documental e vínculo verificado às vendas, cobertura explícita, sinais por anúncio e acompanhamento manual por período. A central e o histórico administrativo passam a usar esses sinais. O campo é filtrado para clientes e não entra no payload pago; análises antigas não são reescritas. Aguardando a primeira execução, o bloco mostra pendência em vez de zero. Detalhes em `KEVIA_FINANCEIRO.md`. Corrigido também o nome antigo que ainda aparecia no título gráfico como HTML fragmentado, com teste de texto renderizado, tamanho e contraste. Integração/publicação condicionadas aos testes desta revisão.
