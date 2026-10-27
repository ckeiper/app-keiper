# Conferência de conteúdo atual

Consulta administrativa sob demanda, vinculada à loja e ao anúncio. Verifica `/users/me` e a propriedade em `/items/{id}` antes de ler `/items/{id}/description` e, somente com categoria MLB verificável, `/categories/{category_id}/attributes`. Até quatro GETs e uma consulta POST ao recurso oficial `/categories/{category_id}/attributes/conditional`; timeout de conexão 3s e leitura 8s por chamada, sem redirecionamentos nem repetição automática. A consulta condicional usa os dados do anúncio retornado e a descrição, somente quando os campos básicos estão disponíveis. Não publica ou altera o anúncio. A autorização usa o fluxo existente de renovação. Abrir a tela não resolve token nem consulta a API.

Mostra título, quantidade de fotos retornadas, atributos principais e descrição em texto simples. Resposta ausente, inválida, não autorizada ou indisponível permanece desconhecida; HTTP 404 da descrição não é convertido em descrição vazia. Falhas na descrição ou categoria preservam as leituras já verificadas. Não lê imagens remotas ou clips nem julga qualidade.

Conferência de presença: regras `required` e `conditional_required` da categoria são apresentadas separadamente. Procura valor no anúncio principal ou em todas as variações, considerando `attributes` e `attribute_combinations`. Os atributos devolvidos pelo recurso condicional são identificados como obrigatórios nessa consulta; os demais são exibidos sem certificar que a ficha está completa. Falhas e dados básicos ausentes deixam a aplicabilidade como não verificada. Não valida os valores, regras da ficha técnica ou aprovação do anúncio. Identificadores repetidos, grupos ausentes, valores complexos não verificados e `value_id=-1` não comprovam preenchimento. Só mostra campo a revisar quando os grupos relevantes foram retornados e não têm valor identificado. Categoria desconhecida não significa ausência de requisitos. Até 100 requisitos exibidos, com total retornado; até 2.000 definições e 1.000 variações para a comparação.

Limites explícitos: título até 1.000 caracteres; descrição até 200.000, com exibição dos primeiros 12.000; até 50 atributos exibidos com total retornado. Texto e nomes retornados são escapados. Valores complexos de atributos sem `value_name` não são presumidos vazios. Não salva a leitura, não altera a oferta e não modifica pareceres. O administrador pode registrar evidências datadas no checklist existente. Sem migração ou integração Mercado Pago.

Documentação oficial consultada em 26/10/2026:
- [Publicar produtos](https://developers.mercadolivre.com.br/pt_br/publicacao-de-produtos)
- [Descrição de produtos](https://developers.mercadolivre.com.br/produto-receba-notificacoes/descricao-de-produtos)
- [Atributos](https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br/atributos)
- [Validações](https://developers.mercadolivre.com.br/pt_br/guia-para-produtos/validacoes)

Referências de atributos/validações verificadas por trechos indexados oficiais; acesso direto retornou HTTP 403 nesta conferência. A consulta condicional usa o recurso oficial documentado e não reproduz validação de publicação.

Exemplos e capturas usam somente dados fictícios locais.
