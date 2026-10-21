"""Validate every authenticated request against the current account revision."""
from flask import abort, redirect, request, session

PUBLIC_ENDPOINTS = {'login', 'recuperar', 'redefinir', 'logo_arquivo', 'static', 'mfa_verify'}


def init_session_schema(conn, execute):
    execute(conn, 'ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS auth_version BIGINT NOT NULL DEFAULT 1')
    execute(conn, '''CREATE OR REPLACE FUNCTION keiper_revoke_user_sessions()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.senha_hash IS DISTINCT FROM OLD.senha_hash
               OR NEW.tipo IS DISTINCT FROM OLD.tipo
               OR NEW.conexao_id IS DISTINCT FROM OLD.conexao_id THEN
                NEW.auth_version := OLD.auth_version + 1;
            END IF;
            RETURN NEW;
        END;
        $$''')
    execute(conn, 'DROP TRIGGER IF EXISTS keiper_user_sessions ON usuarios')
    execute(conn, '''CREATE TRIGGER keiper_user_sessions
        BEFORE UPDATE OF senha_hash, tipo, conexao_id ON usuarios
        FOR EACH ROW EXECUTE FUNCTION keiper_revoke_user_sessions()''')


def install_session_guard(app, load_user):
    @app.before_request
    def validate_account_session():
        if 'usuario_id' not in session or request.endpoint in PUBLIC_ENDPOINTS:
            return None
        # Cookies issued before this protection must log in again once.
        if not isinstance(session.get('auth_version'), int):
            session.clear()
            return redirect('/login')
        try:
            user = load_user(session['usuario_id'])
        except Exception as error:
            # Fail closed, but do not turn a DB outage into a forced logout.
            app.logger.error('session_validation_unavailable error_type=%s', type(error).__name__)
            abort(503, 'Não foi possível validar o acesso. Tente novamente em instantes.')
        if (not user or user['auth_version'] != session['auth_version']
                or user['tipo'] != session.get('tipo')
                or user['conexao_id'] != session.get('conexao_id')):
            session.clear()
            return redirect('/login')
        return None
