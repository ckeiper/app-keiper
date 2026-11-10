# Full e vendas: cobertura, histórico paginado e inventários por variação

O gráfico diário é o conteúdo principal da tela Full e vendas. Os detalhes de cada dia ficam disponíveis no próprio gráfico. Cobertura, inventários e histórico por variação estão recolhidos em Dados e consultas do período. A navegação por variações preserva anúncio e período. O gráfico e os indicadores de cobertura usam a janela completa carregada.

A seção de inventários usa somente a última observação do anúncio dentro do período selecionado, com data/hora explícitas em Brasília. Não representa saldo atual. O vínculo entre variação e inventário vem dos metadados daquela observação; precisa ser único, Full e válido na janela de frescor de três horas já adotada pelo coletor. Quantidade exige consulta única, sem erro e inteiro não negativo. Zero confirmado é preservado; ausente, falha, duplicidade, metadado antigo/futuro ou vínculo compartilhado não recebe quantidade atribuída. Não usa uma observação anterior para substituir a última inválida.

Inventário compartilhado não é rateado nem duplicado entre variações. Não há soma dos saldos exibidos. Coleta parcial é identificada e não se apresenta como todas as variações. Códigos não viram nomes de cor, tamanho ou SKU por inferência. Até vinte variações por página. Detalhes lidam com registros antigos ou incompletos e escapam os textos exibidos.

Oito testes novos cobrem fontes, limite de frescor, compartilhamentos, falhas, zeros, duplicidades, escopo, paginação, cobertura, escaping e compatibilidade. Navegador verifica estados pronto, parcial, sem coleta, segunda página e muitas variações em 1440, 390 e 320 px, com teclado e rolagem. Publicação condicionada aos checks desta revisão.
