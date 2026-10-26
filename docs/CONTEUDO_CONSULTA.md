# Conferência de conteúdo atual

Consulta administrativa sob demanda, vinculada à loja e ao anúncio. Verifica `/users/me` e a propriedade em `/items/{id}` antes de ler `/items/{id}/description`. No máximo três GETs, timeout de conexão 3s e leitura 8s por chamada, sem redirecionamentos nem repetição automática. A autorização usa o fluxo existente de renovação. Abrir a tela não resolve token nem consulta a API.

Mostra título, quantidade de fotos retornadas, atributos principais e descrição em texto simples. Resposta ausente, inválida, não autorizada ou indisponível permanece desconhecida; HTTP 404 da descrição não é convertido em descrição vazia. Se apenas a descrição falhar, os campos já verificados do anúncio continuam disponíveis. Variações são contadas sem certificar seus atributos. Não lê imagens remotas ou clips, não julga qualidade nem verifica atributos obrigatórios da categoria.

Limites explícitos: título até 1.000 caracteres; descrição até 200.000, com exibição dos primeiros 12.000; até 50 atributos exibidos com total retornado. Texto e nomes retornados são escapados. Valores complexos de atributos sem `value_name` não são presumidos vazios. Não salva a leitura, não altera a oferta e não modifica pareceres. O administrador pode registrar evidências datadas no checklist existente. Sem migração ou integração Mercado Pago.

Documentação oficial consultada em 26/10/2026:
- [Publicar produtos](https://developers.mercadolivre.com.br/pt_br/publicacao-de-produtos)
- [Descrição de produtos](https://developers.mercadolivre.com.br/produto-receba-notificacoes/descricao-de-produtos)

Exemplos e capturas usam somente dados fictícios locais.
