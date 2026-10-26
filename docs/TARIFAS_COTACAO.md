# Cotação atual de tarifa por anúncio

Fonte técnica consultada em 26/10/2026: [Custos por vender — Mercado Livre Developers](https://developers.mercadolivre.com.br/pt_br/comissao-por-vender).

A documentação descreve `/sites/MLB/listing_prices` como calculador de leitura. Destaca que a tarifa fixa depende de `logistic_type` e `shipping_mode`, além do contexto comercial. O módulo envia esses dois parâmetros, preço principal atual, categoria, modalidade, BRL, quantidade 1 e canal marketplace. Não reproduz taxas fixas ou percentuais em tabelas locais.

Consulta apenas após POST administrativo com CSRF. Verifica `/users/me`, depois propriedade e contexto em `/items/{id}`, então solicita uma cotação. Máximo de três GETs, sem repetição automática ou redirecionamentos, timeout de conexão 3s e leitura 8s por chamada. A renovação da autorização usa o fluxo existente. GET da tela não resolve token nem consulta APIs.

Moeda, conta, anúncio, preço, categoria, modalidade e logística precisam ser verificáveis. Variações, resposta ambígua, campo monetário inválido e falhas deixam o resultado desconhecido. Não presume valores ausentes como zero. Apenas `sale_fee_amount` é apresentado como tarifa de venda estimada; `fixed_fee` é detalhe incluído, sem nova soma. Não converte `financing_add_on_fee` em reais nem usa o campo para inferir parcelas.

Estimativa atual não é cobrança de venda, tarifa histórica, contribuição, frete nem repasse. Não salva cotações como evidências financeiras e não altera anúncios. Não integra Mercado Pago. Os exemplos de testes e capturas são fictícios e isolados de produção.
