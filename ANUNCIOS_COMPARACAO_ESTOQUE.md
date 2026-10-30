# Comparação de estoque e cobertura observada

Complemento do comparador de dois a quatro anúncios da mesma loja. Um bloco recolhível mostra estoque registrado, data/hora da leitura em Brasília, unidades vendidas na janela atual e estoque dividido pela média diária de unidades. Reaproveita os dados do catálogo e do ranking carregados; nenhuma consulta extra, gravação, migração ou chamada externa.

O estoque precisa ser inteiro não negativo e ter leitura válida de até seis horas, sem data futura. Duplicidade de anúncio na origem deixa o dado indisponível. Zero confirmado é preservado. A cobertura exige vendas positivas inteiras da janela verificada; não usa o período anterior, valor bruto, visitas ou média da loja. Usa sete ou trinta dias conforme seleção, truncando duas casas para não superestimar a cobertura.

A leitura atual é separada da comparação histórica. Não comprova saldo Full, disponibilidade de variações, previsão de demanda ou data de ruptura. Dados faltantes ou antigos não viram zero; sem vendas positivas não há cobertura infinita.

Seis testes novos cobrem fontes, limite de frescor, entradas inválidas, zero, duplicidade, escopo, escaping, imutabilidade e bases de 7/30 dias. O teste de navegador cobre estoque válido, antigo e zero, teclado e rolagem em 1440, 390 e 320 px. Integração e publicação dependem da aprovação dos checks desta revisão.
