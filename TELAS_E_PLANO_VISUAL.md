# Inventário de telas e plano de melhoria visual — Keiper Consultoria

Levantamento do código em 22/10/2026: **46 rotas de tela e 76 rotas no total**. Uma rota com parâmetros representa uma família de telas, não uma entrada por loja ou campanha. Abas, modais e estados da mesma página aparecem após a lista. Este documento cobre o código versionado, sem acessar dados de produção.

## Entrega atual

- Menu recolhível compartilhado aplicado a todas as páginas que usam pagina_loja, com o contexto e os links da loja atual.
- Publicidade da loja redesenhada: cabeçalho, filtros, indicadores, alertas compactos, tabela e gráfico.
- Minhas lojas e gráfico da campanha Ads já receberam melhorias na entrega anterior.
- As demais linhas abaixo são um backlog; receber o novo menu não significa que o conteúdo de cada tela já foi redesenhado.

## Todas as telas

### Acesso e segurança

| # | Tela | Rota | Próximo passo |
|---|---|---|---|
| 1 | Configuração do primeiro acesso | `/primeiro-acesso` | Revisar visual |
| 2 | Login | `/login` | Revisar visual |
| 3 | Recuperar senha | `/recuperar` | Revisar visual |
| 4 | Redefinir senha | `/redefinir/<token>` | Revisar visual |
| 5 | Segurança da conta | `/seguranca` | Revisar visual |
| 6 | Verificação em duas etapas | `/login/verificar` | Revisar visual |

### Painéis globais

| # | Tela | Rota | Próximo passo |
|---|---|---|---|
| 7 | Central de prioridades global | `/prioridades` | Revisar visual |
| 8 | Minhas lojas / página inicial | `/painel` | Atualizada na entrega anterior |
| 9 | Painel legado | `/painel/legado` | Decidir manutenção ou descontinuação antes de redesenhar |
| 10 | Status das conexões | `/status` | Revisar visual |
| 11 | Visão geral consolidada | `/painel/analise` | Revisar visual |

### Loja, anúncios e operação

| # | Tela | Rota | Próximo passo |
|---|---|---|---|
| 12 | Análise, confirmação e resultado de participação em promoção | `/promocoes/participar/<int:cid>/<pid>/<item_id>` | Revisar visual |
| 13 | Anúncios candidatos à promoção | `/promocoes/candidatos/<int:cid>/<pid>` | Revisar visual |
| 14 | Auditoria de frete | `/auditoria-frete/<int:cid>` | Revisar visual |
| 15 | Catálogo de anúncios | `/anuncios/<int:cid>` | Revisar visual |
| 16 | Confirmação de exclusão de loja | `/excluir/<int:cid>` | Revisar visual |
| 17 | Custos e margens | `/custos/<int:cid>` | Revisar visual |
| 18 | Demandas da loja | `/demandas/<int:cid>` | Revisar visual |
| 19 | Desempenho da loja | `/desempenho/<int:cid>` | Revisar visual |
| 20 | Detalhe de uma campanha Ads | `/ads/<int:cid>/campanha/<path:campanha_id>` | Gráfico atualizado; revisar restante da página |
| 21 | Full e vendas da loja | `/full/<int:cid>` | Revisar visual |
| 22 | Full — seleção de loja | `/full` | Revisar visual |
| 23 | Histórico de ações do anúncio | `/anuncios/<int:cid>/<item_id>/acoes` | Revisar visual |
| 24 | Histórico de um concorrente | `/anuncios/<int:cid>/concorrencia/<int:target_id>` | Revisar visual |
| 25 | Lista e gestão de campanhas Ads | `/campanhas/<int:cid>` | Revisar visual |
| 26 | Minhas prioridades da loja | `/prioridades/<int:cid>` | Revisar visual |
| 27 | Monitor de concorrência | `/anuncios/<int:cid>/concorrencia` | Revisar visual |
| 28 | Promoções da loja | `/promocoes/<int:cid>` | Revisar visual |
| 29 | Publicidade / Product Ads da loja | `/ads/<int:cid>` | Redesenhada nesta entrega |
| 30 | Ranking e fila de anúncios | `/ranking-anuncios/<int:cid>` | Revisar visual |
| 31 | Resumo e gestão da loja | `/painel/<int:cid>` | Revisar visual |
| 32 | Resumo operacional da loja | `/painel/<int:cid>/operacao` | Revisar visual |
| 33 | Vendas da loja | `/vendas/<int:cid>` | Revisar visual |

### CRM

| # | Tela | Rota | Próximo passo |
|---|---|---|---|
| 34 | CRM — detalhe e edição do lead | `/crm/<int:lead_id>` | Revisar visual |
| 35 | CRM — novo lead | `/crm/novo` | Revisar visual |
| 36 | CRM — configuração da integração | `/crm/configuracao` | Revisar visual |
| 37 | CRM — importar transcrição | `/crm/importar` | Revisar visual |
| 38 | CRM — lista de leads | `/crm` | Revisar visual |
| 39 | CRM — revisar importação | `/crm/revisar/<draft_id>` | Revisar visual |

### Administração e diagnóstico

| # | Tela | Rota | Próximo passo |
|---|---|---|---|
| 40 | Coleta piloto de visitas Copas | `/admin/coleta-visitas-copas` | Revisar visual |
| 41 | Diagnóstico de um anúncio | `/diagnostico/<int:cid>/<item_id>` | Revisar visual |
| 42 | Diagnóstico geral | `/diagnostico` | Revisar visual |
| 43 | Editar usuário | `/usuarios/editar/<int:uid>` | Revisar visual |
| 44 | Excluir usuário | `/usuarios/excluir/<int:uid>` | Revisar visual |
| 45 | Gestão de usuários | `/usuarios` | Revisar visual |
| 46 | Progresso da coleta de visitas | `/admin/progresso-visitas` | Revisar visual |

## Subtelas e estados dentro dessas páginas

- Resumo da loja: abas Visão geral, Oportunidades e Análise por anúncio; detalhe de produto em modal.
- Catálogo de anúncios: abas Meus anúncios e Concorrência; detalhes técnicos expansíveis; busca, filtros e paginação.
- Diagnóstico do anúncio: evidências, fatores, linha do tempo, troca de métrica, paginação e histórico de ações.
- Promoções: candidatos, análise de preço e margem, confirmação e resultado de participação.
- Publicidade: período padrão ou personalizado, busca/situação/ordenação de campanhas, paginação, alertas expandidos e recolhidos, detalhamento diário e estado sem dados.
- Campanha Ads: períodos de 7/15/30/60/90 dias, cobertura parcial, histórico de mudanças e comparação de períodos.
- Auditoria de frete: upload, progresso, prévia, importação, histórico, consolidação e comparação com vendas.
- Custos: configuração, edição por anúncio e importação de planilha.
- CRM: filtros por etapa e prazo, cadastro, edição, histórico de contatos, importação, revisão e vínculo ao cadastro existente.
- Segurança: ativação, QR code, confirmação, códigos de recuperação e desativação do segundo fator.
- Todas: loading, sem dados, falha, acesso negado, feedback de formulário, foco de teclado e versão para celular devem entrar na revisão visual.

## Ordem sugerida — uma tela por vez

1. Publicidade da loja — entrega atual.
2. Lista e gestão de campanhas Ads.
3. Detalhe de uma campanha Ads, além do gráfico já atualizado.
4. Resumo e gestão da loja, incluindo as três abas.
5. Catálogo de anúncios e detalhes.
6. Desempenho, diagnóstico do anúncio e ranking.
7. Vendas e Full.
8. Promoções, candidatos e confirmação de participação.
9. Custos e auditoria de frete.
10. Demandas e prioridades.
11. Visão geral consolidada e status.
12. CRM, uma rota de cada vez.
13. Usuários, login, recuperação de senha e segurança.
14. Diagnósticos administrativos e decisão sobre telas legadas.

Para cada tela: revisar desktop e celular, preservar regras e permissões, testar ações existentes e validar estados vazio/erro. Não alterar automaticamente todas as telas do backlog nesta entrega.

## Demais rotas — inventário completo

Estas rotas complementam o sistema, mas não são telas independentes de navegação. Fluxos auxiliares podem renderizar confirmações ou mensagens de erro.

### Arquivo

| Rota | Métodos | Função |
|---|---|---|
| `/exportar_demandas/<int:cid>` | GET | `exportar_demandas` |
| `/exportar_vendas/<int:cid>` | GET | `exportar_vendas` |
| `/logo.png` | GET | `logo_arquivo` |
| `/modelo_custos/<int:cid>` | GET | `modelo_custos` |

### Ação

| Rota | Métodos | Função |
|---|---|---|
| `/anuncios/<int:cid>/concorrencia/<int:target_id>/estado` | POST | `competitor_state` |
| `/crm/<int:lead_id>/contato` | POST | `crm_contact` |
| `/crm/revisar/<draft_id>/vincular` | POST | `crm_link_draft` |
| `/primeiro-acesso/imposto` | POST | `primeiro_acesso_imposto` |
| `/prioridades/<int:cid>/acesso` | POST | `acesso_prioridades_cliente` |
| `/promocoes/meta/<int:cid>` | POST | `salvar_meta_promocoes` |
| `/renomear/<int:cid>` | POST | `renomear` |
| `/salvar_config/<int:cid>` | POST | `salvar_config` |
| `/salvar_custo/<int:cid>/<item_id>` | POST | `salvar_custo` |
| `/salvar_roas/<int:cid>/<campanha_id>` | POST | `salvar_roas` |
| `/upload_custos/<int:cid>` | POST | `upload_custos` |
| `/usuarios/criar` | POST | `usuarios_criar` |

### Endpoint / fragmento

| Rota | Métodos | Função |
|---|---|---|
| `/admin/diagnostico-visitas-copas` | GET | `diagnostico_visitas_copas` |
| `/admin/progresso-visitas-copas` | GET | `progresso_visitas_copas` |
| `/atualizacoes/<int:cid>/<scope>` | GET, POST | `section_refresh` |
| `/crm/resumo` | GET | `crm_summary` |
| `/diagnostico/anuncios/<int:cid>/<item_id>` | GET | `diagnostico_anuncio` |
| `/painel/saude` | GET | `painel_saude` |
| `/painel/tendencias` | GET | `painel_tendencias` |

### Fluxo auxiliar

| Rota | Métodos | Função |
|---|---|---|
| `/atualizar` | GET | `atualizar` |
| `/atualizar/<tipo>/<int:cid>` | GET | `atualizar_tipo` |
| `/callback` | GET | `callback_ml` |
| `/conectar` | GET | `conectar` |
| `/oauth` | GET | `callback_ml` |

### Redirecionamento / ação

| Rota | Métodos | Função |
|---|---|---|
| `/` | GET | `home` |
| `/logout` | GET | `logout` |

## Manutenção do inventário

Gerado por scripts/build_screen_plan.py a partir da inspeção AST de todas as rotas Flask dos módulos Python. scripts/screen_inventory.py também gera visual-qa/routes.json com arquivo, linha e função de origem. Novas rotas exigem revisão da contagem e da classificação; os caminhos de ação, arquivos e fragmentos não foram omitidos.
