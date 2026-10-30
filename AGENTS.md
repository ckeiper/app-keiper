# Dashboard Keiper — desenvolvimento

Preserve dados existentes, isolamento por loja, autorização, CSRF e funcionalidades em produção. Mercado Pago e conciliação bancária estão adiados na issue #201. Não invente dados financeiros nem conclusões causais.

## Acompanhamento de Anúncios 2.0

- A tela administrativa `/evolucao-anuncios` mostra somente um gráfico, sem lista ou links externos. Preserve essa preferência do usuário.
- A fonte persistente é `anuncios_progresso.json`. Antes de encerrar um PR funcional de Anúncios, atualize a frente correspondente: implementação, lacuna restante, estado, evidências e data local de conferência.
- Uma frente só pode ficar `concluida` se o escopo descrito estiver implementado, sem lacuna aberta, com código/testes referenciados e checks aprovados. O registro viaja no mesmo PR da implementação; o gráfico de produção só muda quando essa versão é publicada. Falha de deploy mantém o gráfico da versão anterior.
- Acrescente uma medição a `historico` a cada entrega funcional publicada: data de Brasília, resumo, total de frentes e contagens exatas por estado. Não reescreva medições anteriores nem invente medições retroativas. Se várias alterações pertencem à mesma entrega, registre uma única medição desse conjunto. Atualizações puramente editoriais não simulam avanço.
- A lista literal original de 90 ainda não foi recuperada integralmente. Não confunda grupos auditados com requisitos originais, nem invente uma contagem X/90. Mantenha `lista_original_completa=false` e `contagem_das_90=null` enquanto faltar a associação integral. Somente associe `numero_original` com fonte confirmada.
- Registre trabalho real iniciado como `em_andamento`; não mantenha promessa de execução em segundo plano. Parcial precisa explicar a lacuna. Evidência de publicação confirmada pode ser acrescentada na revisão seguinte, sem presumir sucesso de deploy.
- Execute `python scripts/check_anuncios_progress.py` e os testes relevantes. Integre somente após CI aprovado e confirme o commit específico como `live` no Render, além de acesso/logs. Não crie dados de demonstração em produção para testar.
