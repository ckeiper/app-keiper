"""Inventory every Flask route in the source, without importing the live app."""
import ast
import json
from pathlib import Path


def collect(root):
    routes=[]
    for file in sorted(root.glob('*.py')):
        if file.name.startswith('test'):
            continue
        tree=ast.parse(file.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                continue
            calls=[n for n in ast.walk(node) if isinstance(n,ast.Call)]
            names=[n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else '' for n in calls]
            titles=[n.args[0].value for n in calls if n.args and isinstance(n.args[0],ast.Constant)
                    and isinstance(n.args[0].value,str) and isinstance(n.func,ast.Name)
                    and n.func.id in ('pagina','pagina_loja','page','shop_page')]
            for deco in node.decorator_list:
                if not isinstance(deco,ast.Call) or not isinstance(deco.func,ast.Attribute) or deco.func.attr not in ('route','get','post'):
                    continue
                if not deco.args or not isinstance(deco.args[0],ast.Constant):
                    raise ValueError(f'Route needs manual inspection: {file}:{node.lineno}')
                path=deco.args[0].value
                methods=next((ast.literal_eval(k.value) for k in deco.keywords if k.arg=='methods'),[deco.func.attr.upper() if deco.func.attr!='route' else 'GET'])
                if 'GET' not in methods:
                    kind='Ação'
                elif any(n in names for n in ('send_file','send_from_directory')) or 'export' in node.name or 'download' in node.name or 'modelo' in node.name:
                    kind='Arquivo'
                elif node.name in ('home','logout','campanhas_atualizar') or (not titles and 'redirect' in names):
                    kind='Redirecionamento / ação'
                elif titles:
                    kind='Tela'
                elif (file.name=='crm.py' and node.name not in ('crm_summary','crm_contact','crm_link_draft')) or file.name=='account_mfa.py':
                    kind='Tela'
                elif 'jsonify' in names:
                    kind='Endpoint / fragmento'
                else:
                    kind='Endpoint / fragmento'
                # CRM and MFA render through local wrappers rather than page().
                if 'GET' in methods and ((file.name=='crm.py' and node.name not in ('crm_summary','crm_contact','crm_link_draft')) or file.name=='account_mfa.py'):
                    kind='Tela'
                if node.name in ('conectar','callback_ml','atualizar','atualizar_tipo'):
                    kind='Fluxo auxiliar'
                routes.append(dict(path=path,methods=methods,handler=node.name,file=file.name,line=node.lineno,kind=kind,titles=list(dict.fromkeys(titles))))
    return sorted(routes,key=lambda r:(r['kind'],r['path'],r['file']))


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    routes=collect(root)
    dest=root/'visual-qa';dest.mkdir(exist_ok=True)
    (dest/'routes.json').write_text(json.dumps(routes,ensure_ascii=False,indent=2),encoding='utf-8')
    for kind in sorted({r['kind'] for r in routes}):
        group=[r for r in routes if r['kind']==kind]
        print(f'\n{kind}: {len(group)}')
        for r in group:
            print(r['path'],r['handler'],' | '.join(r['titles']))
