# Continuidade verificável no gráfico e na triagem

A linha do tempo e o diagnóstico passam a usar a mesma validação de preços do histórico: confirmação booleana explícita, preço positivo em centavos e timestamp único. A última leitura diária ambígua ou inválida permanece como lacuna, sem recuperar o preço anterior. Eventos na primeira data visível ainda podem usar uma leitura válida do dia anterior dentro do limite de seis horas; não há novas consultas ou preenchimento artificial de lacunas.

A triagem de aumento exige continuidade desde o evento até a última leitura do recorte. Uma falha intermediária, duplicidade ou intervalo superior a seis horas impede reapresentar um aumento antigo como base da recomendação. Uma nova sequência válida pode gerar uma nova verificação sugerida. Isso não identifica causa de queda nem recomenda desconto automático.

A triagem de Full só descreve recuperação observada se a última data do recorte mostrar estoque. Uma leitura positiva anterior seguida por data desconhecida não confirma a situação na última data.

A linha do tempo recebeu o visual azul-marinho, com legenda, eixos, tabela, filtros e paginação contrastantes e navegação por teclado. Não há alterações em vendas, preços, estoques ou dados persistidos.

Validação: confirmação inválida, duplicidade diária, timestamps fora do recorte, comparação na virada de dia, falhas intermediárias, retomada válida e Full desconhecido após leitura positiva. Interface verifica renderização real do gráfico, alinhamento de marcadores, contraste, filtros, teclado e responsividade.
