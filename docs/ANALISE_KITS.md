# Análise de kits por anúncio

Acesso administrativo: diagnóstico do anúncio → Analisar composição de kit (`/anuncios/<loja>/<MLB>/kits`). A ferramenta registra composições declaradas e simulações; não publica ofertas nem altera anúncios, estoque ou custos históricos.

## Escopo

- Proposta de novo kit ou anúncio existente declarado como kit pelo responsável.
- Até cinco componentes e pelo menos duas unidades no total. Kit homogêneo usa uma linha com quantidade maior que um. Componentes podem ser identificações/SKUs manuais ou vinculados a anúncios da mesma loja; vínculo ao próprio anúncio do kit ou repetido é rejeitado.
- Custo unitário e referência obrigatórios por componente; referência geral da composição/custos e data sem futuro. Valores zero precisam ser explicitamente informados; ausência não é zero.
- Preço, tarifa percentual e fixa, impostos, frete, publicidade, embalagem e ajustes informados para uma venda de kit. Percentuais e custos são premissas do administrador, sem cotação ou aprovação oficial do marketplace.
- Custo dos componentes = soma de quantidade × custo unitário. Tarifa = preço × percentual, arredondado a centavos, mais tarifa fixa. Impostos também são arredondados a centavos. Contribuição = preço menos todos os custos. Margem = contribuição/preço. Não é lucro líquido, repasse ou resultado histórico; despesas fixas não são incluídas automaticamente.

## Evidências e limites

A janela de sete ou trinta dias encerrados é fixada no momento da análise (Brasília) e preservada com a versão. As vendas e a disponibilidade são reavaliadas quando a versão é consultada, com as regras já existentes de pedidos pagos, pagamento aprovado, moeda BRL, itens vinculados e cobertura diária. A análise não reconstrói dados ausentes. Valor bruto corresponde somente aos itens do anúncio; não rateia o total de um pedido entre componentes.

As vendas reais do anúncio de referência ficam separadas das vendas dos componentes e da simulação. Em propostas, essas vendas **não validam a demanda da composição nova**. Em anúncios declarados como kits existentes, são vendas verificadas daquele anúncio; a API não certifica a composição declarada. A ferramenta não infere que componentes foram comprados juntos nem estima potencial de vendas.

O limite aritmético de estoque é o mínimo de `estoque geral // quantidade por kit`, somente quando todos os componentes estão vinculados e têm leitura válida de até seis horas. Manual, ausente, inválido ou antigo torna o limite não verificável. Zero confirmado permanece zero. O cálculo não certifica reservas, independência entre estoques, variações ou inventários Full; não é previsão de ruptura.

Próximas conferências destacam contribuição negativa, falta de disponibilidade verificável, ausência de pedidos na janela verificada ou necessidade de validar uma proposta. Não executam decisões comerciais automaticamente.

## Persistência e segurança

Tabela aditiva `listing_kit_analyses`, por loja/anúncio, com composição/premissas em JSON, fontes, datas, autoria e chave de envio. Versões não são sobrescritas. Reenvio idêntico é idempotente; reuso da chave com valores diferentes é rejeitado. Histórico de dez versões por página; acesso a uma versão exige mesma loja e anúncio. Não há exclusão automática de histórico financeiro na remoção de uma conexão, seguindo os demais registros documentais.

Login, autorização administrativa e por loja, CSRF e consultas parametrizadas. A leitura GET usa snapshot somente leitura; emissão não consulta APIs externas. Respostas com dados são privadas, sem cache. Nenhum dado sintético é gravado em produção.

## Validação

Testes de composição, custos/ausência, arredondamento, contribuição negativa, fontes/datas, duplicidades, estoque zero/desconhecido, vendas verificadas versus simulação, idempotência e autorização/CSRF. Integração PostgreSQL cobre gravação de versões, reenvio, preservação e isolamento. Navegador cobre submissão, fonte ausente, interface vazia e ambos os temas em 1440, 390 e 320 px.
