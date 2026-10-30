# Visitas e pedidos por visita na comparação de anúncios

O comparador de dois a quatro anúncios acrescenta visitas registradas, cobertura em dias e pedidos pagos por visita nos mesmos períodos encerrados de sete ou trinta dias. As vendas continuam disponíveis independentemente das lacunas de visitas.

As visitas usam uma única consulta local, restrita à loja, aos anúncios selecionados e às datas exatas, dentro do snapshot somente leitura do ranking. A consulta só ocorre com seleção válida e ranking verificado; não ocorre na seleção vazia, na base pendente ou no modo compacto de prioridades. São no máximo quatro anúncios e sessenta datas esperadas.

Totais exigem todas as datas válidas do respectivo período. Duplicidades, valores negativos, fracionários, booleanos ou inválidos impedem completar a cobertura; não são somados como total parcial. Zero confirmado permanece zero. Pedidos pagos por visita exige os dois períodos completos e denominadores positivos e não é a conversão oficial do Mercado Livre. Não distribui Ads, margem ou outros dados por suposição.

Validação: consulta única e escopo, janelas fechadas, taxa exata, lacunas/duplicidades/valores inválidos, zero, dados de outra loja, seleção inválida, integração sem leituras na base pendente e interface em 1440/390/320 px.
