# Otimizador de Títulos Keiper

1. Extraia este ZIP em uma pasta permanente.
2. No Chrome, abra `chrome://extensions` e ative o modo do desenvolvedor.
3. Clique em **Carregar sem compactação** e selecione a pasta com `manifest.json`.
4. Recarregue o Dashboard e abra **Anúncios → Otimizador de Títulos**.
5. Informe ou selecione o anúncio, confira produto/marca/modelo e clique em **Buscar concorrentes**.

A extensão usa a busca pública do Mercado Livre e abre uma aba temporária. Lê até cinco páginas em ordem de relevância; a ferramenta filtra até 50 anúncios que contenham a identidade informada. Os termos representam frequência nos títulos coletados, não volume de buscas, vendas ou garantia de posicionamento. Anúncios identificados como patrocinados são descartados.

A ferramenta apenas constrói títulos para copiar. Não publica alterações nos anúncios, não lê cookies, senhas ou tokens do Mercado Livre e não resolve verificações de acesso. Se a busca apresentar erro ou exigir verificação, a coleta para e o Dashboard informa a interrupção. A amostra pode ter menos de 30 resultados comparáveis e será identificada como insuficiente.

## Estado de validação

Seletores e fluxo são testados com páginas controladas. A validação ponta a ponta na busca real ainda está pendente: em 26/11/2026 o navegador de teste recebeu HTTP 403 com a mensagem “Hubo un error accediendo a esta pagina...”. Não apresentar esta versão como coleta real validada até essa conferência.
