# Conferência retrospectiva de uma média fixa de vendas

`GET /anuncios/<cid>/<item>/conferencia-media`, acessível pelo padrão semanal, restrito ao administrador com acesso à loja/anúncio. Reutiliza a janela de oito semanas completas anterior à semana em curso e o leitor estrito de vendas do padrão semanal. Mantém cinco consultas em `REPEATABLE READ, READ ONLY`, sem chamadas à API, gravações ou novos campos de banco.

A conferência exige os 56 dias de cobertura e os mesmos pedidos pagos, pagamentos aprovados, itens e preços verificáveis do relatório de origem. Pendência, escopo divergente ou lacuna bloqueia todos os resultados; ausência não vira zero. A série diária precisa conter exatamente 56 datas consecutivas e unidades inteiras não negativas.

## Método fixo

São quatro rodadas. A base tem 28 dias; a semana testada tem os sete dias imediatamente seguintes. A origem avança sete dias por rodada. Índices inclusivos: bases 0–27, 7–34, 14–41 e 21–48; semanas testadas 28–34, 35–41, 42–48 e 49–55. Uma semana concluída pode entrar na base de uma rodada posterior. Nenhuma venda da própria semana testada ou de dias posteriores entra na respectiva estimativa.

Estimativa da semana = unidades dos 28 dias anteriores ÷ 4. Erro = estimado − realizado; erro absoluto = módulo do erro. Erro absoluto médio = soma dos quatro erros absolutos ÷ 4. Desvio médio = soma dos quatro erros ÷ 4, com positivo indicando estimativa acima do realizado. Percentual agregado = soma dos erros absolutos ÷ soma das unidades realizadas nas quatro semanas × 100. Pode superar 100%; não é uma nota de precisão. Se não há unidades realizadas, o percentual fica indefinido, mesmo com erro em unidades igual a zero.

Cálculos em inteiros/Decimal, sem arredondar estimativas antes de calcular os erros; exibição com uma casa decimal. Médias podem produzir frações de unidade. Todas as rodadas aparecem, sem ajuste de parâmetros ou escolha das semanas mais favoráveis.

Referência conceitual para a separação temporal de base e teste: Hyndman e Athanasopoulos, [Forecasting: Principles and Practice, seção 5.10](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation), consultada em 06/11/2026. A implementação usa uma janela móvel fixa de 28 dias e avalia o total semanal, sem alegar reproduzir um protocolo mais amplo de seleção ou certificação de modelos.

## Limites

É simulação retrospectiva com os registros **atualmente** verificados. Não reproduz os dados ou status que estavam disponíveis nas datas históricas. Mede vendas observadas, sem corrigir demanda reprimida, lançamento, pausas, ruptura, preço, promoções ou feriados. Quatro rodadas e uma única regra não certificam precisão futura, sazonalidade, significância, previsão de estoque ou data de ruptura. A tela não produz projeção para datas futuras nem recomenda alteração no marketplace.

## Verificação

Testes cobrem limites temporais, denominadores, frações, erro superior a 100%, ausência de vazamento de unidades posteriores, incorporação de semanas apenas nas rodadas seguintes, base inválida, isolamento, permissões e cinco consultas fixas. Integração PostgreSQL verifica a loja correta e bloqueio por cobertura. Preview usa somente fixtures sintéticas; 48 combinações de estados, dois temas e larguras 320/390/1440, com foco e rolagem da tabela. Nenhum dado de demonstração é criado em produção.
