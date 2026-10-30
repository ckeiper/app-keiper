# Conferência aritmética do relatório por vendas

Validação de fonte em 24/10/2026: relatório fornecido pelo usuário com aba DAILY_CONCILIATION e 32 colunas. O arquivo mistura tipos de movimentos e contém tarifas negativas. Nenhum dado identificável, valor ou linha real foi copiado para fixtures ou repositório.

O resumo novo confere, linha a linha, Valor bruto (=) menos Valor total de tarifas (desconto já aplicado) contra Valor líquido após tarifas. Tarifas pós-pagas não são subtraídas de novo. Sinais negativos são preservados, valores exigem precisão de centavos e diferença de R$ 0,01 já é sinalizada. Diferenças opostas não se anulam na contagem; sua soma é explicitamente algébrica.

A coluna de bruto deve existir uma única vez; arquivos antigos sem essa coluna mantêm o diagnóstico de frete, com financeiro indisponível. Linhas com campos ausentes, fórmulas, valores não finitos, booleanos ou precisão inválida ficam fora dos totais, com contagem explícita. Repetições permanecem, sem deduplicação presumida. Os três totais usam a mesma base de linhas válidas. Nenhuma linha válida não vira total zero na tela.

Aplicado ao relatório real: 7.817 linhas com os três valores válidos, 10 excluídas por validação financeira, nenhuma diferença na base comparável. Não afirmar que todas as linhas foram conciliadas. A triagem numérica inicial cobria mais linhas e não aplicava os mesmos critérios de centavos do importador.

Não é conciliação bancária, faturamento de vendas, saldo, lucro ou confirmação de repasse. Não prova cobrança indevida. Nenhum valor é transferido automaticamente para custos de anúncios. Resumo financeiro acompanha o JSON do relatório nas novas importações; versões antigas não são reprocessadas nem substituídas. Sem migração, chamada externa ou escrita adicional. O arquivo original não foi alterado.

## Grupos e linhas para revisão

Novas importações separam os tipos conhecidos (normalização de caixa, acentos e espaços): Venda → Vendas; Anúncios MClicks → Publicidade; Armazenamento Full e Coleta Full → Serviços Full; Envio → Envios; Cobrança de DIFAL → Tributos; Pagamento de faturas → Pagamento de faturas. Qualquer outro tipo, vazio ou desconhecido, fica em Outros / tipo não identificado. Não há inferência de ajustes ou estornos pelo sinal do valor. A lista fixa limita a quantidade de grupos e impede persistir texto arbitrário do arquivo.

Cada grupo tem linhas válidas, inválidas, diferenças e os mesmos três totais assinados. A soma dos grupos reconcilia com a base global; grupo sem linhas válidas exibe valores indisponíveis. A tabela tem rolagem horizontal no celular. O líquido do grupo Vendas continua sendo líquido de lançamentos desse tipo, não margem de anúncios nem repasse bancário confirmado.

As primeiras 20 linhas inválidas ou com diferença recebem referência da linha Excel, grupo e motivo, sem valor bruto, ID de operação ou outro conteúdo original. As linhas incluem cabeçalhos e espaços vazios. O histórico antigo não é reprocessado; grupos/referências aparecem somente quando disponíveis na nova análise.

Conferência no arquivo real: grupos fecham exatamente com os contadores e totais globais em Decimal; 10 linhas de vendas fora dos critérios e 10 referências para revisão. Sem alteração da fonte ou importação em produção. Oito testes novos cobrem mapeamento, reconciliação, indisponibilidade, entradas desconhecidas, legado, parser, limite de referências e linhas vazias.
