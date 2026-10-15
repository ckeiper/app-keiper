# Vendas — etapa 1

## Regras dos novos indicadores

- Referência: `date_created` da API Orders, convertido para o dia de Brasília
  (UTC−3, marketplace brasileiro). Nunca usar `date_closed` como substituto.
- Incluir somente `status == paid`, com ao menos um pagamento `approved` e
  `currency_id == BRL`. Contar cada pedido uma única vez, independentemente do
  número de itens ou pagamentos. O valor é o `total_amount` do pedido, não a soma
  dos pagamentos (que pode envolver frete). Não representa receita líquida.
- Unidades: soma das quantidades de **todos** os `order_items`, incluindo
  variações. Quantidades ausentes não viram 1. Ticket = faturamento / pedidos;
  preço por unidade = faturamento / unidades. Denominador zero: indisponível.
- Intervalos inclusivos de 7/15/30/60/90 dias ou datas personalizadas (até 366
  dias). A comparação termina na véspera do início e tem a mesma quantidade de
  dias. Hoje está em andamento; não se trata de uma comparação hora a hora.
- Variação sobre base zero positiva é exibida sem percentual; 0 contra 0 = 0%.
- Cancelamentos: contagem separada dos pedidos `cancelled` por criação.
  Devoluções e reembolsos não são inferidos de cancelamentos ou de tags.
  Permanecem indisponíveis: não existem eventos/valores confiáveis na coleta
  atual. Nenhum desses valores é subtraído dos novos indicadores.
- A margem e o CSV existentes continuam com os últimos 100 pedidos fechados,
  independentes do filtro dos novos indicadores, conforme identificado na tela.

## Dados e migração

O esquema antigo só preservava fechamento, status, total e parte dos itens.
Na inicialização, a migração aditiva e idempotente acrescenta a `pedidos`:
`criado_em TEXT`, `pagamentos_json JSONB`, `unidades INTEGER`,
`vendas_verificado_em BIGINT`, `vendas_dia_coleta TEXT`. Cria também
`vendas_cobertura` por loja/dia. O dia de coleta vem do filtro explícito de
criação aplicado na API, não do relógio ou da data de fechamento do pedido.
Não modifica usuários, credenciais, colunas existentes nem remove histórico.
Não armazena dados pessoais do comprador nos novos campos de pagamento.

A sincronização consulta os últimos sete dias em cada execução e carrega/renova
até 30 dias adicionais da janela de 180 dias (necessária para comparar 90 dias).
Os dias históricos mais antigos na fila de atualização têm prioridade; dias
sem pedidos também recebem cobertura. A carga inicial completa demanda várias
execuções. Registros antigos não são presumidos como confirmados antes dessa
revalidação. Dados faltantes na busca acionam a consulta de detalhe do pedido.

Cobertura só é confirmada após paginação completa e contagem consistente de
IDs únicos. Falhas, respostas inválidas, duplicações na paginação ou mais de
1000 pedidos por dia deixam o dia sem cobertura e registram erro. Nesse caso,
indicadores agregados ficam indisponíveis e o gráfico exibe lacunas. Essa
limitação da busca exige subdividir janelas numa futura melhoria para lojas
com mais de 1000 pedidos/dia. Não mostrar totais parciais como completos.

Quantidades desconhecidas invalidam unidades/preço médio, preservando métricas
monetárias verificáveis. Campos monetários/pagamentos inválidos em um período
invalidam seus agregados; no gráfico, apenas os dias afetados têm lacunas.

### Datas ausentes ou inválidas

A data válida é sempre a única referência para contar uma venda. Nenhuma data
alternativa é utilizada para incluir um pedido no faturamento ou nas unidades.
Os dois períodos são avaliados separadamente:

- Quando o timestamp é defeituoso, `vendas_dia_coleta` permite localizar o
  problema no dia retornado pelo filtro da API. O período que contém esse dia
  fica com os indicadores afetados indisponíveis. Outros períodos continuam
  calculáveis. A sincronização tenta reparar timestamps inválidos com o detalhe
  do pedido antes de armazená-los.
- Sem esse campo, um prefixo de calendário válido no timestamp defeituoso é
  usado somente para delimitar um possível problema, com margem de um dia para
  cada lado por não haver fuso confiável. Não é usado para contabilizar vendas.
- Sem nenhuma evidência de dia, o registro é excluído dos cálculos e contado em
  um aviso global explícito, uma única vez. Não se presume que pertença a todos
  os períodos. Os valores apresentados consideram pedidos com data válida;
  não se afirma que o histórico sem data esteja reconciliado ou completo.
- Registros defeituosos atribuíveis a datas fora da seleção não invalidam o
  período atual nem o anterior. O fechamento e o instante de atualização não
  substituem a criação para atribuir um pedido a um período.

`complete` representa cobertura das buscas, não integridade dos campos.
Uma data inválida localizada em um dia coberto continua bloqueando o agregado
afetado. Registros sem localização nunca preenchem lacunas de cobertura.
A consulta lê os campos mínimos dos pedidos verificados da loja, sem comparar
prefixos textuais em SQL: assim timestamps malformados não somem do diagnóstico.
Pedidos legados sem verificação têm aviso próprio e continuam fora dos novos
indicadores. A nova coluna é nula para registros preexistentes até revalidação;
nenhum preenchimento retroativo presume datas.

A tela informa a sincronização mais antiga dos dias cobertos na seleção.
Atualizações históricas são rotativas, não dados em tempo real. Eventos fora
da janela de coleta não são revalidados automaticamente.

## Verificação

`python -m unittest -v test_sales`

Os testes usam somente a biblioteca padrão e não importam `main` (a aplicação
original conecta ao banco e inicia o scheduler durante o import). Cobrem
regras financeiras, precisão decimal, filtros, fusos, quantidades, duplicações,
paginação, falhas de API, esquema aditivo e renderização/validação.

Para testar com PostgreSQL e Flask em ambiente isolado, instale
`requirements.txt`, configure **somente um banco descartável** em
`KEIPER_TEST_DATABASE_URL` e execute `python -m unittest -v test_sales_integration`.
Esse teste inicializa o esquema original e desliga imediatamente o scheduler;
usa API simulada, sem credenciais de produção.

Validação local desta alteração: testes unitários e compilação dos módulos.
O workflow `Sales tests` executa os testes unitários e de integração em banco
PostgreSQL 16 descartável nos Pull Requests, sem acesso ao Render.
PostgreSQL/Flask reais e API autenticada de produção não estavam disponíveis.
A migração e a integração precisam desse teste isolado antes de aprovação.
Nenhuma alteração foi aplicada ao banco de produção ou publicada no Render.

Referência de campos: documentação oficial de Orders do Mercado Livre:
https://developers.mercadolivre.com.br/pt_br/gerenciamento-de-vendas
