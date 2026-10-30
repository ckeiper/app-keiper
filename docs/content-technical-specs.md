# Ficha técnica da categoria

Fonte oficial conferida em 29/10/2026:
https://developers.mercadolivre.com.br/pt_br/atributos

A documentação diferencia os atributos obrigatórios para publicação, consultados em `/categories/{id}/attributes`, dos campos marcados como required na ficha técnica retornada em `/categories/{id}/technical_specs/input`. A leitura desta ficha, isoladamente, não comprova impedimento de publicação ou perda de exposição do anúncio.

A consulta adicional ocorre somente ao clicar em “Consultar conteúdo e ficha técnica”. Reutiliza a categoria do item cuja conta e propriedade foram verificadas. Faz no máximo um GET adicional, com timeout e sem repetição automática. Limitação ou indisponibilidade da API mantém os dados anteriores e mostra ficha não verificada.

O diagnóstico compara presença no anúncio e em cada variação. Distingue a regra de publicação confirmada, exigência da ficha, contexto condicional e regra de publicação não verificada. Não inventa valores, não considera ausência como erro confirmado, não altera ofertas e não aprova revisões manuais. Campos gerenciados não recebem recomendação de edição direta. Exibe até 100 campos e 100 variações por campo; respostas de regras inválidas, duplicadas ou excessivas ficam não verificadas.
