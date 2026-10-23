# IA Keiper · primeira etapa

Regras determinísticas sobre dados já persistidos, sem coleta extra no Mercado Livre e sem alteração de campanhas. Compara sete dias encerrados com os sete anteriores (Brasília). Critérios v1: queda de receita ≥20% e R$100; pedidos ≥20% e cinco pedidos; ROAS ≥25% de queda com gasto ≥R$50 nos dois períodos; gasto ≥R$50 sem receita atribuída; TACOS +5 pontos com gasto ≥R$50. Receita de Ads tem janela de atribuição; evidências não estabelecem causalidade.

A classificação de vendas, cobertura, integridade e atualização reutiliza `overview.load_overview`. Ads exige 14 registros válidos, observados depois do encerramento de cada dia e atualizados há no máximo sete dias. Problemas de dados têm prioridade; regras que dependem dos dados inválidos são suprimidas. Retorna até três recomendações, incluindo qualidade, evidências e períodos. Nenhum alerta é inventado para completar três itens.

## Operação

- Página `/ia-keiper/<loja>`, acessível pelo resumo e menu da loja. Mesma autorização por loja do painel. GET só lê resultados; nunca dispara análise ou API.
- Agendador existente verifica a fila a cada minuto, a partir das 08h de Brasília; processa uma loja ativa por tick. Restrição única loja/dia e trava PostgreSQL entre processos. Não depende de tráfego HTTP enquanto o processo estiver vivo.
- `KEIPER_AI_DAILY_ENABLED=false` interrompe novas análises. Padrão `true` para regras locais quando a versão for implantada.
- Execução é persistida antes de processar; falhas ficam visíveis. Sem repetição automática no mesmo dia, inclusive após crash. Próximo dia ativo faz nova análise; não há backfill de dias em que o serviço ficou desligado. Estado `rules_ready` preserva resultados se houver falha posterior.
- Reutiliza PostgreSQL e APScheduler; nenhuma nova dependência, worker ou plano Render. No Free, suspensão do serviço pode atrasar/impedir a rotina. Não garantir horário exato ou SLA. Acompanhar duração/carga antes de separar worker.

## API paga (desabilitada por padrão)

Não configurar nem habilitar em produção sem confirmação humana de gasto. Exige simultaneamente:

```
KEIPER_AI_PAID_ENABLED=true
KEIPER_AI_PAID_CONFIRMATION=APPROVED
OPENAI_API_KEY=<segredo no Render, nunca no Git>
KEIPER_AI_MODEL=<modelo aprovado>
KEIPER_AI_INPUT_USD_PER_MILLION=<tarifa vigente positiva>
KEIPER_AI_OUTPUT_USD_PER_MILLION=<tarifa vigente positiva>
KEIPER_AI_USD_BRL=<câmbio conservador com margem de impostos>
KEIPER_AI_MONTHLY_BRL=50
```

Tarifas/câmbio inválidos bloqueiam a API. Modelo e preços não são presumidos. Atualizar as tarifas e a conversão antes de habilitar e sempre que mudarem. Usar projeto/chave exclusivos e limites do provedor como defesa adicional.

Uma chamada opcional por análise, apenas se houver anomalia relevante, com agregados e textos fixos de regras. Não envia nome de loja, dados pessoais, tokens ML, IDs de pedidos ou campanhas. Usa Responses API, `store=false`, sem ferramentas e limite de 500 tokens de saída. Saída é texto escapado, identificada como interpretação para revisão humana; não substitui regras/evidências. Referência: https://developers.openai.com/api/docs/guides/text

Orçamento **global para todas as lojas**, por mês de Brasília. Reserva conservadora (bytes de entrada + margem de 1.024 tokens e saída máxima) sob trava transacional; registra modelo, tarifas, câmbio, tokens e compromisso em reais. Reserva é confirmada antes de chamar o provedor. Timeout, crash ou uso não informado retêm a reserva, sem retry. Respostas incompletas não são exibidas, mas o uso informado é registrado. Excesso inesperado da reserva registra uso e bloqueia o restante do mês. Excluir loja não apaga o histórico financeiro.

O painel do administrador mostra total comprometido (inclui reservas incertas), alerta em 80% e bloqueio no limite ou quando a próxima reserva não cabe. Resultado da loja registra bloqueio. Clientes não veem o gasto global de outras lojas. Limite inválido bloqueia novas chamadas. Mês seguinte abre orçamento novo; reservas antigas permanecem no mês original para auditoria.

R$50 é limite configurado de controle estimado, **não promessa de fatura fixa ou teto absoluto do provedor**. Tarifas, câmbio, impostos e chamadas fora desta aplicação podem divergir. Conferir o extrato real e reconciliar reservas incertas administrativamente; não liberá-las sem verificar a cobrança. Não há botão web para habilitar API ou liberar orçamento.

## Render verificado em 23/10/2026

`app-keiper`: web Free, uma instância, `gunicorn main:app`, auto deploy por commit em main, previews desligados. `keiper-db`: Free PostgreSQL 18, expira em 05/11/2026. A amostra disponível de memória (~139 MB de 537 MB) não é um teste de carga; CPU não retornou amostras. Não foi feita alteração de plano ou deploy.

Avaliar primeiro continuidade do banco (upgrade e backup) e serviço sempre ativo. Página oficial anuncia web 0,5 CPU / 512 MB por US$7/mês, cobrado separadamente do banco e da API: https://render.com/pricing . Revalidar preço/plano do banco no Dashboard antes de aprovar; não inferir custo total a partir do preço do app. O upgrade não habilita a API paga.

## Validação e publicação

`python -m unittest -v` roda regras, orçamento e testes PostgreSQL/Flask (estes exigem `KEIPER_TEST_DATABASE_URL`, banco descartável). Workflow existente `Sales tests` executa a suíte completa com PostgreSQL no PR. Nunca usar banco de produção para testes. Não mergear/publicar com CI falho. Piloto após revisão: API desligada, conferir evidências por loja, confirmar persistência e dia seguinte, medir carga e só então avaliar interpretação paga. Rollback: desativar `KEIPER_AI_DAILY_ENABLED` e `KEIPER_AI_PAID_ENABLED`; tabelas/uso permanecem para auditoria.
