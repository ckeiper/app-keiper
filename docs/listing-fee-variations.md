# Cotação de tarifas com variações

Fontes oficiais conferidas em 06/11/2026:

- https://developers.mercadolivre.com.br/pt_br/comissao-por-vender
- https://developers.mercadolivre.com.br/pt_br/variacoes

O calculador é somente leitura e recebe preço, categoria, modalidade, moeda, logística, modo de envio, quantidade e canal. Não recebe um ID de variação nesta implementação. A documentação de variações adverte que preços divergentes podem não representar o preço exibido/cobrado; por isso não escolhemos arbitrariamente um dos preços nem tomamos o menor como referência.

## Regra adotada

A cotação existente continua exigindo POST explícito com CSRF, administrador e acesso ao anúncio da loja, confirmação autenticada de `/users/me` e propriedade em `/items/{id}`. Abrir a tela não consulta APIs. A rotina de cotação faz no máximo três GETs, com timeout e redirects bloqueados, sem enviar alterações ao anúncio. Obtenção e eventual renovação do token permanecem no fluxo existente de conexão.

Após confirmar a conta e o item, `uniform_price` exige `variations` como lista, no máximo 250 entradas (limite local desta implementação), objetos com IDs positivos verificáveis e únicos e preço positivo válido em cada entrada. Todos os preços devem ser exatamente iguais ao preço principal positivo do anúncio, sem arredondamento de inconsistências. Ausência, divergência, duplicação ou formato inválido interrompe o fluxo antes de `/sites/MLB/listing_prices`. Não há fallback para preço principal, escolha de variação ou preço enviado pelo formulário. A base é relida em cada consulta.

O pedido ao calculador permanece o mesmo, com quantidade 1 e canal marketplace. Não amplia a cobertura para User Products, preços promocionais, condições específicas por comprador, preços divergentes ou outros contextos não verificáveis. O resultado identifica quantas variações tiveram o preço comum confirmado na leitura. É um retrato das respostas; não bloqueia mudanças simultâneas feitas fora do sistema.

O total estimado e o detalhe fixo já incluído continuam separados, sem soma duplicada. Um detalhe ausente é desconhecido; total explicitamente zero não vira ausência. A cotação não é cobrança histórica, custo documentado, lucro líquido ou promessa do preço pago. Não grava resultados, não altera os anúncios e não modifica os simuladores de premissas manuais.

## Validação

Testes de preços uniformes (incluindo o limite de 250), divergentes, ausentes, IDs duplicados, estrutura malformada e cotação zero. O teste de rota confirma CSRF/autorização existentes, releitura por POST e que preço/variação forjados no formulário não viram parâmetros do calculador. Prévia e browser check cobrem 48 combinações de estado, tema e largura, com fixtures sintéticas e sem alterações em produção. Consultas reais autenticadas não foram exercitadas como teste.
