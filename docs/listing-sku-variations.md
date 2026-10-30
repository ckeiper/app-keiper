# SKUs oficiais e variações

Fonte consultada em 30/10/2026: https://developers.mercadolivre.com.br/pt_br/variacoes
A documentação distingue SELLER_SKU (atributo) de seller_custom_field (uso interno). Os campos não são combinados. O include_attributes=all já era enviado pela coleta em lotes.

A sincronização existente passa a salvar somente códigos SELLER_SKU, local de origem (principal ou ID da variação), instante, versão e cobertura estrutural em anuncios.sku_metadata_json. Valida anúncio, site e vendedor; códigos não herdam o valor do anúncio principal. Não modifica sku legado, Full, pedidos ou a oferta no Mercado Livre. Nova coluna JSONB opcional, sem reescrever registros existentes e sem chamadas adicionais. Registros anteriores ficam desconhecidos até a atualização habitual do catálogo. Falha de busca mantém o snapshot anterior com sua data; retorno parcial tem estado explícito.

A página administrativa /anuncios/<cid>/skus-variacoes usa transação somente leitura e escopo da loja em cada consulta. Há acesso por card na tela de SKUs repetidos. O agrupamento exige mais de um anúncio distinto, independentemente do número de variações no mesmo anúncio. Todos os status salvos são incluídos. Filtro exato parametrizado, comparação sensível a caixa e acentos, dez grupos por página, até dez anúncios por grupo e dez origens por anúncio; totais contam o conjunto completo da fonte lida. Não usa histórico de pedidos para inferir SKU e não certifica equivalência, canibalização ou impacto financeiro.

Leitura completa refere-se às listas e aos códigos retornados em uma consulta; não comprova cadastro completo na plataforma. Ausência, erro ou resposta ambígua nunca viram SKU vazio ou erro confirmado. Variações repetidas/inválidas invalidam esse conjunto; código principal verificável é preservado. Atributos compostos ou divergentes ficam não verificáveis. Limites: 1.000 variações, 2.000 atributos por grupo, 200 caracteres por código. Sem dados de compradores. Atualidade sinalizada com janela de seis horas, sem afirmar que o conteúdo permaneceu igual entre coletas.

Validação: test_listing_sku_evidence.py, test_listing_sku_variations.py, test_listing_sku_variations_integration.py e 36 casos de tema/largura/estado no workflow Catalog browser checks. Testes sintéticos isolados, sem dados reais de clientes.
