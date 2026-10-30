# Identificadores dos atributos booleanos

Fonte oficial consultada em 29/10/2026:
https://developers.mercadolivre.com.br/pt_br/atributos

A documentação descreve os atributos booleanos com dois valores e orienta consultar o identificador na API da categoria. A conferência usa somente atributos `value_type=boolean`, duas opções com IDs distintos na categoria e o `value_id` explícito do item. Não transforma ausência, texto livre ou valor não aplicável em sim/não. Uma estrutura adicional de valores só é aceita quando contém um único ID coerente com o ID principal.

O diagnóstico distingue ID encontrado na resposta, divergência para conferência e valor não verificável. Não declara erro de publicação nem valida coerência semântica do texto. Atributos de outros tipos não são submetidos a essa regra, preservando seus valores personalizados. Não altera oferta, revisão manual ou dados financeiros.

Inclui os atributos informados no anúncio e nos dois grupos das variações; variações inválidas ou repetidas não recebem conclusões. Campos gerenciados não recebem recomendação de edição direta. Limites de 100 resultados e 5.000 entradas são informados. Reutiliza a consulta de categoria existente, sem novas chamadas à API.
