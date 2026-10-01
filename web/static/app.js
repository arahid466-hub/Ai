const root = document.getElementById('app');
let token = localStorage.getItem('aether_token');
let me = JSON.parse(localStorage.getItem('aether_me') || 'null');

const SERVER_URL = 'https://ai-production-df18.up.railway.app';
const api = async (path, opt = {}) => {
  opt.headers = { ...(opt.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const r = await fetch(path, opt);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(d.detail || 'Request failed');
  return d;
};

function login() {
  root.innerHTML = `<div class="login-page">
    <div class="login-orbit orbit-one"></div><div class="login-orbit orbit-two"></div>
    <div class="login-layout">
      <section class="login-showcase">
        <div class="brand brand-large"><div class="orb"><span>✦</span></div><span>AETHER <b>AI</b></span></div>
        <div class="eyebrow">D2D · DIRECT TO DIALOGUE</div>
        <h1>Think it.<br><span>Chat it.</span><br>Build it.</h1>
        <p class="showcase-copy">A colorful private command center for ideas, code, projects and creative work — connected to your Railway server.</p>
        <div class="feature-row"><span>◉ Local-first</span><span>✦ Creative</span><span>⌁ Secure</span></div>
      </section>
      <section class="card login-card">
        <div class="login-card-top"><span class="live-dot"></span><span>RAILWAY SERVER ONLINE</span></div>
        <h2>Welcome back</h2><p class="muted">Sign in to your Aether D2D workspace.</p>
        <label class="field-label">USERNAME</label><input id="u" class="input" placeholder="Username" value="owner" autocomplete="username">
        <label class="field-label">PASSWORD</label><input id="p" class="input" placeholder="Password" type="password" autocomplete="current-password" onkeydown="if(event.key==='Enter')doLogin()">
        <button class="send login-button" onclick="doLogin()"><span>Enter workspace</span><b>→</b></button>
        <p id="err" class="danger"></p>
        <div class="server-chip"><span class="server-icon">⌁</span><span><small>CONNECTED SERVER</small><b>${SERVER_URL}</b></span></div>
      </section>
    </div>
  </div>`;
}

async function doLogin() {
  const button = document.querySelector('.login-button');
  if (button) button.classList.add('loading');
  try {
    const d = await api('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: u.value, password: p.value }) });
    token = d.token; me = d.user;
    localStorage.setItem('aether_token', token); localStorage.setItem('aether_me', JSON.stringify(me)); render();
  } catch (e) { err.textContent = e.message; } finally { if (button) button.classList.remove('loading'); }
}

function render() {
  root.innerHTML = `<div class="shell">
    <aside class="side"><div class="brand"><div class="orb"><span>✦</span></div><span>AETHER <b>AI</b></span></div>
      <div class="d2d-badge"><span class="live-dot"></span><div><b>D2D CHAT</b><small>DIRECT TO DIALOGUE</small></div></div>
      <div class="nav"><button class="active" onclick="render()"><i>◈</i> Command center</button><button onclick="projects()"><i>▣</i> Projects</button><button onclick="servers()"><i>◉</i> Server URL</button><button onclick="media()"><i>✦</i> Media studio</button><button onclick="system()"><i>⌁</i> System health</button></div>
      <div class="profile"><div class="avatar">${esc((me.username || 'A')[0]).toUpperCase()}</div><div><b>${esc(me.username)}</b><div class="muted">${esc(me.role)} · protected</div></div><button class="ghost" onclick="logout()">Sign out</button></div>
    </aside>
    <main class="main"><header class="top"><div><div class="eyebrow">AETHER D2D WORKSPACE</div><h1>Command center</h1></div><span class="pill"><span class="live-dot"></span> ONLINE</span></header>
      <section class="content"><div class="welcome"><div><p class="eyebrow">YOUR CREATIVE COPILOT</p><h2>What are we building<br><span>today?</span></h2><p>One colorful chat for code, projects, Android, media and authorized security work.</p></div><div class="welcome-spark">✦</div></div>
        <div class="chips"><button class="chip chip-cyan" onclick="fill('Show system status')"><b>⌁</b> System status</button><button class="chip chip-violet" onclick="fill('Create a Python project')"><b>▣</b> Create project</button><button class="chip chip-pink" onclick="fill('Build my APK')"><b>◆</b> Android builder</button><button class="chip chip-gold" onclick="media()"><b>✦</b> Generate media</button><button class="chip" onclick="files()"><b>⇧</b> Upload file</button><button class="chip" onclick="jobs()"><b>◌</b> Job status</button></div>
        <div id="messages" class="messages"></div>
        <div class="composer"><div class="composer-glow"></div><textarea id="box" placeholder="Message Aether… Hindi, English, Hinglish" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}"></textarea><div class="composer-foot"><span class="muted"><span class="pulse"></span> D2D is ready · Shift + Enter for a new line</span><button class="send" onclick="send()">Send <b>↗</b></button></div></div>
      </section>
    </main>
  </div>`;
  loadHistory();
}

function fill(x) { box.value = x; box.focus(); }
async function files() { root.innerHTML = `<div class="login"><div class="card wide-card"><div class="row"><div><div class="eyebrow">D2D FILE VAULT</div><h1>Files & documents</h1></div><button class="ghost" onclick="render()">Back</button></div><p class="muted">Upload documents to this authenticated Railway workspace.</p><input id="fileInput" class="input" type="file" multiple><button class="send" onclick="uploadFiles()">Upload selected files →</button><div id="fileResults" class="messages"></div></div></div>`; try { const list = await api('/api/files'); fileResults.innerHTML = list.map(f => `<div class="msg assistant"><span class="msg-avatar">⇧</span><div>${esc(f.name)}<small class="msg-meta">${f.size} bytes · ${esc(f.created_at || '')}</small></div></div>`).join(''); } catch(e) {} }
async function uploadFiles() { const result = document.getElementById('fileResults'); for (const file of fileInput.files) { const form = new FormData(); form.append('file', file); try { const d = await api('/api/files/upload', { method: 'POST', body: form }); result.innerHTML += `<div class="msg assistant"><span class="msg-avatar">✓</span><div>Uploaded ${esc(d.file.name)}<small class="msg-meta">${d.file.size} bytes</small></div></div>`; } catch(e) { result.innerHTML += `<div class="msg assistant danger">${esc(e.message)}</div>`; } } }
async function jobs() { const list = await api('/api/jobs'); root.innerHTML = `<div class="login"><div class="card wide-card"><div class="row"><div><div class="eyebrow">D2D OPERATIONS</div><h1>Job status</h1></div><button class="ghost" onclick="render()">Back</button></div><div class="messages">${list.length ? list.map(j => `<div class="msg assistant"><span class="msg-avatar">◌</span><div><b>${esc(j.type)}</b><small class="msg-meta">${esc(j.status)} · ${j.progress}% · ${esc(j.job_id)}</small></div></div>`).join('') : '<p class="muted">No background jobs yet.</p>'}</div></div></div>`; }

async function loadHistory() { try { const h = await api('/api/chat/history'); messages.innerHTML = h.map(messageHtml).join(''); messages.scrollTop = messages.scrollHeight; } catch (e) {} }
function messageHtml(x) { return `<div class="msg ${x.role}"><span class="msg-avatar">${x.role === 'user' ? 'YOU' : '✦'}</span><div>${esc(x.content)}</div></div>`; }
async function send() {
  const text = box.value.trim(); if (!text) return;
  messages.innerHTML += messageHtml({ role: 'user', content: text }); box.value = ''; messages.scrollTop = messages.scrollHeight;
  try { const d = await api('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text }) }); messages.innerHTML += `<div class="msg assistant"><span class="msg-avatar">✦</span><div>${esc(d.text)}<small class="msg-meta">${esc(d.route)} · ${esc(d.status)}</small></div></div>`; }
  catch (e) { messages.innerHTML += `<div class="msg assistant danger"><span class="msg-avatar">!</span><div>${esc(e.message)}</div></div>`; }
  messages.scrollTop = messages.scrollHeight;
}
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function logout() { localStorage.clear(); token = null; me = null; login(); }

async function servers() { const s = await api('/api/servers'); root.innerHTML = `<div class="login"><div class="card wide-card"><div class="row"><div><div class="eyebrow">D2D CONNECTIONS</div><h1>Server URL</h1></div><button class="ghost" onclick="render()">Back</button></div><p class="muted">Your APK is centrally connected to <b>${SERVER_URL}</b>.</p><input id="sn" class="input" placeholder="Profile name" value="Railway"><input id="su" class="input" placeholder="https://your-app.up.railway.app"><input id="sk" class="input" placeholder="Optional API key" type="password"><select id="st" class="input"><option value="public">Public host</option><option value="vip">VIP/private host</option><option value="custom">Custom</option></select><button class="send" onclick="addServer()">Add and activate →</button><div id="list">${s.map(x => `<div class="server"><strong>${esc(x.name)} ${x.active ? ' · ACTIVE' : ''}</strong><span class="muted">${esc(x.url)} · ${esc(x.kind)}</span><br><button class="ghost" onclick="activateServer(${x.id})">Use this</button></div>`).join('')}</div></div></div>`; }
async function addServer() { await api('/api/servers', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: sn.value, url: su.value, api_key: sk.value, kind: st.value, active: true }) }); servers(); }
async function activateServer(id) { await api('/api/servers/' + id + '/activate', { method: 'POST' }); servers(); }
async function projects() { const p = await api('/api/projects-v2'); root.innerHTML = `<div class="login"><div class="card wide-card"><div class="row"><div><div class="eyebrow">D2D WORKSPACE</div><h1>Projects</h1></div><button class="ghost" onclick="render()">Back</button></div>${p.length ? p.map(x => `<div class="server"><strong>${esc(x.name)}</strong><span class="muted">${esc(x.status)} · ${esc(x.path || '')}</span></div>`).join('') : '<p class="muted">No projects yet. Ask Aether to create one.</p>'}</div></div>`; }
async function media() { root.innerHTML = `<div class="login"><div class="card wide-card"><div class="row"><div><div class="eyebrow">D2D CREATIVE STUDIO</div><h1>Media generator</h1></div><button class="ghost" onclick="render()">Back</button></div><input id="mp" class="input" placeholder="Describe the image/video"><div class="row"><input id="mw" class="input" value="768" type="number"><input id="mh" class="input" value="768" type="number"><input id="md" class="input" value="5" type="number"></div><div class="row"><button class="send" onclick="genImage()">Generate PNG</button><button class="send" onclick="genVideo()">Generate MP4</button></div><div id="mr" class="messages"></div></div></div>`; }
async function genImage() { const d = await api('/api/media/image', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: mp.value, width: +mw.value, height: +mh.value, duration: 5 }) }); mr.innerHTML = `<div class="msg assistant">PNG ready: <a href="${d.url}" target="_blank">${esc(d.filename)}</a><br><span class="muted">${esc(d.engine)}</span></div>`; }
async function genVideo() { const d = await api('/api/media/video', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: mp.value, width: +mw.value, height: +mh.value, duration: +md.value }) }); mr.innerHTML = `<div class="msg assistant">MP4 ready: <a href="${d.url}" target="_blank">${esc(d.filename)}</a><br><span class="muted">${esc(d.engine)}</span></div>`; }
async function system() { const [s, b, a, i, t] = await Promise.all([api('/api/system-v2/info'), api('/api/system-v2/builder'), api('/api/ai/status'), api('/api/image/status'), api('/api/tts/status')]); alert(`AETHER D2D SYSTEM\nCPU: ${s.cpu}\nArch: ${s.architecture}\nFree: ${s.storage_free_gb} GB\n\nLOCAL AI: ${a.online ? 'ONLINE' : 'OFFLINE'}\nIMAGE: ${i.available ? 'READY' : 'UNAVAILABLE'}\nTTS: ${t.available ? 'READY' : 'BROWSER TTS'}\n\nANDROID BUILDER\nJava: ${b.java}\nGradle: ${b.gradle}\nSDK: ${b.android_sdk}\nadb: ${b.adb}`); }

token ? render() : login();
