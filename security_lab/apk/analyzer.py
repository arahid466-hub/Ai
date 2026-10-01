import hashlib, json, re, shutil, subprocess, tempfile, zipfile
from pathlib import Path

def tools(): return {x:bool(shutil.which(x)) for x in ('apktool','jadx','jadx-gui','aapt','aapt2','apksigner')}
def analyze(path:str):
    p=Path(path).resolve()
    if not p.is_file() or p.suffix.lower()!='.apk': raise ValueError('APK file required')
    report={'file':str(p),'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'tools':tools(),'permissions':[],'components':[],'urls':[],'status':'completed'}
    with zipfile.ZipFile(p) as z:
        names=z.namelist(); report['entries']=len(names); report['has_manifest']='AndroidManifest.xml' in names
        for n in names:
            if n.endswith(('.dex','.so','.arsc')): continue
            try: text=z.read(n).decode('utf-8','ignore')
            except: continue
            report['urls'] += re.findall(r'https?://[^\s"<>]+',text)
            report['permissions'] += re.findall(r'android\.permission\.[A-Z_]+',text)
        report['urls']=sorted(set(report['urls']))[:200]; report['permissions']=sorted(set(report['permissions']))
    return report
