# Diagnóstico oficial das imagens do anúncio

Consulta administrativa sob demanda em `/anuncios/<loja>/<item>/imagem-principal`, acessível pelo checklist de conteúdo. GET só apresenta o formulário. Cada POST com CSRF verifica conta (`/users/me`) e item (`/items/{id}`). O diagnóstico faz mais um `POST /moderations/pictures/diagnostic`; carregar uma página de fotos faz somente os dois GETs. Não há retry, redirecionamentos ou consultas em lote. Nenhuma operação publica, troca ou remove fotos do anúncio.

A principal usa o `thumbnail_id`, confirmado entre os IDs únicos de `pictures`. A galeria permite escolher uma foto atual do mesmo anúncio, em páginas de cinquenta, até o limite de mil fotos e cem variações verificáveis. Antes de diagnosticar, relê a conta, o anúncio e a estrutura integral suportada e determina `thumbnail`, `variation_thumbnail` ou `other` pelos IDs atuais. O papel enviado pelo navegador não é usado. A principal do anúncio prevalece quando também é principal de variação.

A página solicitada deve ser um inteiro de 1 a 20. Página que deixou de existir informa indisponibilidade e pede recarregar, sem diagnóstico. Cada troca de página faz uma nova leitura, sem snapshot persistido, e exige nova escolha. O número da foto mantém a posição na leitura atual; mudanças externas podem alterar posições entre páginas. O ID da escolha é reconferido em toda a lista atual suportada, inclusive depois da posição cinquenta; foto removida ou externa bloqueia o POST de diagnóstico.

Cards mostram número, papel e vínculos com variações; metadados opcionais incompletos usam o identificador verificado. Até três vínculos são apresentados por card, com contagem dos demais. Prévias usam somente URLs HTTPS do CDN `http2.mlstatic.com` retornadas em `secure_url`, sem credenciais, query ou fragmento. Não há download de mídia no servidor; carregamento lazy e `referrerpolicy=no-referrer`. Prévia inválida ou ausente mantém a escolha por ID disponível.

A resposta deve corresponder ao ID de diagnóstico gerado no servidor e conter exatamente um diagnóstico do papel solicitado. Ações `empty` e `diagnostic` precisam ser coerentes com as detecções. Sinais reconhecidos: fundo, tamanho mínimo, textos/logos e marca d’água. Mensagens `REMEDY_SHORT` são escapadas. Resposta incompleta ou desconhecida não representa aprovação. Um resultado sem apontamentos cobre somente os critérios consultados, sem certificar a qualidade integral da foto.

Limites adicionais: dez diagnósticos, vinte detecções e dez mensagens de até 2.000 caracteres por detecção. Host de API fixo, timeout `(3,8)`, sem redirecionamento. HTTP 429 encerra a consulta sem prazo inventado. Não guarda fotos, respostas brutas ou histórico no banco. Autorização administrativa, isolamento por loja e CSRF permanecem obrigatórios.

Conteúdo permanece parcial: clips e coerência semântica com o produto não são avaliados. Estruturas além dos limites exigem conferência externa. Uso autenticado com anúncio real continua pendente; fixtures e deploy não substituem essa validação. Não criar dados de demonstração em produção.

Referências da implementação original (consultadas em 30/10/2026):
- https://developers.mercadolivre.com.br/pt_br/diagnostico-de-imagens
- https://developers.mercadolivre.com.br/en_us/image-diagnostics
- https://developers.mercadolivre.com.br/pt_br/autenticacao-e-autorizacao/publicacao-de-produtos
