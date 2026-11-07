# Calendários coincidentes em uma consulta de promoções

O painel administrativo existente `/anuncios/<cid>/<item_id>/promocoes-resultados` compara os calendários das outras ofertas da consulta histórica selecionada com as duas janelas já validadas: antes e dentro do calendário da oferta escolhida. Não faz novas consultas SQL, chamadas à API, escrita ou migração. Autorização, isolamento por loja/anúncio e leitura transacional existentes são preservados. Uma consulta diferente, mesmo do mesmo anúncio, não entra na análise selecionada.

## Regras

`promotion_overlap.analyze` recebe no máximo 200 registros e uma janela de dias completos em Brasília. Requer identidade e calendário verificáveis da oferta escolhida, com status ativo/started e tipo já suportado pela comparação existente, sem variação. Na janela interna, o calendário escolhido precisa abranger a janela inteira; na janela anterior, seu fim exclusivo precisa preceder ou coincidir com o início da oferta escolhida. A lista de tipos de calendário foi extraída para uma constante compartilhada, sem ampliar a regra existente.

A identidade de cada outro registro combina campanha/ID, tipo, offer_id quando retornado e variação. Repetições idênticas nos campos de status, datas, preços e condições são agrupadas. Registros conflitantes com a mesma identidade não são resolvidos escolhendo uma resposta arbitrária: entram como desconhecidos. Conflito na própria identidade selecionada impede o resumo de coincidências, em vez de apresentar zero.

Somente outras ofertas com status ativo/started observado, tipo suportado, sem variação e datas explícitas com fuso entram na interseção. Os demais registros aparecem em contagens separadas de status sem confirmação, variação, tipo sem regra ou identidade/datas insuficientes. Ausência de ID não gera uma identidade inventada.

O intervalo de cada janela é fechado no início e aberto no fim, `[início 00:00, dia seguinte ao fim 00:00)`. Interseção exige `max(inícios) < min(fins)`: calendários que apenas se tocam não coincidem. UTC e demais offsets são convertidos para Brasília. A tabela mostra a interseção recortada, não o calendário original integral; o fim é exclusivo. Não arredonda a aritmética. Exibe até 20 interseções por janela, ordenadas deterministicamente, com total integral e aviso explícito quando há mais resultados. Uma mesma outra oferta pode aparecer nas duas janelas se seu calendário alcançar ambas; isso não cria uma terceira oferta nem soma descontos.

## Limites

São calendários e status de uma única consulta preservada. Não certificam presença durante toda a janela, aplicação conjunta, vigência efetiva ou quais vendas receberam os descontos. Preços não são somados e resultados de vendas não são atribuídos a uma oferta isolada. A contagem zero significa nenhuma interseção verificável naquela consulta e janela; dados insuficientes não certificam ausência de outras promoções. A frente de resultados de promoções permanece parcial.

## Validação

`test_promotion_overlap.py` cobre limites exclusivos, clipping, fusos, janelas antes/dentro, deduplicação, conflitos, IDs ausentes, estados sem confirmação, tipos condicionais, variações, limite de listagem e escape de HTML. A integração PostgreSQL existente foi ampliada com ofertas distintas por loja, confirmando isolamento e leitura sem rede. O browser check cobre 54 combinações de nove estados, dois temas e três larguras (320/390/1440), com contraste, hover, rolagem e foco da tabela, além de quebra de texto e limites das células na tabela de metadados. As fixtures são sintéticas e não são inseridas em produção. Uso autenticado com uma leitura real não foi exercitado como teste.
