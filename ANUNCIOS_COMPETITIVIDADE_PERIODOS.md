# Amostras de competitividade em dois períodos

O histórico da distância entre preços agora resume, para cada concorrente vinculado, o período encerrado selecionado e o período anterior de mesma duração. Exibe as datas, pares válidos/leituras e quantos pares mostram o preço próprio acima, igual ou abaixo do concorrente.

São contagens da amostra carregada, sem ponderação por tempo ou vendas. Não representam dias em cada condição, participação de mercado, média do período ou perda de vendas. Ausência de leituras fica explícita e não é tratada como estabilidade. Os limites existentes de vínculos e histórico continuam visíveis. Nenhuma consulta adicional, alteração de preço ou reconstrução do passado foi introduzida.

Também foi corrigida a continuidade: uma leitura própria inválida ou duplicada entre dois pares válidos impede calcular a variação entre esses pares, mesmo que uma leitura própria posterior volte a ser válida. Os pares válidos continuam compondo suas amostras, mas a variação exige continuidade verificável. A última leitura inválida do concorrente continua impedindo usar um par anterior como confirmação atual.

Validação: limites entre períodos, contagens independentes por alvo, duplicidades, falhas intermediárias, ausência de leituras, integridade da entrada e interface em 1440/390/320 px.
