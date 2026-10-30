# Calendário informado e comparação de promoções

Acesso administrativo no diagnóstico: **Comparar períodos de promoção**, rota `/anuncios/<loja>/<MLB>/promocoes-resultados`.

## Fonte e preservação

As consultas existentes a `/seller-promotions/items/<MLB>?app_version=v2` passam a preservar leituras separadas, sem aumentar as chamadas à API. O histórico começa nas novas sincronizações; não é reconstruído a partir da oferta atual nem das datas de detecção de mudanças de preço. Salva somente identificadores, tipo, status do item, datas, preços, variação e condições selecionadas (offer_id, percentuais de coparticipação, top_deal_price e sub_type). Não grava o payload completo nem mensagens de erro com credenciais.

Falha de consulta cria leitura não confirmada com a data da tentativa e sem reapresentar a consulta antiga como ativa. Anúncio encerrado/em análise fica não aplicável. Respostas inválidas ou com mais de 200 ofertas não são apresentadas como ausência de promoções. Duplicatas idênticas no mesmo instante são idempotentes. Preserva mudanças de condições/estado e uma leitura representativa por dia de Brasília quando as condições permanecem iguais, evitando crescimento por cópias idênticas a cada atualização. Não é um registro de cada requisição nem comprovação de continuidade entre leituras. Histórico paginado, com dez consultas por página e seleção por identificador restrita ao anúncio e à loja.

## Distinções oficiais

A consulta por item informa status de participação e preço naquele momento; não certifica todas as condições gerais da campanha. A campanha tem seu próprio calendário. Na documentação de campanhas do vendedor, `finished` para a **campanha** significa finalizada; para o **item**, pode significar removido. Portanto o painel não transforma item removido em participação integral até o fim.

Referências oficiais conferidas em 29/10/2026:
- https://developers.mercadolivre.com.br/pt_br/gerenciar-ofertas
- https://developers.mercadolivre.com.br/pt_br/campanhas-do-vendedor

## Comparação

Somente uma leitura de participação ativa, sem variação e de tipo validado permite tentar comparar o calendário. Datas precisam conter fuso explícito; horário local sem offset não é convertido por suposição. Cupons, ofertas por quantidade/pagamento e tipos desconhecidos não recebem uma regra genérica de atribuição. Promoções curtas podem não comportar a comparação diária de 7/30 dias; não são ampliadas artificialmente.

Usa os primeiros sete ou trinta dias **inteiros** dentro do intervalo retornado, todos encerrados em Brasília. Um dia só entra se sua meia-noite inicial e a meia-noite seguinte estiverem dentro do intervalo. O período anterior termina no dia anterior à data local de início da oferta; o dia parcialmente promocional nunca entra como dia sem promoção. Os dois períodos têm o mesmo tamanho. Não usa a data de leitura como início, não inclui hoje/futuro e limita a referência aos últimos 366 dias.

Vendas são as de todo o anúncio nas janelas: pedidos pagos/aprovados, moeda BRL, vínculo dos itens e cobertura diária segundo os classificadores já publicados. Não são vendas atribuídas exclusivamente à promoção. Visitas têm cobertura independente. Ausência não vira zero.

Contribuição financeira só aparece com registros documentados do anúncio e das datas exatas dos dois períodos, cujos fingerprints ainda correspondam às vendas. Links direcionam ao período/registro corretos para conferência. Sem custos, contribuição fica indisponível. A comparação inclui diferenças de volume, mix e outras ofertas; não mede ganho causal da promoção.

## Lacunas preservadas

O calendário retornado e uma leitura ativa **não comprovam participação contínua nem preço/condições constantes** entre coletas. Não se reconstrói vigência passada quando a API não a confirma. A coleta automática integral de custos também não foi implementada por esta entrega. Por isso a frente `promocoes-resultados` permanece parcial, com avanço funcional documentado e sem aumento artificial de concluídas.

## Segurança e validação

Migração aditiva, autorização administrativa por loja/anúncio, GET em transação REPEATABLE READ/READ ONLY, SQL parametrizado e respostas privadas sem cache. Nenhuma adesão, alteração ou cancelamento de promoção é enviado. Testes cobrem falhas e remoções, datas sem fuso, dias parciais/futuros, variações, condição não suportada, deduplicação, histórico e isolamento PostgreSQL, fontes de custos e os temas claro/escuro em 1440/390/320 px.
