# Full e vendas por anúncio

## Uso

Abra **Full e vendas** no menu da loja ou no link do anúncio em **Anúncios**.
Selecione loja, anúncio e período (mesmos presets de Vendas; personalizado até
180 dias). O relatório usa somente dados já coletados e não chama a API ao abrir.
As barras mostram unidades pagas e verificadas do anúncio, de qualquer logística.
Os pontos representam o estoque Full observado nas consultas de cada dia.

Verde significa quantidade positiva em todas as consultas desse dia; laranja,
zero em todas; roxo, consultas conhecidas divergentes; cinza, nenhuma consulta
ou ao menos uma consulta desconhecida. Esses pontos não afirmam disponibilidade
durante o dia inteiro. Não há interpolação, preenchimento de lacunas, cálculo
de horas com estoque nem atribuição das vendas ao Full. O gráfico não estabelece
causalidade. A tabela detalha cada consulta, horário de Brasília e inventários.

## Fontes oficiais e permissões

Consultadas em 19/10/2026:

- [Mercado Envios Full](https://developers.mercadolivre.com.br/envios-fulfillment)
- [Fulfillment](https://developers.mercadolivre.com.br/en_us/fulfillment)
- [Estoque distribuído](https://developers.mercadolivre.com.br/pt_br/lojas-oficiais/estoque-distribuido)

A sincronização existente de `/items` fornece `shipping.logistic_type` e
`inventory_id`, inclusive por variação. A logística informada é exibida
separadamente do estoque: adesão/configuração Full não prova disponibilidade.
Outra logística também não prova ausência de estoque Full, pois há convivência.
Não se usa `available_quantity` geral do anúncio como estoque Full.

Com o token já autorizado da loja, a nova etapa consulta somente
`GET /inventories/{inventory_id}/stock/fulfillment`. O estoque usa o campo
`available_quantity` dessa resposta, com identidade do inventário conferida.
As permissões efetivas dependem do token e do inventário: 401/403 são desconhecidos,
nunca zero. Não se solicita escopo adicional nem se alteram configurações ML.
A autorização real das seis contas deverá ser observada após futura publicação;
este PR não acessa produção nem muda permissões.

## Histórico e ausência de dados

Não foi encontrado histórico confiável de estoque Full no banco atual. A nova
tabela `full_observations` começa vazia, sem migração retrospectiva. A tela informa
a primeira coleta e a primeira confirmação verificável, quando existirem. Antes
disso, e entre períodos sem consultas, o estado é desconhecido. Não se reconstruem
estados antigos a partir de vendas, estoque atual ou movimentos sem saldo inicial.
Não usa o endpoint de operações para inventar cobertura passada.

Variações guardam seus vínculos de inventário. Inventários compartilhados são
consultados/somados uma vez por anúncio. Uma variação com quantidade positiva
comprova algum estoque; quantidade total só é exibida quando todos os vínculos são
verificáveis. Para afirmar zero, todas as variações precisam de resposta válida.
Variação sem `inventory_id`, falha de API ou metadados com mais de três horas
impedem afirmar estoque zero. Evidências guardam IDs, quantidades e motivo seguro;
não guardam token, cabeçalhos nem corpo bruto de erro.

Vendas reutilizam `listing_sales_summary`: pedidos pagos/aprovados em BRL,
quantidades e vínculo completo de itens, cobertura diária e criação em Brasília.
Dias incompletos e pedidos antigos não verificados produzem lacunas. Hoje não tem
total diário fechado. Zero só aparece em dias de vendas verificáveis.

## Integração e limites

Migração aditiva e idempotente: coluna `anuncios.full_metadata_json`, tabela de
observações e índice por loja/anúncio/data. A exclusão já existente de uma loja
inclui o novo histórico. Não altera tabelas ou métricas de vendas existentes.

A fila normal executa `full` após atualizar os anúncios. Até 50 anúncios por
execução, priorizando os menos recentemente consultados, até 75 chamadas únicas
e orçamento de 45 segundos, com timeout de conexão/leitura. Em 401/403/429,
interrompe novas chamadas nessa execução; a fila horária existente permite nova
tentativa. Não há repetição imediata em rate limit. Cada observação é persistida
separadamente. Itens não visitados permanecem lacunas, sem snapshot artificial.
Uma falha remota de Full fica no histórico próprio e não invalida vendas válidas.

O relatório respeita a autorização existente da loja e confirma que o anúncio
pertence a ela. Leituras usam snapshot consistente, orçamento de consulta e
limite de 10 mil observações por seleção; acima disso pede período menor,
sem mostrar histórico truncado. Em catálogos grandes, a coleta rotativa pode
demorar várias execuções para alcançar todos os anúncios; não há promessa de
monitoramento em tempo real ou de detecção de toda mudança intradiária.

## Validação e publicação

Testes unitários cobrem estoque oficial, variações, ausência de vínculo, metadados
antigos, falhas, rate limits, orçamento, lacunas, vendas e escape HTML. Testes
PostgreSQL/Flask cobrem persistência, seleção de anúncios, isolamento de contas,
relatório sem chamadas de rede e chamada da etapa na sincronização normal.

Branch/PR separado. Sem merge, deploy, alteração no Render ou escrita em produção.
Após aprovação futura, conferir no diagnóstico das consultas se os tokens das
lojas têm acesso aos respectivos inventários e acompanhar o início da cobertura.
