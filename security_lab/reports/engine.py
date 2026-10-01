import json, html, hashlib
from pathlib import Path

def build(finding, severity='info', component='unknown', evidence=None, reproduction=None, expected=None, actual=None, fix=None, verification=None):
    return {'finding':finding,'severity':severity,'affected_component':component,'evidence':evidence or [],'reproduction_steps':reproduction or [],'expected_behavior':expected,'actual_behavior':actual,'suggested_fix':fix,'verification_result':verification}
def write(report:dict, out:Path, fmt='json'):
    out=Path(out); out.parent.mkdir(parents=True,exist_ok=True)
    if fmt=='json': out.write_text(json.dumps(report,indent=2))
    elif fmt=='md': out.write_text('# Security Report\n\n'+ '\n'.join(f'**{k.replace("_"," ").title()}:** {v}' for k,v in report.items()))
    else: out.write_text('<html><body><h1>Security Report</h1>'+''.join(f'<h3>{html.escape(k)}</h3><pre>{html.escape(str(v))}</pre>' for k,v in report.items())+'</body></html>')
    return {'path':str(out.resolve()),'filename':out.name,'mime':{'json':'application/json','md':'text/markdown','html':'text/html'}[fmt],'size':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
