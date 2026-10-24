# Revisão da margem documentada

Na página administrativa de rentabilidade por anúncio, plano determinístico limitado ao anúncio e período selecionados. Reutiliza `result_for`, com a mesma validação de fingerprint, valor bruto, unidades e fontes. Sem custos válidos ou com vendas alteradas, não apresenta déficit nem ranking.

Apresenta até três maiores componentes positivos, em ordem de valor total (desempate por chave), participação no valor bruto e ação específica de conferência. Valores zero não entram no ranking; todos zero são explicitados. Valor bruto zero não recebe percentual.

Déficit histórico = max(custos documentados − valor bruto, 0), em Decimal. Não é meta, promessa de economia, lucro líquido ou projeção de preço. Resultado não negativo também não comprova lucro. Nenhuma fonte automática, rateio, consulta adicional, chamada paga, migração ou escrita adicionada. O registro de nova versão continua no fluxo existente com CSRF e confirmação.

Testes: ausência de fontes, alteração das vendas, déficit exato, empates, todos custos zero, receita zero, escape e ações de todos os componentes; verificações de navegador para estados pronto, ausente, alterado e contribuição negativa, desktop/celular.
