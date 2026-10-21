"""Regression tests for the homepage CRM widget."""
from flask import render_template_string
from crm import HOME_WIDGET, SUMMARY


def test_crm_home_keeps_async_fetch_and_actions():
    assert "fetch('/crm/resumo'" in HOME_WIDGET
    assert "kc-crm-card" in HOME_WIDGET
    assert "crm-home-summary" in HOME_WIDGET
    assert "Abrir CRM" in HOME_WIDGET


def test_crm_summary_renders_empty_followup_state():
    from flask import Flask
    app = Flask(__name__)
    with app.app_context():
        page = render_template_string(SUMMARY, overdue=0, due=0, undated=0, leads=[])
    assert "Seus próximos contatos" in page
    assert "Nenhum retorno vencido" in page
    assert "/crm?prazo=atrasados" in page
    assert "/crm?prazo=hoje" in page
    assert "/crm?prazo=sem_data" in page
    assert "/crm/novo" in page
    assert "/crm/importar" in page
