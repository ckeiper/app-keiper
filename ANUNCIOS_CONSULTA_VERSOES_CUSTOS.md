# Consulta de versões dos custos por anúncio

O histórico da rentabilidade permite abrir um registro específico e conferir datas, base original, seis componentes de custo e referências declaradas. A consulta é somente leitura: não restaura versões, não preenche custos novos e não substitui a última versão usada pelos indicadores.

A consulta exige administrador com acesso à loja e filtra simultaneamente loja, anúncio, período e identificador. Identificadores inválidos são recusados antes das consultas. Registro ausente ou fora do escopo retorna resposta genérica. A leitura compartilha o snapshot somente leitura da página; nenhuma consulta adicional ocorre sem seleção de registro.

O formulário de nova versão mantém suas validações e proteção CSRF. Fontes continuam declaradas pelo administrador, sem auditoria automática de documentos. A base histórica pode diferir das vendas atuais.

Validação: isolamento, parâmetros inválidos, somente leitura, manutenção do cálculo pela última versão, escape de conteúdo, ausência de restauração, PostgreSQL real e interface em 1440/390/320 px.
