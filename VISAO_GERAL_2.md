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

São quatro consultas por página com lojas: lista autorizada, pedidos mínimos,
cobertura e erros. As três leituras de dados ocorrem na mesma transação somente
leitura `REPEATABLE READ`. Não há consulta por loja, API externa, escrita,
agendamento adicional ou recarga automática. Usa o índice existente de
`(conexao_id, pedido_id)` para ordenar e limitar a leitura.

O lote de pedidos verificados tem limite de **20.000 registros**, mais uma linha
para detectar excesso, antes do processamento em Python. Nenhum total parcial
é apresentado se ultrapassar: todas as lojas da seleção ficam excluídas, e os
alertas de queda suspensos. A tabela explica o limite. A leitura inclui histórico
verificado fora do intervalo para não esconder datas malformadas e problemas
sem localização, logo esse teto considera também esses registros. Para volumes
maiores será necessário agregar/instrumentar o histórico no banco; não elevar
o limite sem medir memória/latência. O teto pode ser alcançado mesmo em filtros
curtos se a base histórica for grande.

Persistem os limites da etapa 1: janela automática de 180 dias, carga gradual,
ausência de fonte confiável para devoluções/reembolsos e falta de cobertura para
dias com mais de 1000 pedidos. Datas sem localização são sinalizadas e não
presumidas como pertencentes a todos os períodos.

## Testes

`python -m unittest -v` executa toda a suíte. Testes de PostgreSQL/Flask exigem
`KEIPER_TEST_DATABASE_URL` apontando a banco descartável, como no workflow
`Sales tests`. Cobrem coorte consistente, ticket ponderado, limites inclusivos,
base zero, prioridade financeira, integridade, cobertura, atualização obsoleta,
permissões, acesso anônimo, consultas em lote, teto de leitura, filtros e
preservação da página antiga, atualização externa que não libera períodos
antigos, limites de 3/48 horas, recuperação de erros por seleção e contrato DOM,
persistência e permissões de renomeação. A API de produção não é acionada nos testes.
