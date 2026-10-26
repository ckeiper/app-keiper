"""Private graph and its same-origin refresh endpoint. No database or external I/O."""
import hashlib
import json
from flask import session,jsonify
from anuncios_progress import read,summary
from anuncios_progress_view import render


def revision(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=True).encode()).hexdigest()


def refresh_script(current):
    return '''<script>(function(){
let revision=REVISION,busy=false;
async function update(){
 if(document.visibilityState!=='visible'||busy)return;busy=true;
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
 try{
  const response=await fetch('/evolucao-anuncios/grafico',{credentials:'same-origin',cache:'no-store',signal:controller.signal});
  if(!response.ok||!(response.headers.get('Content-Type')||'').includes('application/json'))return;
  const data=await response.json();
  if(typeof data.revision==='string'&&typeof data.html==='string'&&data.revision!==revision){
   const target=document.querySelector('.ap-progress');if(target){target.outerHTML=data.html;revision=data.revision;}
  }
 }catch(error){}finally{clearTimeout(timer);busy=false;}
}
setInterval(update,60000);document.addEventListener('visibilitychange',update);
})();</script>'''.replace('REVISION',json.dumps(current))


def register_progress(app,login_required,page):
    @app.route('/evolucao-anuncios')
    @login_required
    def anuncios_progress():
        if session.get('tipo')!='admin':return 'Acesso restrito',403
        try:
            data=read();model=summary(data)
        except (ValueError,KeyError,TypeError,OSError):
            return page('Evolução de Anúncios',"<main class='ap-progress'><h2>Acompanhamento temporariamente indisponível</h2><p>Não foi possível validar o registro desta versão.</p></main>"),503
        return page('Evolução de Anúncios',render(data,model)+refresh_script(revision(data)))

    @app.route('/evolucao-anuncios/grafico')
    @login_required
    def anuncios_progress_chart():
        if session.get('tipo')!='admin':return 'Acesso restrito',403
        try:
            data=read();model=summary(data)
        except (ValueError,KeyError,TypeError,OSError):
            return jsonify(error='Registro indisponível.'),503
        response=jsonify(revision=revision(data),html=render(data,model))
        response.headers['Cache-Control']='no-store'
        return response
