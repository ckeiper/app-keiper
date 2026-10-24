# Base observada dos alertas de estoque

Os cartões de prioridade e seus planos passam a informar a quantidade registrada, a média de unidades vendidas por dia e a cobertura estimada quando inferior a sete dias. Quando a fonte fornece a base verificável, também informam o total de unidades e os dias encerrados usados no cálculo. A estimativa descreve o ritmo passado; não prevê demanda, data de ruptura, receita recuperável ou saldo no Full.

Os sinais continuam exigindo leitura recente do catálogo (até seis horas), quantidade inteira não negativa e período de vendas verificado. Datas fracionárias, não positivas, futuras ou inválidas, quantidades booleanas e unidades vendidas fracionárias não são aceitas. Dados recusados permanecem desconhecidos, nunca viram estoque zero. O limite de sete dias continua exclusivo; a exibição trunca duas casas para não mostrar sete dias em um alerta inferior a sete.

Sem novas consultas, chamadas externas, alterações de estoque ou mudança na ordenação por perda bruta verificada. Cobertura curta e estoque zero continuam independentes da verificação de saldo no Full.
