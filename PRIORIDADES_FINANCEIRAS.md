# Evidências financeiras nos anúncios prioritários

Integração dos custos documentados à fila existente, sobre a base `36df005` (#236).

## O que muda

Para o administrador, os cards de anúncios com perda bruta passam a mostrar evidências adicionais quando houver custos documentados compatíveis com as vendas do período:

- Contribuição documentada negativa no período atual, com o valor em reais.
- Margem documentada menor que no período anterior, com os dois percentuais e a diferença em pontos percentuais. Margens negativas não são descartadas como dado ausente.
- Orientação para conferir componentes/fontes na rentabilidade do anúncio. Não há promessa de recuperação monetária ou alteração automática de preço/campanha.

A ordem continua sendo a maior perda **bruta** verificada, conforme a fila original. Este lote não converte a fila em um ranking global de lucro nem inclui anúncios sem perda bruta apenas por terem contribuição negativa. As fontes são declaradas pelo administrador, não auditadas automaticamente.

## Critérios

- Apenas os registros mais recentes de cada anúncio e dos dois períodos exatos (7 ou 30 dias encerrados), na mesma loja.
- Cada registro precisa manter correspondência com valor bruto, unidades e fingerprint completo da base de vendas. A base inclui identidade/status/pagamentos dos pedidos e os vínculos/preços/quantidades dos itens.
- Registro ausente ou alterado não vira margem zero. Uma versão antiga não substitui silenciosamente uma versão recente invalidada.
- Contribuição atual negativa pode ser confirmada sem inventar o período anterior. O alerta de queda de margem exige dados completos nos dois períodos e denominadores válidos.
- Flags de confirmação com valores inválidos, ausentes, booleanos ou não finitos continuam sendo tratadas como informação não confirmada.

## Segurança e desempenho

As informações financeiras são adicionadas **somente para sessões administrativas**. Clientes continuam vendo a fila operacional sem consulta à tabela de custos e sem exposição de margens, contribuições ou referências financeiras.

Pedidos, itens e cobertura já carregados pelo ranking são reutilizados. Há uma única consulta financeira adicional por loja/período, sem consultas por anúncio ou chamadas ao marketplace. O agrupamento por anúncio e janela ocorre em memória. A leitura inicial usa `REPEATABLE READ, READ ONLY`, incluindo os registros financeiros no mesmo snapshot das vendas, enquanto os coletores seguem executando normalmente.

O fingerprint é compartilhado com a página de rentabilidade; a extração do helper não muda hashes existentes. Não há nova tabela, migração ou alteração dos custos salvos. Regras/orçamento da KEVIA e API paga não são alterados.

## Validação

Testes de fontes ausentes, registro recente inválido, identidade de pedido alterada sem mudar valores, isolamento por loja/período, negativos, flags inválidas, compatibilidade da fila e consulta única para múltiplos anúncios. Integração PostgreSQL verifica o card administrativo real, ausência de consulta/exposição financeira na sessão de cliente e supressão dos alertas após alteração da venda, preservando os registros. QA de navegador cobre cards com evidência, dados alterados e custos ausentes em desktop/celular e teclado.
