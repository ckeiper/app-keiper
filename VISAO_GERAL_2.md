# Visão Geral 2.0

`/` continua direcionando para `/painel`, agora a central administrativa. O
dashboard anterior está preservado em `/painel/legado`, com todos os seus
recursos; painéis individuais, abas, autenticação, renomeação de lojas,
usuários, diagnóstico, sincronização e scheduler não foram removidos.
Não há chamadas ao Mercado Livre nem disparo de sincronizações em GET da nova
visão geral. A rotina horária e a atualização nos painéis individuais continuam
disponíveis. Nenhuma publicação no Render faz parte desta alteração.

## Indicadores e acesso

Reutiliza `period`, `summarize` e `change` de `sales_metrics`, os dados/cobertura
persistidos por `sales_sync` e os filtros/formatação de `sales_view`.
Faturamento e pedidos seguem as mesmas regras: `paid`, pagamento `approved`,
BRL e data de criação em Brasília. O ticket consolidado é a soma dos
faturamentos dividida pela soma dos pedidos, nunca a média dos tickets das lojas.
Hoje está em andamento; períodos personalizados e comparação têm as mesmas
regras da etapa 1. Não utiliza visitas ou conversão na nova página.

A política de acesso existente permite todas as lojas ao tipo `admin`; clientes
veem somente a loja da sessão (`conexao_id`). Os IDs são filtrados por
`pode_ver_loja` antes das leituras de vendas e usados em todas as consultas em
lote. O cálculo também ignora linhas fora dessa lista, defensivamente. Não há
seletor na URL que amplie a permissão. A alteração não cria uma nova política
de delegação de administradores, que ainda não existe no esquema atual.

## Completude e comparação

Uma loja só participa dos totais se os dois períodos tiverem cobertura completa,
sem problemas de integridade (inclusive datas sem localização), conexão ativa,
sincronização recente e sem erro de coleta posterior à última busca bem-sucedida.
Falta de unidades não bloqueia métricas de faturamento/pedidos/ticket, pois não
dependem de unidades. Bases anteriores sem pedidos são válidas, mas sem
percentual de queda. Ticket sem pedidos fica indisponível.

A mesma coorte de lojas é usada nos totais atuais e anteriores. A tela mostra
quantas lojas entraram e quantas foram excluídas: a soma não é apresentada como
total de todas as lojas quando há exclusões. Sem elegíveis, os totais são
indisponíveis, não zero. Na tabela, valores verificáveis de apenas um período
podem aparecer, acompanhados da exclusão e motivo; não são somados. Lojas com
pedidos sem data localizável são excluídas do consolidado mesmo quando o módulo
individual consegue mostrar um subtotal dos pedidos com data válida.

## Alertas

- Faturamento: redução **igual ou superior a 15%**, sem arredondar antes do
  teste do limiar.
- Pedidos: redução **igual ou superior a 20% e pelo menos 5 pedidos**. Os dois
  critérios evitam alertas excessivos em bases pequenas.
- Sincronização/dados: cobertura incompleta em qualquer intervalo, campos
  inválidos ou datas não localizáveis, conexão não ativa, nenhum sucesso de
  busca registrado ou dia selecionado com busca há **mais de 3 horas nos últimos
  7 dias**, ou **mais de 48 horas para dias históricos**. O marco de 7 dias usa
  a data corrente de Brasília e corresponde à janela reconsultada em cada
  sincronização; 48 horas acomodam a rotação diária do histórico e atrasos.
  Todos os dias dos dois períodos precisam atender ao respectivo limite;
  atualizar um dia externo ou apenas parte da seleção não valida os demais.
  No limite exato de 3/48 horas, o dia ainda é aceito.
  Um erro nas categorias `pedidos`, `atualizacao`, `refresh` ou `token` sem data
  ou com `quando >= menor timestamp de sucesso dos dias selecionados` também
  suspende elegibilidade. A resolução exige sucesso posterior ao erro em todos
  os dias selecionados; um sucesso externo não apaga o problema. A cobertura
  completa continua obrigatória. Erros de anúncios/Ads não são tratados como
  falhas de vendas. A recuperação conservadora após erro pode aguardar a rotação
  de todos os dias históricos selecionados.
- Lojas não elegíveis não geram alertas de queda.
- A prioridade financeira usa `max(faturamento anterior - atual, 0)` apenas
  quando ambos são confiáveis. Ordenação decrescente; impacto desconhecido
  aparece depois, sem estimativa inventada. Empates usam nome e tipo. Alertas
  de faturamento e pedidos da mesma loja podem coexistir e **não se somam**.

## Custo e limitações

A página executa a lista autorizada e quatro leituras de dados quando não há
paginação de exceções: agregação diária SQL, cobertura apenas dos dois períodos,
erro relevante mais recente por loja e primeiro lote de datas não canônicas.
As leituras de dados usam uma única transação REPEATABLE READ somente leitura.
Não há API externa, escrita nem sincronização no GET.

Não há teto de 20 mil pedidos nem totais truncados. O PostgreSQL agrega apenas
os pedidos verificados da janela selecionada (incluindo o período anterior),
retornando no máximo uma linha por loja/dia. O índice parcial
idx_overview_orders_day usa loja e a data normalizada por
keiper_overview_day_v1: fuso fixo de Brasília, independente do fuso da sessão.
O formato ISO canônico é validado sem lançar erros para datas impossíveis.
Datas incomuns ou inválidas seguem o classificador Python original de Vendas,
em lotes de 500 com paginação por (conexao_id,pedido_id), no índice parcial
idx_overview_orders_unusual. Todos os lotes usam o mesmo snapshot; não há OFFSET
nem descarte por limite. Assim, datas sem localização em qualquer parte do
histórico continuam sinalizadas, e datas inválidas localizáveis afetam somente
os dias possíveis. A memória dos pedidos é limitada ao lote, embora históricos
com muitas datas incomuns ainda exijam percorrer todas essas exceções.

idx_overview_errors_latest permite buscar somente o erro mais recente entre
pedidos/atualizacao/refresh/token por loja. NULL vem primeiro e continua bloqueando
a elegibilidade. Nenhum corte por idade é aplicado: erros antigos não resolvidos
continuam bloqueando até todos os dias selecionados terem sucesso posterior.
O esquema atual já guarda uma linha por loja/categoria; a consulta também fica
limitada a uma linha por loja caso exista histórico. As funções e índices são
instalados na inicialização, nunca pelo GET; a primeira construção de índices
pode levar tempo proporcional ao histórico da base.

As regressões incluem mais de 100 mil pedidos entre duas lojas (mais de 20 mil
no período por loja), histórico externo, paginação de exceções, paridade com
sales_metrics para pagamentos/valores/datas, 30 mil registros de erros e sucesso
parcial. EXPLAIN ANALYZE com BUFFERS verifica o índice da janela seletiva no
PostgreSQL descartável; isso não é uma medição da latência em produção.
Na execução 38896966440, o plano seletivo usou idx_overview_orders_day,
retornou 25 linhas e acessou quatro blocos em cache, sem varrer os 102 mil
registros inseridos. O teste de concorrência confirma que agregação, cobertura,
erros e páginas de exceções não incorporam escritas posteriores ao snapshot.

Persistem os limites da etapa 1: janela automática de 180 dias, carga gradual,
ausência de fonte confiável para devoluções/reembolsos e falta de cobertura para
dias com mais de 1000 pedidos. Datas sem localização são sinalizadas e não
presumidas como pertencentes a todos os períodos.

## Testes

`python -m unittest -v` executa toda a suíte. Testes de PostgreSQL/Flask exigem
`KEIPER_TEST_DATABASE_URL` apontando a banco descartável, como no workflow
`Sales tests`. Cobrem coorte consistente, ticket ponderado, limites inclusivos,
base zero, prioridade financeira, integridade, cobertura, atualização obsoleta,
permissões, acesso anônimo, consultas em lote, históricos grandes, filtros e
preservação da página antiga, atualização externa que não libera períodos
antigos, limites de 3/48 horas, recuperação de erros por seleção e contrato DOM,
persistência e permissões de renomeação. A API de produção não é acionada nos testes.

## Atualização com a main de 16/10/2026

Branch atualizada com `0838195616f659ae35cbf5a74c7c667f6740a0e2`, incluindo o
PR #3 e os ajustes posteriores de Anúncios/Promoções/Pesos (#4–#6). A integração
combina os imports, mantém `/painel` como Visão Geral 2.0 e preserva a página
anterior em `/painel/legado`, a assinatura compatível dos filtros de Vendas e o
encerramento idempotente do scheduler na preparação das suítes.

Regressões de PostgreSQL/Flask exercitam juntos o redirecionamento da raiz, painel
inicial, legado, Vendas, Anúncios com preço efetivo e colunas PACKAGE_WEIGHT /
SELLER_PACKAGE_WEIGHT, Promoções e permissões, sem consultas à API. O teste de
limite pelo painel confirma alerta para queda de exatamente 15% (R$250 para
R$212,50) e ausência de alerta para queda inferior a 15%, mesmo quando a formatação
arredonda a variação exibida para 15,0%.

Esta atualização altera somente a branch do PR #2. Não faz merge na main,
não altera o Render e não publica a aplicação.
