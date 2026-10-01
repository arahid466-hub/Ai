import os, re, json, time, hmac, base64, hashlib, secrets, sqlite3, subprocess, platform, shutil, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from ai.core.autonomous_agent import AutonomousAgent
from ai.tool_registry import snapshot
from security_lab.apk.analyzer import analyze as analyze_apk
from security_lab.authorized_checks import apk_integrity, apk_surface, api_target_guard, toolchain_status
from server.extended_api import router as extended_router

ROOT=Path(__file__).resolve().parent.parent
WEB=ROOT/'web'
DATA=Path(os.getenv('AETHER_DATA_DIR', str(ROOT/'data'))).resolve()
DB=Path(os.getenv('AETHER_DB', str(DATA/'aether.db'))).resolve()
WORKSPACE=Path(os.getenv('AETHER_WORKSPACE', str(DATA/'workspace'))).resolve()
UPLOADS=Path(os.getenv('AETHER_UPLOADS', str(DATA/'uploads'))).resolve()
MEDIA=Path(os.getenv('AETHER_MEDIA', str(DATA/'media'))).resolve()
LOGS=Path(os.getenv('AETHER_LOG_DIR', str(DATA/'logs'))).resolve()
for p in (DATA, WORKSPACE, UPLOADS, MEDIA, LOGS, DATA/'models', DATA/'huggingface/hub', DATA/'jobs', DATA/'cache'):
    p.mkdir(parents=True, exist_ok=True)
START=time.time()
SECRET=os.getenv('AETHER_SECRET_KEY','').encode() or secrets.token_bytes(48)
OWNER=os.getenv('AETHER_OWNER_USERNAME','owner')


def now(): return datetime.now(timezone.utc).isoformat()
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def pwh(p,s=None):
    s=s or secrets.token_bytes(16)
    return 'pbkdf2$'+base64.urlsafe_b64encode(s).decode()+'$'+hashlib.pbkdf2_hmac('sha256',p.encode(),s,210000).hex()
def verify(p,v):
    try:
        _,ss,hh=v.split('$'); s=base64.urlsafe_b64decode(ss.encode())
        return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',p.encode(),s,210000).hex(),hh)
    except Exception: return False

def init_db():
    c=db(); c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, name TEXT, description TEXT, owner TEXT, path TEXT, status TEXT, created_at TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, owner TEXT, type TEXT, status TEXT, progress INTEGER, result TEXT, error TEXT, created_at TEXT, started_at TEXT, completed_at TEXT);
    CREATE TABLE IF NOT EXISTS ai_messages(id INTEGER PRIMARY KEY, user TEXT, role TEXT, content TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS server_profiles(id INTEGER PRIMARY KEY, owner TEXT, name TEXT, url TEXT, api_key TEXT, kind TEXT, active INTEGER, created_at TEXT);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    ''')
    if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
        password=os.getenv('AETHER_OWNER_PASSWORD') or secrets.token_urlsafe(14)
        c.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)',(OWNER,pwh(password),'owner',now())); c.commit()
        print(f'AETHER_INITIAL_OWNER={OWNER}')
        print('AETHER_INITIAL_PASSWORD=generated; set AETHER_OWNER_PASSWORD in Railway Variables')
    c.close()


def jwt(payload):
    payload={**payload,'exp':int(time.time())+86400}
    enc=lambda x:base64.urlsafe_b64encode(json.dumps(x,separators=(',',':')).encode()).rstrip(b'=').decode()
    a=enc({'alg':'HS256','typ':'JWT'}); b=enc(payload)
    sig=base64.urlsafe_b64encode(hmac.new(SECRET,f'{a}.{b}'.encode(),hashlib.sha256).digest()).rstrip(b'=').decode()
    return f'{a}.{b}.{sig}'
def decode(t):
    try:
        a,b,s=t.split('.')
        good=base64.urlsafe_b64encode(hmac.new(SECRET,f'{a}.{b}'.encode(),hashlib.sha256).digest()).rstrip(b'=').decode()
        if not hmac.compare_digest(s,good): raise ValueError()
        p=json.loads(base64.urlsafe_b64decode(b+'=='))
        if p['exp']<time.time(): raise ValueError()
        return p
    except Exception: raise HTTPException(401,'Invalid or expired session')
def user(authorization:Optional[str]=Header(None)):
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401,'Login required')
    return decode(authorization[7:])

def owner_only(u=Depends(user)):
    if u.get('role')!='owner': raise HTTPException(403,'Owner permission required')
    return u

def safe_path(project_id, rel=''):
    c=db(); row=c.execute('SELECT path FROM projects WHERE id=?',(project_id,)).fetchone(); c.close()
    if not row: raise HTTPException(404,'Project not found')
    base=Path(row['path']).resolve(); target=(base/rel).resolve()
    if base!=target and base not in target.parents: raise HTTPException(400,'Path outside project blocked')
    return base,target


def qwen_request(message, history=None):
    url=os.getenv('AETHER_LOCAL_AI_URL','http://127.0.0.1:8090/v1/chat/completions').rstrip('/')
    payload={'model':os.getenv('AETHER_LOCAL_AI_MODEL','Qwen3-0.6B-Q4_K_M.gguf'),'messages':[
        {'role':'system','content':'You are Aether AI, a private local-first assistant. Help with coding, projects, media, Android development and authorized defensive security testing. Never assist unauthorized intrusion, credential theft, malware or destructive actions.'}
    ] + (history or []) + [{'role':'user','content':message}], 'temperature':float(os.getenv('AETHER_AI_TEMPERATURE','0.2')), 'max_tokens':int(os.getenv('AETHER_AI_MAX_TOKENS','384')), 'stream':False}
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+os.getenv('AETHER_LOCAL_AI_KEY','local')},method='POST')
    with urllib.request.urlopen(req,timeout=float(os.getenv('AETHER_AI_TIMEOUT','120'))) as r:
        d=json.loads(r.read().decode())
    return d.get('choices',[{}])[0].get('message',{}).get('content','').strip()

def route(message):
    low=message.lower()
    for keys,name in [(['build apk','apk','android'],'ANDROID_BUILDER'),(['image','photo','picture','png','jpg'],'IMAGE'),(['video','mp4','movie'],'VIDEO'),(['audio','tts','speak','voice'],'TTS'),(['security','scan','apk analysis','authorized'],'SECURITY'),(['terminal','shell','command'],'TERMINAL'),(['project'],'PROJECT'),(['file','upload'],'FILE')]:
        if any(k in low for k in keys): return name
    return 'CHAT'

app=FastAPI(title='Aether AI Server',version='2.0.0')
app.mount('/static',StaticFiles(directory=WEB/'static'),name='static')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

@app.on_event('startup')
def startup():
    init_db()
    print(f'AETHER: data root={DATA}')
    print(f'AETHER: model path={DATA / "models"}')
    print(f'AETHER: FFmpeg={bool(shutil.which("ffmpeg"))}')
    print(f'AETHER: Android builder={bool(shutil.which("gradle"))}')
    print(f'AETHER: TTS={bool(shutil.which("espeak-ng") or shutil.which("espeak"))}')
@app.get('/')
def root(): return FileResponse(WEB/'index.html')
@app.get('/health')
def health():
    total=free=0
    try:
        du=shutil.disk_usage(DATA); total=round(du.total/1e9,2); free=round(du.free/1e9,2)
    except Exception: pass
    return {'server':'Aether AI Server','status':'online','version':'2.0.0','uptime':round(time.time()-START,1),'platform':platform.platform(),'architecture':platform.machine(),'cpu_cores':os.cpu_count(),'storage':{'total_gb':total,'free_gb':free}}
@app.get('/api/health')
def api_health(): return health()
@app.get('/api/config/public')
def public_config():
    def base_url(value): return (value or '').rstrip('/').removesuffix('/health').rstrip('/')
    public=base_url(os.getenv('AETHER_PUBLIC_URL','')); apk=base_url(os.getenv('AETHER_APK_SERVER_URL',public))
    return {'server_url':public,'apk_server_url':apk,'features':{'chat':True,'image':True,'video':True,'tts':True,'security_lab':True,'android_builder':True,'uploads':True,'jobs':True,'streaming':True}}

class Login(BaseModel): username:str; password:str
@app.post('/api/auth/login')
def login(x:Login):
    r=db().execute('SELECT * FROM users WHERE username=?',(x.username,)).fetchone()
    if not r or not verify(x.password,r['password_hash']): raise HTTPException(401,'Invalid credentials')
    return {'token':jwt({'sub':r['username'],'role':r['role']}),'user':{'username':r['username'],'role':r['role']}}
@app.get('/api/auth/me')
def me(u=Depends(user)): return u

class Chat(BaseModel): message:str=Field(min_length=1); project_id:Optional[int]=None
@app.post('/api/chat')
def chat(x:Chat,u=Depends(user)):
    c=db(); c.execute('INSERT INTO ai_messages(user,role,content,created_at) VALUES(?,?,?,?)',(u['sub'],'user',x.message,now()))
    history=[{'role':r['role'],'content':r['content']} for r in c.execute('SELECT role,content FROM ai_messages WHERE user=? ORDER BY id DESC LIMIT 12',(u['sub'],)).fetchall()][::-1]
    r=route(x.message); local=False
    try: reply=qwen_request(x.message,history[:-1]); local=True
    except Exception as e: reply=f'[{r}] Local AI is not currently available. Request accepted by Aether routing. Configure/enable local Qwen or an OpenAI-compatible server. Detail: {type(e).__name__}'
    c.execute('INSERT INTO ai_messages(user,role,content,created_at) VALUES(?,?,?,?)',(u['sub'],'assistant',reply,now())); c.commit()
    plan=AutonomousAgent().plan(x.message)
    return {'text':reply,'route':r,'plan':plan.steps,'status':'completed' if local else 'fallback','local_ai':local}
@app.get('/api/chat/history')
def history(u=Depends(user)):
    return [dict(x) for x in db().execute('SELECT role,content,created_at FROM ai_messages WHERE user=? ORDER BY id DESC LIMIT 100',(u['sub'],)).fetchall()][::-1]

class ServerIn(BaseModel): name:str; url:str; api_key:str=''; kind:str='custom'; active:bool=False
@app.get('/api/servers')
def servers(u=Depends(user)): return [dict(x) for x in db().execute('SELECT id,name,url,kind,active,created_at FROM server_profiles WHERE owner=? ORDER BY id DESC',(u['sub'],)).fetchall()]
@app.post('/api/servers')
def add_server(x:ServerIn,u=Depends(user)):
    if not re.match(r'^https?://[^\s]+$',x.url): raise HTTPException(422,'URL must start with http:// or https://')
    c=db();
    if x.active: c.execute('UPDATE server_profiles SET active=0 WHERE owner=?',(u['sub'],))
    c.execute('INSERT INTO server_profiles(owner,name,url,api_key,kind,active,created_at) VALUES(?,?,?,?,?,?,?)',(u['sub'],x.name,x.url.rstrip('/'),x.api_key,x.kind,int(x.active),now())); c.commit(); return {'ok':True}
@app.post('/api/servers/{sid}/activate')
def activate(sid:int,u=Depends(user)):
    c=db(); c.execute('UPDATE server_profiles SET active=0 WHERE owner=?',(u['sub'],)); c.execute('UPDATE server_profiles SET active=1 WHERE id=? AND owner=?',(sid,u['sub'])); c.commit(); return {'ok':True}
@app.delete('/api/servers/{sid}')
def delete_server(sid:int,u=Depends(user)):
    c=db(); c.execute('DELETE FROM server_profiles WHERE id=? AND owner=?',(sid,u['sub'])); c.commit(); return {'ok':True}

class ProjectIn(BaseModel): name:str; description:str=''
@app.post('/api/projects-v2')
def create_project(x:ProjectIn,u=Depends(user)):
    slug=re.sub(r'[^a-zA-Z0-9_-]','-',x.name).strip('-')[:48] or 'project'; base=(WORKSPACE/f'{slug}-{int(time.time())}').resolve(); base.mkdir(parents=True)
    c=db(); c.execute('INSERT INTO projects(name,description,owner,path,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(x.name,x.description,u['sub'],str(base),'ready',now(),now())); pid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; c.commit(); return {'id':pid,'name':x.name,'path':str(base)}
@app.get('/api/projects-v2')
def projects(u=Depends(user)): return [dict(x) for x in db().execute('SELECT id,name,description,owner,status,created_at,updated_at FROM projects WHERE owner=? ORDER BY id DESC',(u['sub'],)).fetchall()]
@app.get('/api/projects-v2/{pid}')
def project(pid:int,u=Depends(user)):
    r=db().execute('SELECT * FROM projects WHERE id=? AND owner=?',(pid,u['sub'])).fetchone()
    if not r: raise HTTPException(404,'Project not found')
    return dict(r)
@app.delete('/api/projects-v2/{pid}')
def del_project(pid:int,u=Depends(user)):
    r=db().execute('SELECT path FROM projects WHERE id=? AND owner=?',(pid,u['sub'])).fetchone()
    if not r: raise HTTPException(404,'Project not found')
    shutil.rmtree(r['path'],ignore_errors=True); c=db(); c.execute('DELETE FROM projects WHERE id=?',(pid,)); c.commit(); return {'ok':True}
@app.get('/api/project-files/{pid}/tree')
def tree(pid:int,u=Depends(user)):
    base,_=safe_path(pid,''); return {'files':[str(p.relative_to(base)) for p in base.rglob('*') if p.is_file()][:1000]}

@app.get('/api/system-v2/info')
def sysinfo(u=Depends(user)):
    checks={x:bool(shutil.which(x)) for x in ['python3','node','java','ffmpeg','ffprobe','clang','gradle','adb']}
    du=shutil.disk_usage(DATA)
    return {'os':platform.platform(),'architecture':platform.machine(),'cpu':os.cpu_count(),'storage_free_gb':round(du.free/1e9,2),'storage_total_gb':round(du.total/1e9,2),'binaries':checks,'local_ai':{'url':os.getenv('AETHER_LOCAL_AI_URL','http://127.0.0.1:8090/v1/chat/completions'),'model':os.getenv('AETHER_LOCAL_AI_MODEL','Qwen3-0.6B-Q4_K_M.gguf')}}

def builder(u):
    return {'java':bool(shutil.which('java')),'gradle':bool(shutil.which('gradle')),'android_sdk':bool(os.getenv('ANDROID_HOME') or os.getenv('ANDROID_SDK_ROOT')),'adb':bool(shutil.which('adb')),'message':'READY' if shutil.which('java') and shutil.which('gradle') else 'NEEDS TOOLCHAIN'}
@app.get('/api/system-v2/builder')
def builder2(u=Depends(user)): return builder(u)
@app.get('/api/builder/status')
def builder_status(u=Depends(user)): return builder(u)
@app.get('/api/jobs-v2')
def jobs(u=Depends(user)): return [dict(x) for x in db().execute('SELECT * FROM jobs WHERE owner=? ORDER BY created_at DESC LIMIT 100',(u['sub'],)).fetchall()]

@app.post('/api/terminal/run')
def terminal(command:str=Form(...),u=Depends(user)):
    if u.get('role') not in ('owner','admin','developer'): raise HTTPException(403,'Developer role required')
    parts=command.strip().split(); allowed={'python','python3','pip','pip3','node','npm','npx','java','javac','gradle','ffmpeg','ffprobe','clang','gcc','g++','git','ls','pwd','find','cat','head','tail','grep','sed','wc','mkdir','cp','mv','touch','zip','unzip'}
    blocked=('rm -rf /','mkfs','dd if=','fork','shutdown','reboot','sudo',' su ','curl | sh','wget | sh')
    sensitive=('/etc','/root','/proc','/sys','/dev','/run','/var/run','/var/lib','/home/ubuntu/.ssh')
    metachar=(';','&&','||','|','`','$(','>','<')
    if (not parts or parts[0] not in allowed or any(x in command for x in blocked)
            or any(x in command for x in sensitive) or any(x in command for x in metachar)):
        raise HTTPException(400,'Command blocked by workspace allowlist')
    p=subprocess.run(parts,cwd=WORKSPACE,capture_output=True,text=True,timeout=60); return {'stdout':p.stdout[-16000:],'stderr':p.stderr[-16000:],'exit_code':p.returncode}

@app.get('/api/system/status')
def system_status(u=Depends(user)): return sysinfo(u)
@app.get('/api/ai/status')
def ai_status(u=Depends(user)):
    url=os.getenv('AETHER_LOCAL_AI_URL','http://127.0.0.1:8090/v1/chat/completions'); base=url.split('/v1/',1)[0]
    try:
        urllib.request.urlopen(urllib.request.Request(base+'/health'),timeout=2); online=True; error=None
    except Exception as e: online=False; error=str(e)
    return {'primary':'local_qwen','configured':True,'online':online,'url':url,'model':os.getenv('AETHER_LOCAL_AI_MODEL','Qwen3-0.6B-Q4_K_M.gguf'),'error':error}
@app.get('/api/image/status')
def image_status(u=Depends(user)):
    try: import PIL; ok=True; version=PIL.__version__
    except Exception: ok=False; version=None
    marker=DATA/'stable-diffusion-ready'; status='ready' if marker.exists() else ((DATA/'stable-diffusion.status').read_text().strip() if (DATA/'stable-diffusion.status').exists() else 'unavailable')
    return {'engine':'Aether Pillow generator','available':ok,'version':version,'stable_diffusion':{'status':status,'model':'runwayml/stable-diffusion-v1-5'},'message':'READY' if ok else 'INSTALL Pillow'}
@app.get('/api/tts/status')
def tts_status(u=Depends(user)):
    engines={x:bool(shutil.which(x)) for x in ('termux-tts-speak','espeak','espeak-ng','pico2wave')}
    return {'available':any(engines.values()),'engines':engines,'languages':['hi','en','hinglish'],'message':'READY' if any(engines.values()) else 'BROWSER TTS AVAILABLE'}
class TTSRequest(BaseModel): text:str=Field(min_length=1,max_length=5000); language:str='en'; speed:float=1.0
@app.post('/api/media/tts')
def make_tts(x:TTSRequest,u=Depends(user)):
    engine=shutil.which('espeak-ng') or shutil.which('espeak')
    if not engine: raise HTTPException(503,'No server TTS engine installed; browser TTS remains available')
    voice='hi' if x.language.lower().startswith('hi') else 'en'
    speed=max(80,min(450,int(175*max(0.5,min(2.0,x.speed)))))
    name=f'audio-{secrets.token_hex(8)}.wav'; out=MEDIA/name
    p=subprocess.run([engine,'-v',voice,'-s',str(speed),'-w',str(out),x.text],capture_output=True,text=True,timeout=60)
    if p.returncode or not out.is_file(): raise HTTPException(500,p.stderr[-1000:] or 'TTS generation failed')
    return {'ok':True,'type':'audio','filename':name,'url':'/media/'+name,'engine':Path(engine).name}
@app.get('/api/security/status')
def security_status(u=Depends(user)):
    from security_lab.apk.analyzer import tools as apk_tools
    return {'available':True,'scope':'owned apps, owned servers, local sandbox and explicitly authorized targets only','apk_tools':apk_tools(),'internet_wide_scanning':False,'offensive_bypass':False}
@app.get('/api/tools/status')
def tools_status(u=Depends(user)): return snapshot()

@app.post('/api/security/apk/analyze')
async def apk_analyze(file:UploadFile=File(...),u=Depends(user)):
    if not file.filename.lower().endswith('.apk'): raise HTTPException(422,'APK file required')
    dest=(UPLOADS/f'{secrets.token_hex(12)}-{Path(file.filename).name}').resolve(); dest.write_bytes(await file.read())
    try: return analyze_apk(str(dest))
    except Exception as e: raise HTTPException(400,str(e))
class AuthorizedCheck(BaseModel): kind:str; target:str=''; expected_sha256:Optional[str]=None
@app.post('/api/security/authorized-check')
def authorized_check(x:AuthorizedCheck,u=Depends(user)):
    if x.kind=='apk_integrity': return apk_integrity(x.target,x.expected_sha256)
    if x.kind=='apk_surface': return apk_surface(x.target)
    if x.kind=='api_target_guard': return api_target_guard(x.target)
    if x.kind=='toolchain': return {'check':'toolchain','status':'completed','tools':toolchain_status()}
    raise HTTPException(422,'Unknown defensive check')

class MediaRequest(BaseModel): prompt:str=Field(min_length=1,max_length=2000); width:int=768; height:int=768; duration:int=5
@app.post('/api/media/image')
def make_image(x:MediaRequest,u=Depends(user)):
    try: from PIL import Image,ImageDraw,ImageFont
    except Exception as e: raise HTTPException(503,'Pillow not installed')
    w=max(256,min(x.width,1536)); h=max(256,min(x.height,1536)); seed=int(hashlib.sha256(x.prompt.encode()).hexdigest()[:8],16)
    name=f'image-{secrets.token_hex(8)}.png'; path=MEDIA/name
    if (DATA/'stable-diffusion-ready').exists() and os.getenv('AETHER_PREFER_STABLE_DIFFUSION','1') == '1':
        try:
            from ai.stable_diffusion import generate
            engine=generate(x.prompt,w,h,path)
            return {'ok':True,'type':'image','filename':name,'url':'/media/'+name,'engine':engine}
        except Exception as exc:
            # Never claim SD success; retain a clearly labelled procedural fallback.
            sd_error=f'{type(exc).__name__}: {exc}'
    else:
        sd_error=None
    bg=((seed>>16)&255,(seed>>8)&255,seed&255); im=Image.new('RGB',(w,h),bg); d=ImageDraw.Draw(im)
    for i in range(12):
        r=(seed*(i+3))%min(w,h)//3; cx=(seed*(i+7))%w; cy=(seed*(i+11))%h; d.ellipse((cx-r,cy-r,cx+r,cy+r),outline=(255,255,255),width=max(2,w//300))
    try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',max(18,w//32))
    except Exception: font=ImageFont.load_default()
    text=x.prompt[:300]; d.multiline_text((w//12,h//2),text,fill='white',font=font,spacing=12)
    im.save(path,'PNG'); engine='local procedural image generator'
    if sd_error: engine += f' (Stable Diffusion fallback: {sd_error})'
    return {'ok':True,'type':'image','filename':name,'url':'/media/'+name,'engine':engine}
@app.post('/api/media/video')
def make_video(x:MediaRequest,u=Depends(user)):
    if not shutil.which('ffmpeg'): raise HTTPException(503,'FFmpeg not installed')
    # Generate a simple visual frame through the local image endpoint logic.
    try: from PIL import Image,ImageDraw
    except Exception: raise HTTPException(503,'Pillow not installed')
    w=max(320,min(x.width,1280)); h=max(180,min(x.height,720)); seed=int(hashlib.sha256(x.prompt.encode()).hexdigest()[:8],16); bg=((seed>>16)&255,(seed>>8)&255,seed&255)
    img=Image.new('RGB',(w,h),bg); ImageDraw.Draw(img).text((30,h//2),x.prompt[:180],fill='white')
    frame=MEDIA/f'frame-{secrets.token_hex(8)}.png'; img.save(frame)
    name=f'video-{secrets.token_hex(8)}.mp4'; out=MEDIA/name; dur=max(1,min(x.duration,60))
    p=subprocess.run(['ffmpeg','-y','-loop','1','-i',str(frame),'-t',str(dur),'-r','24','-pix_fmt','yuv420p','-c:v','libx264','-movflags','+faststart',str(out)],capture_output=True,text=True,timeout=180)
    frame.unlink(missing_ok=True)
    if p.returncode: raise HTTPException(500,p.stderr[-2000:])
    return {'ok':True,'type':'video','filename':name,'url':'/media/'+name,'engine':'FFmpeg local video generator'}

app.mount('/media',StaticFiles(directory=MEDIA),name='media')
app.include_router(extended_router)

if __name__=='__main__': init_db()
