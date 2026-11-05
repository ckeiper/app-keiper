# Distribuição semanal por anúncio

`GET /anuncios/<cid>/<item_id>/padrao-semanal`, acessível pelo diagnóstico, restrito ao administrador com acesso à loja. Faz cinco consultas sob transação `REPEATABLE READ, READ ONLY`: existência do anúncio na loja e as quatro leituras existentes de `read_sales_context`. Não consulta APIs, responde perguntas, altera anúncios ou grava avaliações. O número de leituras não cresce com os dias.

## Janela e método

As oito semanas de calendário completas anteriores à semana atual, de segunda a domingo, em Brasília: exatamente 56 dias e oito ocorrências de cada dia da semana. Domingo atual também fica fora. Não há seleção automática de apenas semanas favoráveis, preenchimento de lacunas, uso da semana parcial ou reconstrução de histórico.

`listing_sales_summary` valida a janela integral: cobertura diária da loja, pedidos pagos em BRL com pagamento aprovado, quantidades e vínculos completos de todos os itens pagos, preço unitário verificável do anúncio. O indicador é de unidades vendidas deste anúncio; total do pedido não é distribuído aos itens. Pendências de verificação da loja bloqueiam a análise. Após a validação integral, a mesma regra é aplicada aos grupos diários, com agrupamento por data de criação do pedido em Brasília. Cancelados e pagamentos não aprovados não entram.

Cada dia da semana mostra soma de unidades, média (soma ÷ 8), mediana das oito observações, mínimo/máximo e número de semanas com pelo menos uma unidade vendida. Participação = unidades do dia ÷ unidades totais da janela. Sem unidades, a participação fica indefinida, com marcador `—`; totais, médias e faixas verificadas podem ser zero. Faltando um único dia de cobertura ou com falha de integridade, nenhum gráfico ou distribuição é exibido. A cobertura diária continua visível e é explicitamente da coleta da loja, sem certificar a disponibilidade do anúncio.

Os cálculos usam inteiros/Decimal. Números decimais exibidos têm uma casa; arredondamentos podem impedir que percentuais exibidos somem exatamente 100%. As barras representam médias na mesma escala. Tabela acessível com cabeçalhos/caption e rolagem interna em telas estreitas; cobertura com progress e datas textuais, sem depender apenas de cor.

## Limites

Trata-se de perfil descritivo de calendário. Oito observações são o recorte fixo do relatório, sem alegação de suficiência estatística ou validação preditiva. Não controla preço, campanhas, promoções, feriados, lançamento, pausas ou ruptura. Dias anteriores à criação e sem disponibilidade não são normalizados pelo tempo ativo. Um pico isolado pode influenciar a média; mediana e faixa são mostradas para conferência. Não recomenda horários, orçamento ou mudanças no marketplace e não certifica sazonalidade anual/mensal nem repetição futura.

## Verificação

`test_listing_weekly_pattern.py`: janela em todos os dias da semana, aritmética, mediana/pico, zeros, itens/conta, cobertura, datas e transições UTC/Brasília, proteção de rotas e cinco consultas fixas. `test_listing_weekly_pattern_integration.py`: PostgreSQL descartável com cobertura, mapeamento incompleto e lojas distintas, sem chamadas externas. Browser check: 36 combinações de estado, tema e largura (320/390/1440), com tabela, foco, rolagem e indisponibilidade. Fixtures são sintéticas e nunca são inseridas em produção.
