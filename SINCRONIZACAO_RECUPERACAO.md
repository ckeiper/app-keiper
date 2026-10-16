# Recuperação da sincronização

O diagnóstico em produção identificou que o erro geral `tuple index out of range`
era de 13/10/2026, anterior às atualizações de 16/10. Não há evidência de que
essa exceção específica tenha voltado a ocorrer na versão atual. Ela permanecia
na tabela e na tela sem evidência de resolução por categoria.

O código atual também chamava `puxar_ads_dia`, função inexistente, depois de
`puxar_ads`, que já coleta métricas diárias. Essa chamada foi removida. O job
horário executava todas as lojas em sequência sem isolamento; uma exceção antes
do final interrompia as lojas seguintes. Agora ele usa a fila existente, e cada
etapa registra a própria falha sem interromper vendas ou as etapas seguintes.
O botão geral de atualização também enfileira a coleta e retorna imediatamente.

A coluna aditiva `erros.resolvido_em` preserva o último erro de cada categoria.
Sucesso explicitamente confirmado marca somente erros anteriores ao início da
coleta. Uma nova falha reabre o aviso; sucesso antigo não resolve falha concorrente.
Retorno ausente ou falso não é evidência de sucesso. A exceção geral antiga pode
ser resolvida quando o fluxo passa a completar suas etapas isoladas, enquanto
erros específicos continuam pendentes. O diagnóstico mostra loja e situação;
Anúncios mostra somente avisos ainda pendentes.

A Visão Geral mantém sua regra mais conservadora: a data do erro ainda é
comparada ao sucesso em todos os dias selecionados, mesmo após resolução da
categoria. A cobertura nunca é criada pelo simples término de uma atualização.
O histórico de erros é o último por loja/categoria, como no esquema anterior;
não se promete um registro de todas as ocorrências.

Permissões indisponíveis em Product Ads, visitas sem coletor habilitado e dias
sem cobertura continuam explícitos. Nenhum valor é inventado e nenhum erro é
apagado em massa. A carga histórica continua gradual, até 30 dias por execução;
uma janela que falhar, exceder o limite de paginação ou retornar rate limit não
é marcada como completa. Não foram alterados endpoints nem permissões do ML.

Testes novos cobrem isolamento de etapas/lojas, falha no próprio registro de
erro, coletor Ads chamado uma vez, retomada sem apagar falhas concorrentes,
diagnóstico com histórico e autorização da atualização em segundo plano.
