# Rentabilidade histórica por anúncio

Continuação do fluxo de custos documentados do PR #235, sobre a base `ac991cd`.

## Resultado

A página administrativa de rentabilidade compara o período selecionado com o período imediatamente anterior de mesma duração. As janelas são encerradas e não se sobrepõem. Continua mostrando contribuição sobre valor bruto dos itens, não lucro líquido ou repasse bancário.

- Diferença de contribuição em reais; diferença de margem em **pontos percentuais**; unidades vendidas nos dois períodos.
- Composição aritmética: diferença do valor bruto menos diferenças de produtos, tarifas, frete do vendedor, impostos, publicidade e ajustes documentados. A soma dos efeitos precisa reconciliar com a diferença de contribuição; inconsistência bloqueia a comparação.
- Participação de cada custo no valor bruto. Aumento de total causado apenas por aumento proporcional de volume não é apresentado como aumento do peso financeiro.
- Pontos de conferência para contribuição negativa, margem menor e até dois componentes com maior aumento de participação. Não representam causa comprovada, projeção de recuperação ou recomendação automática de alteração de preços/campanhas.
- Link para conferir as fontes do período anterior. Não copia custos atuais para períodos anteriores nem presume valores zero.

## Integridade

A comparação exige vendas verificadas e registros completos nos dois períodos. Zero precisa ter referência documental; cobertura, vínculo, quantidade, preço, pagamentos ou fingerprint inválidos bloqueiam o resultado afetado. Uma contribuição atual negativa pode ser exibida como evidência própria mesmo sem comparação anterior, sem preencher o período ausente.

Margens negativas permanecem negativas. Quando o valor bruto de um período é zero, não há divisão por zero, margem comparativa ou comparação de participação. Não se calcula crescimento percentual sobre contribuição zero ou negativa. Mudanças menores que a precisão exibida de 0,01 ponto percentual não criam alertas de zero ponto.

As referências são declaradas pelo administrador e não equivalem a validação automática de documentos. Não há novas chamadas ao marketplace, gastos de IA, importações ou alteração dos dados financeiros existentes.

## Consulta e segurança

As duas janelas compartilham quatro leituras limitadas por loja e datas: pedidos, itens, cobertura e pendências. A função antiga de uma única janela permanece compatível; o fingerprint de um período não muda por a leitura incluir a janela vizinha. Não há consulta por pedido/anúncio em loop.

GET usa uma única transação `REPEATABLE READ, READ ONLY`, para não misturar versões de pedidos, itens e custos enquanto as coletas rodam. O registro de custos mantém o fluxo de POST e CSRF existente. Acesso segue exclusivo do administrador, com validação de loja/anúncio. Colunas, tabelas e registros antigos não são modificados por este lote.

A comparação anterior respeita a janela de 366 dias da interface; se ficar fora dela, não lê pedidos mais antigos nem oferece um atalho inválido.

## Testes

Cobertura para identidade aritmética, efeitos com sinais corretos, margem em pontos percentuais, volumes diferentes, margens negativas, receita zero, custo/fonte ausente, cobertura incompleta, vendas alteradas, janelas inválidas, precisão de exibição, limite histórico, quatro leituras, fingerprint estável e HTML escapado. A integração PostgreSQL renderiza a página com vendas e custos de dois períodos, altera a venda e confirma a supressão da comparação sem apagar versões anteriores. Teste de navegador cobre estados disponível, negativo, ausente e desatualizado em desktop e celular.

A lista literal dos 90 requisitos e as fontes automáticas completas de custos continuam pendentes. Este lote aprofunda a análise histórica com evidência existente, sem declarar esses pontos resolvidos.
