# Preenchimento assistido da ficha técnica

Rota administrativa `/anuncios/<conexao>/<MLB>/completar-ficha`, integrada ao botão da consulta de conteúdo. GET só lê o histórico local. POST de análise verifica conta e propriedade e lê título, descrição integral em texto simples (até 200.000 caracteres), atributos, variações, metadados da categoria e ficha técnica. Une os campos retornados pelas duas fontes e identifica `hidden`, `new_hidden` e `used_hidden`. Não usa modelo externo, OCR, imagens ou interpretações sem evidência.

As sugestões vêm de linhas explícitas `Nome ou ID do campo: valor` ou `= valor`, presentes no título ou descrição. Aliases devem identificar somente um campo; valores conflitantes ou linhas com vários campos ficam pendentes. Não usa a ocorrência solta de uma marca no título para inferir a marca do produto. Não copia medidas do produto para a embalagem nem inventa características. Campos sem fonte suficiente permanecem para revisão. Primeiras 50 sugestões por análise; após aplicá-las, uma nova leitura avalia as restantes. O inventário completo aceito continua paginado.

Envia apenas atributos comuns realmente vazios. Nunca substitui valores preenchidos, N/A, estruturas ou evidências próprias das variações. Não envia array `variations` nem modifica preço, estoque, fotos, título ou descrição. Tipo string respeita o limite de comprimento retornado e limite de leitura de 1.000 caracteres; listas/booleanos precisam corresponder univocamente a uma opção oficial; números ambíguos por separador de milhares não são sugeridos; unidades precisam corresponder à categoria. Esses limites são escolhas do leitor, não novas exigências do ML.

Por política desta primeira versão, ficam fora do envio: catálogo, identidade/PK, atributos fixos, inferidos, somente leitura, internos/restritos, atributos que definem variações/fotos e modalidades não verificadas. Campos exclusivos de cada variação ainda não são editados. Para User Products, consulta o vínculo recomendado pela API e só permite envio quando a busca escopada retorna exatamente o próprio item como único associado; compartilhamento ou resposta incompleta bloqueia a atualização. A interface mostra o motivo, sem afirmar que a plataforma proíbe todos esses casos.

## Revisão, envio e confirmação

Sugestões começam desmarcadas. Cada card mostra campo, identificação de oculto, antes, valor proposto e trecho/fonte. O cliente só envia IDs selecionados, nunca um payload de atualização confiado pelo servidor. Sessão administrativa, loja, anúncio, autor, CSRF e conexão ativa são conferidos. A análise expira em 15 minutos. Antes de escrever, relê fontes/regras/vínculos e compara a impressão da análise; mudança invalida a proposta. Alterações fora deste sistema durante a janela entre leitura e PUT não podem ser atomicamente impedidas pela aplicação; não há garantia inventada de transação entre ML e PostgreSQL.

Um PUT por análise, somente com os atributos escolhidos. Antes dele, persiste intenção e seleção. Nova leitura do anúncio, com conta/propriedade conferidas novamente, compara os campos; HTTP 200 sozinho não certifica gravação. Valores simples e a representação redundante `values` de um único valor são aceitos somente quando coerentes. Divergência, timeout, HTTP 429, resposta não confirmada ou falha na leitura ficam inconclusivos, sem retry automático e sem continuar a cadeia após 429. O botão de confirmação faz somente GETs. O administrador pode encerrar após conferir manualmente no ML; isso registra a decisão e não desfaz nem reenvia mudanças.

Planos e eventos persistem em duas tabelas novas (`listing_attribute_plans`, `listing_attribute_events`), sem alteração destrutiva de dados existentes. Planos guardam somente proposta, evidências, inventário e impressão; nunca tokens ou a descrição inteira. Eventos são append-only. A chave da análise deduplica submissões. Um advisory lock de sessão por item protege o fluxo mesmo entre commits e chamadas HTTP, com conexão dedicada fechada no finally; outra aba não envia em paralelo. Índice único impede duas intenções pendentes do mesmo item, inclusive em conexões duplicadas. Falha após intenção persistida mantém envio pendente, bloqueando reenvio. Histórico visível das dez análises mais recentes, mantendo as anteriores no banco.

## Fontes e validação

Documentação oficial consultada em 31/10/2026 pelo índice de busca:
- https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br/atributos — comportamento de tags e atualização de atributos.
- https://developers.mercadolivre.com.br/pt_br/user-products — modificações podem propagar para itens vinculados; consulta dos associados.
- https://developers.mercadolivre.com.br/pt_br/descricao-de-produtos/variacoes — preservação dos IDs e restrições de alterações em variações.

Testes usam respostas sintéticas e PostgreSQL descartável no CI: evidência e conflitos, campos bloqueados, propriedade, seleções adulteradas, validade da análise, intenção durável, atualização única, confirmação, timeout, 429, CSRF, escopo por autor/loja, concorrência entre planos e separação entre confirmação e reenvio. Não foi alterado anúncio real para testar esta entrega. Disponibilidade da permissão de escrita de cada conta e sucesso de gravação com item real dependem da ação explícita do administrador e da resposta oficial; não são presumidos pelo deploy.


## Leitura de frases explícitas — 31/10/2026

Também reconhece afirmações em português com o nome/ID oficial do campo e os verbos “é”, “são”, “mede” e “medem”: “O material é de aço” e “A largura mede 12,5 cm”. Aceita artigos/possessivos e remove somente o ponto final da frase; preserva a passagem do título/descrição como evidência (parágrafo de até 1.500 caracteres ou a própria frase). Não deduz campos por palavras soltas, sinônimos ou medidas sem identificação do atributo.

Perguntas, negações, alternativas, aproximações, frases compostas e valores conflitantes fazem o campo ficar para conferência. Contextos de embalagem, compatibilidade, exemplos ou variantes não são promovidos a atributos do produto; o bloqueio de contexto atravessa parágrafos até uma seção explícita do próprio produto. A leitura de frases só é habilitada em anúncios sem array de variações; os rótulos antigos continuam disponíveis. Não é compreensão semântica irrestrita e não usa modelo pago.

Para strings, opções oficiais com correspondência única podem usar o ID retornado pela categoria, evitando depender de capitalização no read-back; valores personalizados continuam sendo texto. Nomes ambíguos não escolhem um ID arbitrário. A documentação oficial de atributos foi reconferida em 31/10/2026 pelo índice de busca e confirma IDs para valores conhecidos de strings. A confirmação continua exigindo nova leitura.

A mesma documentação informa que N/A pode ser omitido na leitura padrão. O editor e a consulta de conteúdo passam a consultar o item completo com `include_internal_attributes=true`, tanto na análise/revalidação quanto na confirmação. Um N/A retornado é identificado como declaração a conferir, nunca oferecido como campo vazio. Não amplia permissões nem transforma campos internos em editáveis.

O leitor tem versão persistida na análise. Propostas de versão anterior ou expiradas não oferecem o envio; o servidor também as invalida. Antes do PUT, os valores e as representações efetivamente aprovadas precisam coincidir com os recalculados, mesmo quando a impressão das fontes não mudou. Atualização do leitor não autoriza substituição silenciosa de um valor revisado. Sem mudanças de schema ou novos endpoints de escrita.

Correspondências de opções oficiais preservam pontuação. IDs de unidade preservam símbolos e capitalização; nomes textuais completos podem ignorar acentos/case, mas abreviações curtas não são adivinhadas. Assim, @ não vira % e Mb não vira MB. Trata-se de cautela do leitor, não de nova regra imposta ao vendedor.

## Dados informados pelo consultor — 31/10/2026

A revisão oferece “Informar dado faltante” para os mesmos atributos comuns vazios elegíveis, inclusive ocultos. O formulário aceita campo oficial, valor e fonte/observação opcional. Exibe tipo e até dez exemplos oficiais (não é lista exaustiva). O servidor valida o tipo, limites, opções e unidades usando as regras já consultadas, sem presumir obrigatoriedade ou validar semanticamente a veracidade do dado declarado.

“Adicionar à revisão” relê anúncio/regras/vínculos e cria um plano sucessor imutável, com autoria e origem “Informado por você”. Não faz PUT. A revisão anterior preserva os dados originais e aponta para a nova revisão. Reenvio do mesmo formulário retorna o mesmo plano sem novas consultas; reutilização da chave com conteúdo diferente é recusada. Falha de validação mantém o campo digitado para correção e não substitui o plano anterior. Até 50 campos informados por revisão, priorizados no limite de 50 propostas; uma nova inclusão do mesmo campo substitui apenas a proposta no novo rascunho.

A seleção continua desmarcada. No envio, o servidor usa exclusivamente os dados persistidos, confere a autoria e recalcula o payload pelas regras atuais antes de qualquer PUT. Mudança do anúncio, categoria, vínculo, input ou payload aprovado bloqueia o envio. Versão do leitor 3 invalida antigas revisões prontas; confirmação de envios pendentes continua somente leitura. Não muda schema nem amplia as permissões ou o escopo de edição. Não houve gravação em anúncio real como teste.
