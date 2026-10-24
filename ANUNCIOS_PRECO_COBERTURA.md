# Cobertura do histórico próprio de preços e promoções

A seção de preço, promoções e concorrência passa a apresentar dois cards: período encerrado selecionado e período anterior de mesma duração. Cada card informa as datas, leituras com preço confirmado sobre o total carregado, mudanças entre leituras comparáveis e leituras com promoção explicitamente confirmada. Ausência de leituras fica explícita. Esses números não indicam duração do preço, dias em promoção, resultados financeiros ou cobertura contínua.

Mudanças de preço agora exigem timestamp único, confirmação booleana explícita e preço positivo em centavos. Uma duplicidade ou leitura inválida interrompe a sequência; a comparação só recomeça entre novas leituras válidas. O limite continua sendo seis horas, inclusive. O cálculo usa a mesma validação para os eventos consumidos pelo histórico, pela linha do tempo e pela triagem. Não há novas consultas ou alterações nos dados persistidos.

A seção ganhou fundo azul-marinho, cards informativos, contraste nos eventos e filtros e foco visível para navegação por teclado. A descrição do histórico de alterações dos concorrentes respeita a duração selecionada em vez de fixar 14 dias.

Validação: duplicidades em qualquer ordem, confirmação inválida, preços subcentavo, interrupções e retomada, limites de seis horas e de períodos encerrados, contagens independentes, ausência de leituras e interface em 1440/390/320 px.
