# KEVIA — evidências financeiras documentadas

Continuação sobre `8e738e4` (#237). O bloco financeiro usa regras locais sobre custos registrados e vendas verificadas. Não treina um modelo, não envia custos à interpretação paga e não altera campanhas ou preços.

## Análise diária

A rotina diária existente da KEVIA passa a salvar um retrato financeiro privado junto ao resultado da loja. Reutiliza a mesma janela de sete dias encerrados e os sete anteriores. Não muda o horário, a fila, a trava por processo ou a regra de uma execução por loja/dia.

Antes de concluir, verifica os registros mais recentes dos dois períodos, as fontes declaradas e a correspondência com valor bruto, unidades e fingerprint das vendas. Registros ausentes, não verificáveis ou modificados não são convertidos em zero. Margens negativas permanecem negativas; a comparação de margem exige denominadores válidos nos dois períodos.

O retrato informa:

- Quantos anúncios têm custos atuais documentados compatíveis com as vendas.
- Quantos têm contribuição documentada negativa e a soma **somente dessas contribuições negativas**, sem compensar contribuições positivas. Não é lucro líquido ou resultado total da loja.
- Quantos permitem comparação de margem e quantos tiveram queda em pontos percentuais.
- Cobertura: entre os anúncios com vendas pagas verificadas, quantos tinham custos compatíveis. Não extrapola um subconjunto para toda a operação.
- Até três anúncios para conferir, ordenados primeiro por contribuição negativa documentada e depois por queda de margem; não atribui causalidade nem estima recuperação monetária.

A leitura requer uma consulta quando não há registros financeiros; com registros, são até cinco consultas restritas à loja e às datas. Usa transação `REPEATABLE READ, READ ONLY` e limite de 10 segundos por consulta. Falha financeira é salva como indisponibilidade e não apaga a análise pública de vendas/Ads.

## Retrato histórico, não tempo real

A página mostra data da conferência, período e limites da amostra. Alterações posteriores não estão incluídas; o link **Revalidar na rentabilidade do anúncio** abre o cálculo que confere novamente as fontes atuais. Custos cadastrados após uma análise entram na próxima execução diária.

Resultados antigos não são reescritos, e execuções já concluídas no dia não são apagadas ou reabertas para retroagir custos. Enquanto não existir uma execução desta versão, o administrador vê o estado **Aguardando a primeira execução financeira desta versão**, sem valores zero fictícios.

## Privacidade e gastos

O campo `financial` é privado. A rota da loja filtra esse campo de todos os resultados e do histórico para clientes; o renderizador também exige opção administrativa explícita. A central permanece protegida pelo acesso administrativo.

Os sinais financeiros ficam separados da lista pública de recomendações. O adaptador pago continua recebendo apenas as evidências públicas que já recebia: nenhuma referência documental, ID de anúncio ou soma financeira privada entra no payload. Não há chamada adicional ao provedor, mudança de orçamento, preço presumido ou chave nova.

## Central, histórico e acompanhamento

A central administrativa pode priorizar lojas com sinais documentados, identificando que a contagem se limita aos registros conferidos. O histórico administrativo identifica o estado financeiro de cada execução; clientes continuam recebendo apenas o histórico público.

O acompanhamento manual existente aceita os sinais financeiros salvos. Seus códigos incluem anúncio e período, para que um status resolvido de outro dia não seja apresentado como resolução de uma nova ocorrência. O status é declarado pelo administrador, não uma comprovação automática de melhora.

A identidade visível **KEVIA** também é aplicada ao título gráfico que antes ainda montava “KYRA” em fragmentos de HTML. Testes verificam o texto renderizado, tamanho e contraste do título, preservando URLs, tabelas e identificadores internos.

## Validação

Cobertura unitária para valores negativos, queda de margem com contribuição positiva, ausência de fontes, versão de custos invalidada, receita zero, cobertura parcial, escopo por loja/período, máximo de três itens, privacidade do renderizador/histórico/central, falha isolada e exclusão do payload pago.

Integração PostgreSQL executa a rotina real, confirma persistência e execução única, renderiza o bloco administrativo, registra revisão com CSRF e verifica que cliente não recebe custos, valores ou códigos financeiros nem pode revisar. GET usa somente o retrato salvo, sem recalcular ou chamar APIs.

QA de navegador cobre dados disponíveis, cobertura parcial, custos ausentes, falha, primeira execução pendente e cliente, nos tamanhos desktop/celular, com navegação por teclado e marca renderizada KEVIA.
