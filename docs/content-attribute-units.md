# Conferência de unidades dos atributos

Fonte oficial consultada em 29/10/2026:
https://developers.mercadolivre.com.br/pt_br/atributos

A documentação descreve `number_unit` como número com unidade e orienta consultar as unidades disponíveis na API da categoria. A implementação compara somente `value_struct.unit` com os IDs de `allowed_units` retornados na mesma consulta autorizada do anúncio. Não acrescenta chamadas à API.

Os resultados separam unidade compatível com os metadados consultados, divergência para conferência e valor não verificável. Nenhum deles certifica validade integral do anúncio. Texto livre sem estrutura, valores compostos, declaração não aplicável e metadados incompletos não são interpretados como erro. Não converte unidades, não cria aliases, limites positivos ou faixas numéricas e não rejeita valores personalizados de outros tipos de atributo.

A conferência inclui atributos opcionais informados e os dois grupos das variações. Variações inválidas ou duplicadas não recebem conclusões. Limites de 100 resultados e 5.000 entradas ficam explícitos. Campos marcados como gerenciados pelo Mercado Livre não recebem recomendação de edição direta. Nenhum dado do anúncio ou parecer manual é alterado.
