# Interrupção da consulta de conteúdo após HTTP 429

A conferência `/anuncios/<loja>/<item>/conteudo-atual` encadeia conta, item, descrição, atributos de categoria, consulta condicional opcional e ficha técnica opcional. Havia uma falha: um 429 na descrição impedia apenas a ficha técnica, mas ainda permitia consultar a categoria. Agora o fluxo interrompe todas as chamadas subsequentes da **mesma consulta** após qualquer 429, incluindo GET e a consulta condicional POST. Não faz retry automático nem mantém uma requisição web esperando liberação da cota.

Fonte oficial consultada em 30/10/2026: https://developers.mercadolivre.com.br/pt_br/usuarios-e-aplicativos/rate-limit-erro-429 . A orientação geral é reduzir picos e adotar backoff apropriado. Nesta leitura interativa limitada, a escolha é encerrar o encadeamento e orientar nova tentativa posterior; não inventa cota fixa, prazo de liberação ou cooldown global por loja/aplicação. Não altera os coletores agendados ou outras consultas simultâneas.

Se conta ou item não puderam ser verificados, não apresenta leitura do anúncio. Se já obteve o item, preserva título, fotos e atributos retornados; mantém descrição ou regras anteriores quando obtidas e marca as partes não consultadas como desconhecidas por limitação. Não transforma bloqueio em ausência, erro do anúncio, condição não aplicável ou revisão aprovada. Mostra aviso discreto de consulta parcial nos dois temas.

O sinal `rate_limited` é propagado também quando a última chamada (ficha técnica) retorna 429. Falhas 404/500 permanecem independentes: não são rotuladas como limite. Segurança, propriedade, CSRF, timeouts e ausência de gravação no Mercado Livre permanecem no fluxo existente. Não há nova chamada, schema ou alteração de dados reais para testes.

Regressões verificam a contagem exata de requisições em cada posição, preservação da evidência, interrupção da condicional/ficha e mensagens. Um teste de ficha técnica antes aninhado dentro de outro método passou a ser um método de teste executado. Navegador cobre sete estados × dois temas × três larguras, com fixtures sintéticas isoladas. A frente Conteúdo continua parcial pelo escopo amplo ainda não concluído.
