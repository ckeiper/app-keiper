# Diagnóstico oficial da imagem principal

Consulta administrativa sob demanda em `/anuncios/<loja>/<item>/imagem-principal`, acessível pelo checklist de conteúdo. GET só apresenta o formulário; POST com CSRF verifica conta (`/users/me`) e item (`/items/{id}`) antes de chamar `POST /moderations/pictures/diagnostic`. Máximo de dois GETs e um POST, sem retry, redirecionamentos, lotes ou chamadas a modelos de IA de terceiros. O POST cria uma consulta de diagnóstico; não publica, associa, troca ou remove fotos e não altera o anúncio.

Fontes oficiais consultadas em 30/10/2026:
- https://developers.mercadolivre.com.br/pt_br/diagnostico-de-imagens
- https://developers.mercadolivre.com.br/en_us/image-diagnostics
- https://developers.mercadolivre.com.br/pt_br/autenticacao-e-autorizacao/publicacao-de-produtos

A foto é exclusivamente o `thumbnail_id` retornado pelo item da mesma conta e site MLB, confirmado entre os IDs únicos de `pictures`. Não presume que a primeira foto seja principal. ID ausente, vínculo ambíguo ou categoria inválida encerra a leitura como desconhecida. Não aceita URL, base64 ou ID de foto do formulário; não baixa nem renderiza mídia externa. O corpo contém apenas ID de diagnóstico gerado no servidor, `picture_id`, categoria, tipo `thumbnail` e título limitado. Categoria vem do item; não inventa exigência universal de fundo branco ou tamanho mínimo.

A resposta precisa corresponder ao ID da consulta e conter um único diagnóstico `thumbnail`. Não reaproveita apontamentos de `other` ou `variation_thumbnail`. Ações `empty` e `diagnostic` precisam ser coerentes com as detecções. Sinais reconhecidos: fundo, tamanho mínimo, textos/logos e marca d’água. As orientações `REMEDY_SHORT` vêm da API e são exibidas como texto escapado. Regras não reconhecidas, duplicadas, ausentes ou inconsistentes permanecem não verificáveis, nunca viram ausência de problemas. Um resultado sem apontamentos cobre só os critérios efetivamente consultados; não aprova o anúncio ou a qualidade completa da foto.

Limites locais: 1.000 fotos para conferir o vínculo, dez diagnósticos, vinte detecções e dez mensagens de até 2.000 caracteres por detecção. Host fixo, bearer sem exposição, timeout `(3,8)`, sem redirecionamento. HTTP 429 encerra a consulta e pede tentativa posterior, sem prazo inventado. Não guarda fotos, respostas brutas ou histórico no banco. Conta/loja/anúncio, administrador e CSRF são conferidos no servidor; resposta privada usa a proteção global existente. Shell mantém Anúncios ativo e não apresenta botão genérico de atualizar anúncios nesta página.

A frente Conteúdo permanece parcial: nesta etapa só a imagem principal recebe o diagnóstico oficial; fotos secundárias, variações, clips e coerência semântica não são analisadas. Em catálogo, orienta conferir a gestão das imagens antes de propor edição. Uso autenticado e disponibilidade real do endpoint na conta precisam ser distinguidos de testes com fixtures e prova de deploy. Não criar dados de demonstração nem induzir erros ou moderações em produção.
