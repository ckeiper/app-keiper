# Anúncios 2.0 — distância histórica entre preços

Escolha aprovada: histórico de competitividade com diagnóstico das perdas. Esta etapa acrescenta evidência temporal de distância entre preços, sem afirmar perda de vendas ou causalidade. Usa somente observações já coletadas e vínculos informados pelo usuário, no diagnóstico individual, junto ao histórico existente de preço/promoções e concorrência.

Para cada leitura de concorrente do período encerrado, utiliza a última observação própria anterior ou simultânea, no máximo seis horas antes. Não usa preço futuro nem o snapshot atual para reconstruir o passado. A leitura própria deve ser confirmada, preços positivos/finitos e sem ambiguidade por timestamp. Duplicidade, falha ou preço inválido interrompe a comparação. Não retrocede para um preço próprio antigo após falha mais recente. São processados somente IDs presentes nos vínculos carregados daquele anúncio; sem consultas adicionais ou escrita.

Distância em reais = próprio − concorrente. Distância percentual = diferença ÷ concorrente. Variação em pontos percentuais exige dois pares consecutivos separados por até seis horas, sem leitura inválida entre eles. A última observação atual sem par válido torna o contexto indisponível; não reapresenta par antigo como atual. Contagens explicitam pares válidos e leituras do período, não dias de cobertura nem estabilidade. Mesmos limites de 20 vínculos e 300 observações do carregador existente, com aviso quando limitados.

Tabela mostra timestamps próprios e concorrentes em Brasília, dois preços, distância e variação. Não é posição de mercado, média do período ou preço atual. Vínculo não comprova equivalência de produto, quantidade, variação, frete, prazo ou cupons. A leitura orienta revisão dessas condições; não recomenda reduzir preço automaticamente. Não altera filtros/histórico anteriores, coleta, publicação, margem ou anúncios.

Oito testes novos: pareamento cronológico exato, leitura futura/desatualizada, falha própria sem fallback, erro/duplicidade/preço ausente do concorrente, ruptura por erro intermediário, exclusão de hoje/vínculos estrangeiros, duplicidade própria, escape e ressalvas. Navegador cobre tabela em 1440/390/320 px. Nenhuma série real de produção foi escrita ou fabricada.

As 90 melhorias literais continuam sem documento integral recuperado. Esta entrega corresponde a uma escolha visível do usuário; não atribui número ou percentual de conclusão por suposição. Mercado Pago adiado na #201.
