# Ficha técnica da categoria

Fonte oficial conferida em 29/10/2026:
https://developers.mercadolivre.com.br/pt_br/atributos

A documentação diferencia os atributos obrigatórios para publicação, consultados em `/categories/{id}/attributes`, dos campos marcados como required na ficha técnica retornada em `/categories/{id}/technical_specs/input`. A leitura desta ficha, isoladamente, não comprova impedimento de publicação ou perda de exposição do anúncio.

A consulta adicional ocorre somente ao clicar em “Consultar conteúdo e ficha técnica”. Reutiliza a categoria do item cuja conta e propriedade foram verificadas. Faz no máximo um GET adicional, com timeout e sem repetição automática. Limitação ou indisponibilidade da API mantém os dados anteriores e mostra ficha não verificada.

O diagnóstico compara presença no anúncio e em cada variação. Distingue a regra de publicação confirmada, exigência da ficha, contexto condicional e regra de publicação não verificada. Não inventa valores, não considera ausência como erro confirmado, não altera ofertas e não aprova revisões manuais. Campos gerenciados não recebem recomendação de edição direta. Exibe 50 campos por página e detalhes de até 100 variações por campo; respostas de regras inválidas, duplicadas ou excessivas ficam não verificadas.


## Inventário completo da resposta — 31/10/2026

A conferência agora avalia todos os campos retornados em `technical_specs/input`, inclusive sem `required`. Não afirma que esse recurso enumera todos os atributos possíveis no Mercado Livre. Campos sem a marca são chamados complementares nesta ficha; regras de publicação e condicionais continuam independentes. Respostas vazias não certificam ficha completa. Campos gerenciados, N/A e informação desconhecida preservam a cautela anterior.

São mantidos todos os resultados aceitos pelo limite existente de 5.000 definições, com contagens integrais e navegação/filtros locais em páginas de 50. Sem JavaScript, os primeiros 50 ficam disponíveis com aviso explícito. Todos os campos e até 1.000 variações são conferidos; o detalhe visual mostra até as primeiras 100 variações por campo, com limite declarado. O estado agregado considera também as demais variações. Atributos são indexados uma vez por grupo, e os estados das variações são compactados para limitar memória/payload. Não acrescenta requisições, retries, sincronizações ou escritas no anúncio.

Ajuda contextual substitui o parágrafo de limites, disponível por mouse, foco e toque. Busca, filtros, paginação e mensagens usam `textContent`; o JSON embutido escapa caracteres que poderiam encerrar o elemento script. Testes verificam ausência de execução de conteúdo recebido. O formulário original e seus controles de autorização/CSRF permanecem.

A documentação oficial acima foi reconferida pelo índice de busca em 31/10/2026; o acesso direto devolveu HTTP 403. A distinção de `required` permanece a documentada, sem criar novas exigências ou concluir perda de exposição. Uso autenticado com anúncio real não exercitado nesta entrega.

Valores somente em value_struct, sem ID/texto simples, são não verificáveis pelo leitor de presença; não são ausência confirmada. A conferência específica de unidades continua separada.
