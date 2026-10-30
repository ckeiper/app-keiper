# Mapa de vendas por estado

Acesso: Vendas → Mapa de vendas por estado (`/vendas/<loja>/estados`). Períodos de 7/15/30/60/90 dias e personalizado de até 366 dias, em Brasília. O mapa pode ser colorido por pedidos ou faturamento; a tabela mostra as 27 UFs, pedidos, faturamento bruto, participação no total registrado e ticket. Destinos desconhecidos entram no denominador e aparecem separados, sem inventar vendas ou uma UF.

Fonte comercial: pedidos sincronizados e verificados, pagos, em BRL, com pagamento aprovado. O pedido é contado uma vez mesmo em envio compartilhado. Faturamento corresponde ao total bruto do pedido, sem deduzir reembolsos/devoluções. Data inválida, pagamento inválido, cobertura diária de vendas e proporção de pedidos com destino identificado ficam explícitos. O destino do envio não é apresentado como domicílio ou perfil do comprador.

Coleta: depois da sincronização existente de pedidos, sob a exclusão por loja já utilizada, confirma `/users/me` e consulta `/orders/{id}/shipments?views=destination`, com `X-New-Domain: true` e `x-format-new: true`. Aceita somente envios de compra (`forward`), não cancelados, do vendedor confirmado, país BR e código estadual BR-UF válido. Vários destinos divergentes ficam desconhecidos. A resposta completa não é persistida nem registrada em logs: salva apenas loja/pedido, UF, motivo e datas de tentativa/verificação.

São no máximo nove requisições por execução, até oito pedidos e orçamento de 40 segundos. Erros 401/403/429 interrompem o lote, sem repetição automática na mesma execução. O histórico é preenchido progressivamente em atualizações de Vendas, inclusive as atualizações periódicas existentes; uma visita GET ao mapa não chama a API. Tentativas desconhecidas aguardam um dia; destinos confirmados são reavaliados depois de 30 dias. A fila prioriza os pedidos ainda não tentados. Dados antigos anteriores à sincronização disponível permanecem ausentes. Isso é cobertura dos dados, não uma previsão de vendas.

Referências da API consultadas em 28/10/2026:
- https://developers.mercadolivre.com.br/pt_br/gerenciamento-de-vendas/gerenciamento-de-vendas
- https://developers.mercadolivre.com.br/pt_br/gerenciamento-de-envios

Cartografia ilustrativa: geometria estadual de `codeforgermany/click_that_hood`, `public/data/brazil-states.geojson`, obtida em 28/10/2026, com os 27 códigos de UF da fonte. Limites simplificados em 0,04 grau e transformados em caminhos SVG estáticos; não são utilizados para inferir o estado de uma venda. Sem CDN, mapas externos, geolocalização ou rastreamento no navegador. Fonte: https://github.com/codeforgermany/click_that_hood/blob/main/public/data/brazil-states.geojson . Licença da distribuição em `assets/BRAZIL_STATES_LICENSE.txt`.

Validação: testes unitários de campos, destinos, deduplicação, rate limit e autorização; integração PostgreSQL de persistência/repetição/isolamento; navegador nos temas claro/escuro em 1440/390/320 px. Dados de testes são sintéticos, exclusivamente no ambiente isolado.
