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
    out='<details class="ae-manual"><summary>Informar dado faltante</summary><form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="manual"><input type="hidden" name="plan" value="'+esc(plan)+'"><input type="hidden" name="manual_key" value="'+esc(key+'-manual')+'"><div class="ae-manual-rows">'
    options='<option value="">Selecione um campo</option>'
    for field in fields:
        label=field['name']+(' · Oculto' if field['hidden'] else '')+' ('+field.get('attribute_id',field['id'])+')'
        guidance={'string':'Texto','list':'Opção oficial','boolean':'Opção oficial','number':'Número','number_unit':'Número e unidade'}.get(field['value_type'],'Valor')
        if field.get('examples'):guidance+=' · Exemplos oficiais: '+', '.join(field['examples'])
        options+='<option data-help="'+esc(guidance)+'" value="'+esc(field['id'])+'">'+esc(label)+'</option>'
    for i in range(count):
        selected=codes[i] if i<len(codes) else ''
        # Server-side recovery keeps every submitted row after validation errors.
        choice=options.replace('value="'+esc(selected)+'">','value="'+esc(selected)+'" selected>',1) if selected else options
        out+='<fieldset class="ae-manual-row"><legend>Campo '+str(i+1)+'</legend><label>Campo ou variação<select name="manual_field" required>'+choice+'</select></label><p class="ae-value-help" aria-live="polite"></p><label>Valor'+tip('Valor informado','Use o valor correto do produto. Números com unidade precisam de espaço, por exemplo 10 cm. Todos os campos deste lote serão validados antes de criar a revisão; adicionar ainda não altera o anúncio.')+'<input name="manual_value" maxlength="1000" required value="'+esc(raw[i] if i<len(raw) else '')+'"></label><label>Fonte ou observação (opcional)<input name="manual_note" maxlength="500" value="'+esc(notes[i] if i<len(notes) else '')+'"></label><button type="button" class="ae-remove-row"'+(' hidden' if count==1 else '')+'>Remover campo '+str(i+1)+'</button></fieldset>'
    return out+'</div><p class="ae-batch-count" aria-live="polite">'+str(count)+' de 50 campos neste lote</p><button type="button" class="ae-add-row"'+(' disabled' if count==50 else '')+'>Adicionar outro campo</button><button type="submit">Adicionar à revisão</button></form></details>'


SCRIPT='''<script>document.querySelectorAll('.ae-manual').forEach(function(panel){const list=panel.querySelector('.ae-manual-rows');const add=panel.querySelector('.ae-add-row');const form=panel.querySelector('form');function hint(row){const select=row.querySelector('select');row.querySelector('.ae-value-help').textContent=select.selectedOptions[0]?.dataset.help||'';}function update(){const rows=[...list.children];rows.forEach(function(row,i){row.querySelector('legend').textContent='Campo '+(i+1);row.querySelector('select').setCustomValidity('');const remove=row.querySelector('.ae-remove-row');remove.hidden=rows.length===1;remove.textContent='Remover campo '+(i+1);hint(row);});add.disabled=rows.length>=50;panel.querySelector('.ae-batch-count').textContent=rows.length+' de 50 campos neste lote';}list.addEventListener('change',function(event){const row=event.target.closest('.ae-manual-row');if(row)hint(row);});list.addEventListener('click',function(event){if(!event.target.matches('.ae-remove-row'))return;const rows=[...list.children];if(rows.length<=1)return;const row=event.target.closest('.ae-manual-row');const next=row.nextElementSibling||row.previousElementSibling;row.remove();update();next.querySelector('select').focus();});add.addEventListener('click',function(){if(list.children.length>=50)return;const row=list.firstElementChild.cloneNode(true);row.querySelectorAll('input,select').forEach(function(input){input.value='';});list.appendChild(row);update();row.querySelector('select').focus();});form.addEventListener('submit',function(event){const seen=new Set();for(const select of list.querySelectorAll('select')){select.setCustomValidity(seen.has(select.value)?'Selecione campos diferentes em cada linha.':'');seen.add(select.value);}if(!form.checkValidity()){event.preventDefault();form.reportValidity();}});list.addEventListener('input',function(){list.querySelectorAll('select').forEach(function(s){s.setCustomValidity('');});});update();});</script>'''
