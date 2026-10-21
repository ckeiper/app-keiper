"""Optional administrator TOTP with encrypted seeds and single-use recovery codes."""
import hashlib
import html
import os
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken
from flask import abort, redirect, request, session
import pyotp
import qrcode
from qrcode.image.svg import SvgPathImage
from werkzeug.security import check_password_hash

KEY_ENV = 'MFA_ENCRYPTION_KEY'
CHALLENGE_SECONDS = 300
SETUP_SECONDS = 600


class MfaConfigurationError(RuntimeError):
    pass


def init_mfa_schema(conn, execute):
    for column in (
        'mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE', 'mfa_secret TEXT',
        'mfa_last_step BIGINT NOT NULL DEFAULT -1', 'mfa_pending_secret TEXT',
        'mfa_pending_nonce TEXT', 'mfa_pending_expires BIGINT',
        'mfa_pending_attempts INTEGER NOT NULL DEFAULT 0'):
        execute(conn,'ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS '+column)
    execute(conn,'''CREATE TABLE IF NOT EXISTS auth_mfa_challenges (
        nonce_hash TEXT PRIMARY KEY, usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        auth_version BIGINT NOT NULL, expires_at BIGINT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0, consumed BOOLEAN NOT NULL DEFAULT FALSE)''')
    execute(conn,'''CREATE TABLE IF NOT EXISTS auth_mfa_recovery_codes (
        usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        code_hash TEXT NOT NULL, PRIMARY KEY(usuario_id,code_hash))''')


def cipher():
    try:
        return Fernet(os.environ[KEY_ENV].encode('ascii'))
    except (KeyError, ValueError, UnicodeError):
        raise MfaConfigurationError('A configuração de segurança está indisponível.') from None


def encrypt_seed(seed):
    return cipher().encrypt(seed.encode()).decode()


def decrypt_seed(value):
    try:
        return cipher().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, UnicodeError, AttributeError):
        raise MfaConfigurationError('Não foi possível validar a configuração de segurança.') from None


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def recovery_hash(value):
    return digest(value.replace('-','').replace(' ','').lower())


def matching_step(seed,code,last=-1,now=None):
    if not code.isascii() or len(code)!=6 or not code.isdigit():
        return None
    step=int(time.time() if now is None else now)//30
    totp=pyotp.TOTP(seed)
    for candidate in (step,step-1,step+1):
        if candidate>last and secrets.compare_digest(totp.at(candidate*30),code):
            return candidate
    return None


def complete_login(user):
    session.clear()
    session.permanent=True
    for field,key in (('usuario_id','id'),('username','username'),('nome','nome'),
                      ('tipo','tipo'),('conexao_id','conexao_id'),('auth_version','auth_version')):
        session[field]=user[key]


def issue_challenge(user,bank,query,execute):
    nonce=secrets.token_urlsafe(32)
    expires=int(time.time())+CHALLENGE_SECONDS
    with bank() as conn:
        rows=query(conn,'SELECT id,auth_version,mfa_enabled FROM usuarios WHERE id=%s FOR UPDATE',(user['id'],))
        if not rows or not rows[0]['mfa_enabled'] or rows[0]['auth_version']!=user['auth_version']:
            return False
        execute(conn,'DELETE FROM auth_mfa_challenges WHERE usuario_id=%s AND expires_at<%s',(user['id'],int(time.time())))
        execute(conn,'''INSERT INTO auth_mfa_challenges(nonce_hash,usuario_id,auth_version,expires_at)
            VALUES(%s,%s,%s,%s)''',(digest(nonce),user['id'],user['auth_version'],expires))
    session.clear()
    session['mfa_pending']={'uid':user['id'],'nonce':nonce,'expires':expires}
    return True


def consume_factor(conn,user,code,query,execute):
    normalized=code.replace('-','').replace(' ','').lower()
    if len(normalized)==24 and all(c in '0123456789abcdef' for c in normalized):
        return bool(query(conn,"""DELETE FROM auth_mfa_recovery_codes
            WHERE usuario_id=%s AND code_hash=%s RETURNING usuario_id""",(user['id'],recovery_hash(code))))
    if not code.isascii() or len(code)!=6 or not code.isdigit():
        return False
    step=matching_step(decrypt_seed(user['mfa_secret']),code,user['mfa_last_step'])
    if step is None:
        return False
    execute(conn,'UPDATE usuarios SET mfa_last_step=%s WHERE id=%s',(step,user['id']))
    return True


def verify_challenge(pending,code,bank,query,execute):
    now=int(time.time())
    if not isinstance(pending,dict) or pending.get('expires',0)<now or not pending.get('nonce'):
        return None
    with bank() as conn:
        rows=query(conn,'SELECT * FROM usuarios WHERE id=%s FOR UPDATE',(pending.get('uid'),))
        if not rows or not rows[0]['mfa_enabled']:
            return None
        user=rows[0]
        rows=query(conn,'''SELECT * FROM auth_mfa_challenges
            WHERE nonce_hash=%s AND usuario_id=%s FOR UPDATE''',(digest(pending['nonce']),user['id']))
        if not rows:
            return None
        challenge=rows[0]
        if (challenge['consumed'] or challenge['attempts']>=5 or challenge['expires_at']<now
                or challenge['auth_version']!=user['auth_version']):
            return None
        execute(conn,'UPDATE auth_mfa_challenges SET attempts=attempts+1 WHERE nonce_hash=%s',(digest(pending['nonce']),))
        if not consume_factor(conn,user,code,query,execute):
            return None
        execute(conn,'UPDATE auth_mfa_challenges SET consumed=TRUE WHERE nonce_hash=%s',(digest(pending['nonce']),))
        return user


def register_mfa(app,bank,query,execute,page,rate):
    @app.errorhandler(MfaConfigurationError)
    def mfa_unavailable(error):
        app.logger.error('mfa_configuration_unavailable')
        return 'A verificação de segurança está temporariamente indisponível. Tente novamente em instantes.',503

    esc=html.escape
    def account(conn,lock=False):
        rows=query(conn,'SELECT * FROM usuarios WHERE id=%s'+(' FOR UPDATE' if lock else ''),(session['usuario_id'],))
        if not rows:abort(403)
        return rows[0]

    def view(title,body):
        return page(title,"<div style='max-width:680px;margin:auto'><div class='card'>"
            +body+"</div><p><a href='/painel'>Voltar ao painel</a></p></div>")

    def admin():
        if 'usuario_id' not in session:return redirect('/login')
        if session.get('tipo')!='admin':abort(403)

    def form(action,label,password=False):
        return ("<form method='post' style='margin-top:18px'><input type='hidden' name='acao' value='"+action+"'>"
            +("<label>Senha atual<input type='password' name='senha' class='input' autocomplete='current-password' required maxlength='256'></label>" if password else '')
            +(("<label>"+("Código de seis números do aplicativo" if action=="confirmar" else "Código do aplicativo ou de recuperação")+"<input name='codigo' class='input' autocomplete='one-time-code' required maxlength='100'></label>") if action in ('confirmar','desativar') else '')
            +"<button class='btn-salvar' style='max-width:100%;white-space:normal'>"+label+"</button></form>")

    @app.route('/login/verificar',methods=['GET','POST'])
    def mfa_verify():
        pending=session.get('mfa_pending')
        if not pending or pending.get('expires',0)<int(time.time()):
            session.pop('mfa_pending',None)
            return redirect('/login')
        error=''
        if request.method=='POST':
            if not rate(bank,execute,'mfa_login',str(pending['uid'])):
                return 'Muitas tentativas. Aguarde 15 minutos.',429
            code=request.form.get('codigo','').strip()
            if len(code)>100:abort(400)
            user=verify_challenge(pending,code,bank,query,execute)
            if user:
                complete_login(user)
                return redirect('/painel/'+str(user['conexao_id']) if user['tipo']=='cliente' and user['conexao_id'] else '/painel')
            error="<div class='aviso'>Código inválido, expirado ou já utilizado. Use um novo código ou entre novamente.</div>"
        return view('Confirmar acesso',"<h2>Confirmar acesso</h2><p>Digite o código do aplicativo autenticador ou um código de recuperação.</p>"
            +error+"<form method='post'><label>Código<input name='codigo' class='input' autocomplete='one-time-code' autofocus required maxlength='100'></label>"
            "<button class='btn-salvar'>Confirmar e entrar</button></form><p><a href='/login'>Voltar ao login</a></p>")

    @app.route('/seguranca',methods=['GET','POST'])
    def account_security():
        denied=admin()
        if denied:return denied
        notice=''
        with bank() as conn:
            user=account(conn,lock=request.method=='POST')
            if request.method=='POST':
                if not rate(bank,execute,'mfa_settings',str(user['id'])):
                    return 'Muitas tentativas. Aguarde 15 minutos.',429
                action=request.form.get('acao','')
                password=request.form.get('senha','')
                code=request.form.get('codigo','').strip()
                if len(password)>256 or len(code)>100:abort(400)
                if action=='iniciar' and not user['mfa_enabled']:
                    if not check_password_hash(user['senha_hash'],password):
                        notice='Senha atual incorreta.'
                    else:
                        nonce=secrets.token_urlsafe(32)
                        seed=pyotp.random_base32()
                        execute(conn,'''UPDATE usuarios SET mfa_pending_secret=%s,mfa_pending_nonce=%s,
                            mfa_pending_expires=%s,mfa_pending_attempts=0 WHERE id=%s''',
                            (encrypt_seed(seed),digest(nonce),int(time.time())+SETUP_SECONDS,user['id']))
                        session['mfa_setup_nonce']=nonce
                        user=account(conn)
                elif action=='confirmar' and not user['mfa_enabled']:
                    nonce=session.get('mfa_setup_nonce','')
                    valid=(nonce and user['mfa_pending_nonce'] and secrets.compare_digest(digest(nonce),user['mfa_pending_nonce'])
                           and (user['mfa_pending_expires'] or 0)>=int(time.time()) and user['mfa_pending_attempts']<5)
                    if valid:
                        execute(conn,'UPDATE usuarios SET mfa_pending_attempts=mfa_pending_attempts+1 WHERE id=%s',(user['id'],))
                        seed=decrypt_seed(user['mfa_pending_secret'])
                        step=matching_step(seed,code)
                        if step is not None:
                            codes=['-'.join(raw[i:i+4] for i in range(0,len(raw),4)) for raw in [secrets.token_hex(12) for _ in range(10)]]
                            execute(conn,'''UPDATE usuarios SET mfa_enabled=TRUE,mfa_secret=%s,mfa_last_step=%s,
                                mfa_pending_secret=NULL,mfa_pending_nonce=NULL,mfa_pending_expires=NULL,
                                auth_version=auth_version+1 WHERE id=%s''',(user['mfa_pending_secret'],step,user['id']))
                            execute(conn,'DELETE FROM auth_mfa_recovery_codes WHERE usuario_id=%s',(user['id'],))
                            for recovery in codes:
                                execute(conn,'INSERT INTO auth_mfa_recovery_codes VALUES(%s,%s)',(user['id'],recovery_hash(recovery)))
                            user=account(conn)
                            session['auth_version']=user['auth_version']
                            session.pop('mfa_setup_nonce',None)
                            body="<h2>Verificação em duas etapas ativada</h2><p>Guarde estes códigos fora do painel. Cada um só pode ser usado uma vez. Eles não serão exibidos novamente.</p>"
                            body+="<div style='display:grid;gap:10px;margin:20px 0'>"+''.join("<code class='recovery-code'>"+esc(c)+"</code>" for c in codes)+"</div>"
                            return view('Códigos de recuperação',body+"<a href='/seguranca'>Concluir</a>")
                    notice='Código inválido ou configuração expirada. Aguarde um novo código ou inicie novamente.'
                elif action=='desativar' and user['mfa_enabled']:
                    if check_password_hash(user['senha_hash'],password) and consume_factor(conn,user,code,query,execute):
                        execute(conn,'''UPDATE usuarios SET mfa_enabled=FALSE,mfa_secret=NULL,mfa_last_step=-1,
                            mfa_pending_secret=NULL,mfa_pending_nonce=NULL,mfa_pending_expires=NULL,
                            auth_version=auth_version+1 WHERE id=%s''',(user['id'],))
                        execute(conn,'DELETE FROM auth_mfa_recovery_codes WHERE usuario_id=%s',(user['id'],))
                        execute(conn,'DELETE FROM auth_mfa_challenges WHERE usuario_id=%s',(user['id'],))
                        session.clear()
                        return redirect('/login')
                    notice='Senha ou código inválido. Aguarde um novo código do aplicativo e tente novamente.'
            body="<h2>Segurança da conta</h2>"+("<div class='aviso'>"+esc(notice)+"</div>" if notice else '')
            if user['mfa_enabled']:
                count=query(conn,'SELECT COUNT(*) AS total FROM auth_mfa_recovery_codes WHERE usuario_id=%s',(user['id'],))[0]['total']
                body+="<p><span class='tag ativa'>Verificação em duas etapas ativa</span></p><p>Seu login exige a senha e um código do aplicativo.</p><p>Códigos de recuperação disponíveis: "+str(count)+".</p>"
                body+=form('desativar','Desativar verificação em duas etapas',password=True)
            else:
                body+="<p>Adicione uma confirmação por aplicativo autenticador para proteger seu acesso.</p>"
                nonce=session.get('mfa_setup_nonce','')
                pending=(nonce and user['mfa_pending_nonce'] and secrets.compare_digest(digest(nonce),user['mfa_pending_nonce'])
                         and (user['mfa_pending_expires'] or 0)>=int(time.time()) and user['mfa_pending_attempts']<5)
                if pending:
                    seed=decrypt_seed(user['mfa_pending_secret'])
                    uri=pyotp.TOTP(seed).provisioning_uri(name=user['username'],issuer_name='Keiper Consultoria')
                    svg=qrcode.make(uri,image_factory=SvgPathImage).to_string(encoding='unicode').replace('<svg ', '<svg style="width:100%;height:auto" ',1)
                    body+="<p>1. Escaneie o QR Code no Google Authenticator, Microsoft Authenticator ou outro aplicativo compatível.</p><div style='background:white;width:260px;max-width:100%;margin:18px auto'>"+svg+"</div>"
                    body+="<p>Ou cadastre esta chave manualmente:</p><code id='mfa-manual-key' style='overflow-wrap:anywhere'>"+esc(seed)+"</code><p>2. Digite o código de seis números para confirmar. A configuração vale por 10 minutos.</p>"
                    body+=form('confirmar','Confirmar e ativar')
                else:
                    body+=form('iniciar','Configurar aplicativo autenticador',password=True)
        return view('Segurança da conta',body)
