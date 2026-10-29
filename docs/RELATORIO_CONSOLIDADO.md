# Relatório consolidado por anúncio

Acesso pelo relatório de revisão do diagnóstico: “Relatório consolidado e PDF”. HTML em `/anuncios/<loja>/<MLB>/relatorio-consolidado`; download real em `/anuncios/<loja>/<MLB>/relatorio-consolidado.pdf`. Aceita `dias=7` ou `dias=30`, sempre encerrados ontem em Brasília, comparados com a janela anterior de mesmo tamanho.

Consolida vendas verificadas do anúncio (pedidos, unidades, bruto dos itens e ticket), visitas e razão observacional pedidos/visitas, série diária de vendas/visitas/Full/preço, revisão de conteúdo, contexto Ads da loja, contribuição financeira documentada do mesmo anúncio/período, histórico de ações, tarefas e contagem local de perguntas. Não amplia a coleta de perguntas. Não presume equivalência da conversão calculada à métrica oficial do ML. Não rateia publicidade da conta por item nem apresenta contribuição como lucro líquido.

O snapshot é lido em transação somente leitura `REPEATABLE READ`. A autorização exige administrador com acesso à loja e o anúncio deve existir nessa loja. Todos os acessos são locais; gerar ou abrir o relatório não consulta APIs externas, não altera dados e não envia mensagens. Respostas HTML/PDF não são armazenáveis em cache compartilhado. Arquivo PDF tem nome controlado, tipo `application/pdf`, `nosniff` e download em anexo.

O PDF A4 é gerado no servidor com ReportLab 4.4.9 e fontes Vera incorporadas, tabelas multipágina e cabeçalhos repetidos. O HTML continua disponível em tema claro/escuro e pode ser impresso. Não depende da janela de impressão para baixar o PDF e não envia o relatório automaticamente a terceiros.

Limites explícitos: até 5.000 observações de Full e preço por fonte/período, 50 ações mais recentes e as dez tarefas por prazo do relatório operacional, com contagens gerais e avisos. Cobertura incompleta ou bases não verificáveis aparecem como indisponíveis. Um estado de Full observado não comprova estoque contínuo; mudança de preço ou ação registrada não prova causa de vendas. Posicionamento, sazonalidade, avaliações e previsão não são inventados para completar o documento.

Validação: testes de fonte e ausência versus zero, isolamento/autorização, transação somente leitura, extração de conteúdo do PDF, textos longos, responsividade e download no celular. Fixtures sintéticas em `scripts/listing_consolidated_report_preview.py`; inspeção visual por renderização com Poppler.
