# Anúncios: promoções e pesos

Correção isolada da Visão Geral 2.0. Não requer mudança de configuração de deploy.
Não altera endpoints de escrita do Mercado Livre: todas as consultas são GET.

## Problemas encontrados

- A integração local/MLB usava `/marketplace/seller-promotions`, rota de Global Selling.
- Anúncios eram acrescentados duas vezes à lista de gravação; a extração de peso não
  consultava `attributes`, ignorava variações e não registrava a origem/unidade.
- `original_price > price` no item era mostrado como promoção sem confirmar participação.
- A busca parava em 200 anúncios e podia apagar registros após uma busca incompleta.
- Campanhas eram apagadas antes de concluir a consulta dos seus itens.

## Contratos utilizados

| Recurso | Campos utilizados | Limitações |
| --- | --- | --- |
| `/users/{seller}/items/search?search_type=scan` | results, scroll_id, paging.total | Limit 100, sem offset; falha de busca não apaga dados |
| `/items?ids=...&include_attributes=all` | attributes, sale_terms, shipping.dimensions, variations[].attributes/attribute_combinations | Lotes de 20; item com erro mantém o registro anterior |
| `/seller-promotions/items/{id}?app_version=v2` | type, id, status, price, original_price, start_date, end_date/finish_date, variation_id quando presente | Array por anúncio; nenhum preço é copiado de `items.price`; não atribuir ofertas do anúncio a uma variação específica sem ID |
| `/seller-promotions/users/{seller}?app_version=v2` | results: id, type, name, status, start_date, finish_date | Mantém a aba Promoções, inclusive campanhas sem anúncios associados |
| `/seller-promotions/promotions/{id}/items?promotion_type=...&app_version=v2` | results: id, status, price | Apenas participantes started/active alimentam o cache legado de itens ativos |

A paginação de campanhas aceita `paging.searchAfter`/`search_after` e offset/total;
páginas repetidas ou limite defensivo de 1000 páginas invalidam a coleta, preservando
integralmente o cache anterior. Campanhas e participantes só são substituídos após
coleta completa, na mesma transação. A aba Anúncios usa seu próprio snapshot por item,
portanto não deduz a participação pelo status geral de uma campanha.

Tipos do vendedor: PRICE_DISCOUNT, SELLER_CAMPAIGN, SELLER_COUPON_CAMPAIGN.
Campanhas de plataforma/cofinanciadas mantêm o tipo original (DEAL, SMART,
MARKETPLACE_CAMPAIGN etc.). A indicação de origem da campanha **não informa quem
financiou todo o desconto**. Campos adicionais, inclusive boost/percentuais MELI e
vendedor, ficam preservados no JSON bruto, sem inventar um preço final ou somar descontos.
Tipos futuros têm origem “Não disponível”. Candidatas/pendentes/finalizadas aparecem com
status explícito e preço identificado como não ativo; nunca entram no contador de ativos.
Desconto percentual só é calculado com os dois preços positivos e original > promocional.
Datas não retornadas ficam “Não disponível”. Todos os valores são escapados no HTML.
Datas com fuso explícito também impedem que uma oferta vencida ou ainda não iniciada
seja contada/exibida como ativa, mesmo que a última resposta da API ainda diga active.
O status original é mantido visível entre parênteses. Datas sem fuso continuam exibidas
como retornadas, sem presumir o fuso horário da campanha.

## Pesos e rastreabilidade

`pesos_json` guarda valor, unidade original, kg, campo exato, valor bruto e escopo
(anúncio/ID da variação). A data de coleta é `anuncios.atualizado_em`. São consultados
WEIGHT, SELLER_PACKAGE_WEIGHT e PACKAGE_WEIGHT em attributes/sale_terms e combinações
de variação; `shipping.dimensions` é fallback com formato `AxBxC,peso_em_gramas`.
Produto, pacote declarado e dimensões continuam identificados separadamente na célula;
não se afirma que sejam equivalentes ou que PACKAGE_WEIGHT seja uma pesagem logística.

Conversões aceitas: kg, g, gr/gramas, mg, lb e oz. Atributos sem unidade reconhecida,
números não finitos, zero/negativos ou formatos ambíguos não viram kg por suposição.
Unidades podem vir em value_struct, values[].struct ou texto explícito `1,5 kg`.
Variações sem peso exibem a ausência e apontam o peso comum, quando existir.

O campo legado `peso` permanece em kg para consumidores existentes. Prioridade:
SELLER_PACKAGE_WEIGHT, shipping.dimensions, PACKAGE_WEIGHT, WEIGHT. Se houver pesos
próprios de variações, só há escalar quando todas informam o mesmo valor; nenhuma média
ou escolha arbitrária da primeira variação. A coluna de frete continua sendo estimativa
pela tabela existente e peso cadastrado, com esse limite explicitado na tela.

**Mapeamento atualizado por solicitação do usuário em 15/10/2026:** Peso cadastrado
exibe exclusivamente PACKAGE_WEIGHT; Peso logístico exibe exclusivamente
SELLER_PACKAGE_WEIGHT e traz a indicação “Declarado pelo vendedor”. São valores oficiais
retornados nos atributos da API, sem afirmar que SELLER_PACKAGE_WEIGHT é peso aferido ou
faturável pela transportadora. Ausência de um campo não usa o outro como substituto.
Cada variação mantém seu próprio valor e a origem/unidade permanecem no tooltip e JSON.

Limite semântico mantido: não foi confirmado um campo por anúncio com
contrato público de peso logístico aferido/faturável nos recursos utilizados. A API de
envios possui `shipments/{id}.dimensions.weight` e `shipments/{id}/items[].dimensions.weight`,
mas são dados de um envio/itens de uma venda: não se transfere peso de pacote, múltiplas
unidades ou envio histórico para o cadastro do anúncio. Também não se usa peso cadastrado,
PACKAGE_WEIGHT read_only, dimensões cúbicas ou cálculo volumétrico como prova de peso
logístico aferido. A coluna usa a definição operacional expressamente escolhida pelo
usuário, com a ressalva do peso declarado visível; não foi criado um endpoint de pesagem.

## Permissões, falhas e atualização

Token OAuth da conta vendedora autorizada. Revisar no painel do aplicativo a permissão
funcional de leitura de Anúncios e de “Promoções, cupons e descontos”. Uma permissão de
admin no GitHub não permite confirmar a configuração do aplicativo ML. Não foram usados
tokens de produção nem alteradas permissões; disponibilidade real depende da conta/tipo
de campanha. 401 pede renovação/autorização; 403 mostra orientação de permissão/conta;
404 e JSON inválido são indisponibilidade, **não ausência de promoção**.

São até três tentativas para rede, JSON inválido, 429 e 5xx, com espera exponencial e
Retry-After numérico respeitado até 30 segundos. Retry-After maior ou em formato data
adia a consulta para a próxima atualização sem manter o worker esperando. 401/403/429
abrem circuito para os demais itens de promoções naquela coleta. Erros não incluem token
nem corpo remoto. Snapshot anterior é preservado para auditoria, marcado não confirmado
e excluído do contador ativo. Snapshot com mais de duas horas é desatualizado na tela.
Uma resposta 200 `[]` é a única que confirma ausência de promoções associadas.
Não há consultas remotas na renderização da página. Atualizações manuais e jobs existentes
executam a coleta. Respostas por item/campanha ficam limitadas ao formato documentado;
uma mudança de contrato falha explicitamente.

Migração aditiva/idempotente no startup: `anuncios.pesos_json TEXT` e
`anuncios.promocoes_json TEXT`, nullable. Registros existentes ficam não verificados até
a próxima coleta. Nenhuma coluna existente é removida. Rollback do código mantém os
novos campos sem afetar o schema antigo. A branch parte de main e não incorpora a branch
`codex/visao-geral-etapa-2`.

## Validação

`python -m unittest discover -v` cobre normalização/unidades, dimensões, conflitos,
variações incompletas, rastreabilidade, escaping, ausência de promoção, tipo/status,
rate limit/Retry-After, autorização, recuperação de falhas, paginação e preservação
atômica do cache. Os testes extraem as funções reais de main via AST para exercitar
gravação e HTML sem inicializar banco/scheduler; não substituem uma verificação de
PostgreSQL real. `test_listing_integration.py` é opt-in com
`KEIPER_TEST_DATABASE_URL` apontando **exclusivamente a banco descartável**.
Não foi realizada chamada autenticada ao Mercado Livre ou validação em produção.

A suíte também verifica duas gravações reais sem duplicação e com preservação do custo,
renderização autenticada sem chamadas de rede, isolamento por loja e rollback do cache
de campanhas após falha de escrita. A preparação dos testes encerra o scheduler apenas
se estiver rodando, permitindo executar Anúncios e Vendas juntos no mesmo processo.

## Fontes oficiais consultadas em 15/10/2026

- [Gerenciar promoções](https://developers.mercadolivre.com.br/pt_br/gerenciar-ofertas)
- [Campanhas do vendedor](https://developers.mercadolivre.com.br/pt_br/realizacao-de-testes/campanhas-do-vendedor)
- [Atributos e SELLER_PACKAGE_WEIGHT](https://developers.mercadolivre.com.br/pt_br/atributos)
- [Dimensões e unidades](https://developers.mercadolivre.com.br/pt_br/autenticacao-e-autorizacao/itens-atributos-de-envio-e-dimensoes)
- [Variações e include_attributes](https://developers.mercadolivre.com.br/pt_br/autenticacao-e-autorizacao/variacoes)
- [Busca de itens e scan](https://developers.mercadolivre.com.br/pt_br/itens-e-buscas)
- [Permissões funcionais](https://developers.mercadolivre.com.br/pt_br/recurso-visits/permissoes-funcionais)
- [Envios](https://developers.mercadolivre.com.br/pt_br/registre-o-seu-aplicativo/gerenciamento-de-envios)
- [sale_price](https://developers.mercadolivre.com.br/devcenter/api-de-precos): identifica o preço vencedor por contexto e regular_amount; usado no resumo somente quando há metadata.promotion_id e preços positivos em BRL com desconto. Não usa items.price como prova de promoção e não inventa vigência.

## Ajustes após conferência da produção

Confirmados em chamadas autenticadas: PACKAGE_WEIGHT e SELLER_PACKAGE_WEIGHT da Copas
Ind retornam pesos diferentes; o mapeamento das colunas segue a escolha do usuário.
O HTTP 400 de um anúncio encerrado retornou `Item status is not allowed (closed)`;
anúncios com status closed agora são marcados como não aplicáveis sem consultar promoções.
Um anúncio ativo retornou HTTP 409 na consulta de campanhas, mas sale_price confirmou
amount 221.81, regular_amount 299 e metadata.promotion_id no contexto channel_marketplace.
O preço vencedor tem sua própria data/erro no snapshot e pode ser mostrado com aviso
explícito de campanhas não confirmadas. Os circuitos de 401/403/429 são separados por
recurso. Um erro não vira ausência de promoção.

A coluna Promoção mostra um resumo compacto, com o preço vencedor oficial quando
confirmado. Campanhas ativas e candidaturas/outros status ficam em blocos expansíveis
fechados por padrão. Não se escolhe arbitrariamente o menor preço das campanhas.
Valores monetários e datas são formatados para leitura. Status e respostas brutas
permanecem no snapshot para rastreabilidade.

Atualizações manuais de Anúncios/Promoções rodam em segundo plano, com proteção contra
duplicação por loja e aviso na página, evitando timeout HTTP em lojas com centenas de
anúncios. Cada snapshot é gravado após a consulta do item, preservando progresso se a
coleta for interrompida; o cache geral de campanhas continua atômico.
