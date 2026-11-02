"""Bounded batch input; values remain declarations until individually reviewed."""
from html import escape
from contextual_help import tip


def render(fields,csrf,plan,key,values=None):
    esc=lambda v:escape(str(v),quote=True)
    def values_for(name):
        if values is None:return []
        if hasattr(values,'getlist'):return values.getlist(name)[:50]
        value=values.get(name)
        return [value] if value is not None else []
    codes,raw,notes=(values_for(k) for k in ('manual_field','manual_value','manual_note'))
    count=min(50,max(len(codes),len(raw),len(notes),1))
    out='<details class="ae-manual"'+(' open' if codes else '')+'><summary>Informar dado faltante</summary><form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="manual"><input type="hidden" name="plan" value="'+esc(plan)+'"><input type="hidden" name="manual_key" value="'+esc(key+'-manual')+'"><div class="ae-manual-rows">'
    scopes={}
    for field in fields:
        if field.get('variation_id'):scopes.setdefault(field['variation_id'],'Variação '+field['variation_id'])
    filters='<div class="ae-field-filters"><label>Buscar campo<input type="search" class="ae-field-search" maxlength="200" placeholder="Nome ou código do atributo"></label><label>Destino<select class="ae-field-scope"><option value="all">Todos os destinos</option><option value="common">Anúncio principal</option><option value="variations">Todas as variações</option>'
    for vid,label in scopes.items():filters+='<option value="'+esc(vid)+'">'+esc(label)+'</option>'
    filters+='</select></label></div><p class="ae-field-count" role="status" aria-live="polite"></p>'
    options='<option value="">Selecione um campo</option>'
    for field in fields:
        label=field['name']+(' · Oculto' if field['hidden'] else '')+' ('+field.get('attribute_id',field['id'])+')'
        guidance={'string':'Texto','list':'Opção oficial','boolean':'Opção oficial','number':'Número','number_unit':'Número e unidade'}.get(field['value_type'],'Valor')
        if field.get('examples'):guidance+=' · Exemplos oficiais: '+', '.join(field['examples'])
        options+='<option data-scope="'+esc(field.get('variation_id','common'))+'" data-help="'+esc(guidance)+'" value="'+esc(field['id'])+'">'+esc(label)+'</option>'
    for i in range(count):
        selected=codes[i] if i<len(codes) else ''
        # Server-side recovery keeps every submitted row after validation errors.
        choice=options.replace('value="'+esc(selected)+'">','value="'+esc(selected)+'" selected>',1) if selected else options
        out+='<fieldset class="ae-manual-row"><legend>Campo '+str(i+1)+'</legend>'+filters+'<label>Campo ou variação<select name="manual_field" required>'+choice+'</select></label><p class="ae-value-help" aria-live="polite"></p><label>Valor'+tip('Valor informado','Use o valor correto do produto. Números com unidade precisam de espaço, por exemplo 10 cm. Todos os campos deste lote serão validados antes de criar a revisão; adicionar ainda não altera o anúncio.')+'<input name="manual_value" maxlength="1000" required value="'+esc(raw[i] if i<len(raw) else '')+'"></label><label>Fonte ou observação (opcional)<input name="manual_note" maxlength="500" value="'+esc(notes[i] if i<len(notes) else '')+'"></label><button type="button" class="ae-remove-row"'+(' hidden' if count==1 else '')+'>Remover campo '+str(i+1)+'</button></fieldset>'
    return out+'</div><p class="ae-batch-count" aria-live="polite">'+str(count)+' de 50 campos neste lote</p><button type="button" class="ae-add-row"'+(' disabled' if count==50 else '')+'>Adicionar outro campo</button><button type="submit">Adicionar à revisão</button></form></details>'


SCRIPT=r'''<script>document.querySelectorAll('.ae-manual').forEach(function(panel){
const list=panel.querySelector('.ae-manual-rows'),add=panel.querySelector('.ae-add-row'),form=panel.querySelector('form');
const fold=value=>value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR').trim();
const catalog=[...list.firstElementChild.querySelector('[name=manual_field]').options].filter(o=>o.value).map(function(o){const option=o.cloneNode(true);option.removeAttribute('selected');return {option,search:fold(o.textContent+' '+o.value)};});
function hint(row){const select=row.querySelector('[name=manual_field]');row.querySelector('.ae-value-help').textContent=select.selectedOptions[0]?.dataset.help||'';}
function filter(row){
 const select=row.querySelector('[name=manual_field]'),chosen=select.value,query=fold(row.querySelector('.ae-field-search').value).split(/\s+/).filter(Boolean),scope=row.querySelector('.ae-field-scope').value;
 const matches=catalog.filter(entry=>(scope==='all'||entry.option.dataset.scope===scope||(scope==='variations'&&entry.option.dataset.scope!=='common'))&&query.every(word=>entry.search.includes(word)));
 const fragment=document.createDocumentFragment(),blank=document.createElement('option');blank.value='';blank.textContent='Selecione um campo';fragment.appendChild(blank);
 const retained=chosen&&!matches.some(entry=>entry.option.value===chosen),prior=catalog.find(entry=>entry.option.value===chosen);
 if(retained&&prior){const option=prior.option.cloneNode(true);option.textContent+=' (selecionado)';fragment.appendChild(option);}
 matches.forEach(entry=>fragment.appendChild(entry.option.cloneNode(true)));select.replaceChildren(fragment);select.value=chosen;select.setCustomValidity('');
 row.querySelector('.ae-field-count').textContent=(matches.length?matches.length+' '+(matches.length===1?'campo encontrado':'campos encontrados'):'Nenhum campo encontrado')+(retained&&prior?' · Campo selecionado mantido.':'');hint(row);
}
function update(){const rows=[...list.children];rows.forEach(function(row,i){row.querySelector('legend').textContent='Campo '+(i+1);row.querySelector('[name=manual_field]').setCustomValidity('');const remove=row.querySelector('.ae-remove-row');remove.hidden=rows.length===1;remove.textContent='Remover campo '+(i+1);hint(row);});add.disabled=rows.length>=50;panel.querySelector('.ae-batch-count').textContent=rows.length+' de 50 campos neste lote';}
list.addEventListener('change',function(event){const row=event.target.closest('.ae-manual-row');if(!row)return;if(event.target.matches('.ae-field-scope'))filter(row);else if(event.target.matches('[name=manual_field]')){hint(row);filter(row);}});
list.addEventListener('input',function(event){const row=event.target.closest('.ae-manual-row');if(row&&event.target.matches('.ae-field-search'))filter(row);list.querySelectorAll('[name=manual_field]').forEach(function(s){s.setCustomValidity('');});});
list.addEventListener('click',function(event){if(!event.target.matches('.ae-remove-row'))return;const rows=[...list.children];if(rows.length<=1)return;const row=event.target.closest('.ae-manual-row'),next=row.nextElementSibling||row.previousElementSibling;row.remove();update();next.querySelector('[name=manual_field]').focus();});
add.addEventListener('click',function(){if(list.children.length>=50)return;const row=list.firstElementChild.cloneNode(true);row.querySelectorAll('input,select').forEach(function(input){input.value='';});row.querySelector('.ae-field-scope').value='all';list.appendChild(row);filter(row);update();row.querySelector('.ae-field-search').focus();});
form.addEventListener('submit',function(event){const seen=new Set();for(const select of list.querySelectorAll('[name=manual_field]')){select.setCustomValidity(seen.has(select.value)?'Selecione campos diferentes em cada linha.':'');seen.add(select.value);}if(!form.checkValidity()){event.preventDefault();form.reportValidity();}});
[...list.children].forEach(filter);update();
});</script>'''
