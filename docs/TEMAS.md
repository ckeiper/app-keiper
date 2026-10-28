# Aparência do Dashboard Keiper

O botão no cabeçalho alterna entre o tema escuro existente (padrão) e o tema claro. A preferência fica em `localStorage` na chave `keiper-theme`, por navegador/dispositivo, e acompanha as páginas e abas da mesma origem. Não altera dados das lojas. Com armazenamento indisponível, a troca funciona durante a página aberta.

`theme_switcher.py` concentra inicialização antes da pintura, paleta clara, controle acessível e atualização de eixos/legendas do Chart.js. As regras claras usam uma camada CSS com declarações prioritárias para conviver com os estilos legados. Nenhuma inversão de imagens ou de gráficos é aplicada. O modo escuro conserva os estilos existentes.

Validação: `python -m unittest test_theme_switcher test_visual_theme test_store_ads_design test_management_design`; `python scripts/theme_preview.py`; `node scripts/theme_browser_check.cjs`. Os previews usam apenas dados sintéticos. A checagem de navegador verifica troca, persistência, abas, armazenamento bloqueado, gráficos e 12 telas em 1440, 390 e 320 pixels. Os dados e o escopo auditado de Anúncios 2.0 não são modificados por esta entrega visual.
