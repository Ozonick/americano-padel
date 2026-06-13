/**
 * app.js — Núcleo de la aplicación
 * Estado global, WebSocket, autenticación, navegación, utilidades y keep-alive.
 */

// ── Estado global ─────────────────────────────────────────────────────────────
const S = {
  role:    'viewer',   // 'viewer' | 'admin' | 'superadmin'
  password: '',
  tab:     'fixture',
  state:   null,       // último estado del servidor (torneo principal)
  mex:     null,       // estado del modo mexicano
  tri:     null,       // estado del modo triangular (localStorage)
  torneo:  null,       // estado del torneo de parejas (server)
  ws:      null,
  jugadores_edit: [],
  canchaVista: 'todas',
  keepAlive:   false,
  _kaTimer:    null,
  modosHabilitados: { mexicano: true, triangular: true },
};

const LETRAS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';

const COLORES = [
  { bg: 'rgba(41,171,226,.16)',  brd: 'rgba(41,171,226,.45)',  txt: '#29ABE2' },
  { bg: 'rgba(255,215,0,.16)',   brd: 'rgba(255,215,0,.5)',    txt: '#D4A800' },
  { bg: 'rgba(255,255,255,.08)', brd: 'rgba(255,255,255,.25)', txt: '#cccccc' },
  { bg: 'rgba(255,69,58,.14)',   brd: 'rgba(255,69,58,.35)',   txt: '#ff6b62' },
  { bg: 'rgba(191,90,242,.14)',  brd: 'rgba(191,90,242,.35)',  txt: '#bf5af2' },
  { bg: 'rgba(100,210,255,.14)', brd: 'rgba(100,210,255,.35)', txt: '#64d2ff' },
];


// ── Roles ─────────────────────────────────────────────────────────────────────
function esAdmin() { return S.role === 'admin' || S.role === 'superadmin'; }
function esSuper() { return S.role === 'superadmin'; }


// ── WebSocket ─────────────────────────────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws    = new WebSocket(`${proto}://${location.host}/ws`);
  S.ws = ws;

  ws.onopen = () => {
    document.getElementById('ws-dot').classList.add('ok');
    S._ping = setInterval(() => { if (ws.readyState === 1) ws.send('ping'); }, 20000);
  };

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'state')          applyStateSafe(data);
    if (data.type === 'mexicano_state') { S.mex = data; if (S.tab === 'mexicano') renderTab(); }
    if (data.type === 'torneo_state')   { S.torneo = data; if (S.tab === 'torneo') renderTab(); }
    // pings del server se ignoran silenciosamente
  };

  ws.onclose = () => {
    document.getElementById('ws-dot').classList.remove('ok');
    clearInterval(S._ping);
    setTimeout(connectWS, 2000);
  };
}

function applyStateSafe(data) {
  S.state = data;
  const focused = document.activeElement;
  applyState(data, focused?.classList.contains('g-in'));
}

function applyState(data, skipFixtureRender = false) {
  const cfg = data.config || {};

  // Header
  document.getElementById('hdr-nombre').textContent =
    cfg.torneo_nombre || 'Panteras Pádel';
  document.getElementById('hdr-sub').textContent =
    `${data.jugadores?.length || 0} jugadores · ${cfg.canchas || '?'} canchas`;

  // Parámetros sidebar
  document.getElementById('p-canchas').textContent  = cfg.canchas       || '—';
  document.getElementById('p-games').textContent    = cfg.games_partido || '—';
  document.getElementById('p-rondas').textContent   = cfg.rondas_prel   || '—';
  document.getElementById('p-rondas-f').textContent = cfg.rondas_final  || '—';

  // Submenú de canchas (fixture)
  const grupos_count = (data.grupos || []).length;
  const submenu = document.getElementById('submenu-canchas');
  if (submenu) {
    const colores = ['#29ABE2','#D4A800','#aaa','#ff6b62','#bf5af2','#64d2ff'];
    let sm = `<button class="nav-btn sub-cancha-btn ${S.canchaVista === 'todas' ? 'active' : ''}"
      data-cancha="todas" onclick="setFixtureView('todas')" style="font-size:12px;padding:6px 12px">
      <span style="margin-right:6px;opacity:.5">└</span> Ver todas</button>`;
    for (let gi = 0; gi < grupos_count; gi++) {
      const col = colores[gi % colores.length];
      sm += `<button class="nav-btn sub-cancha-btn ${S.canchaVista === gi ? 'active' : ''}"
        data-cancha="${gi}" onclick="setFixtureView(${gi})"
        style="font-size:12px;padding:6px 12px;border-left:3px solid ${col}">
        <span style="margin-right:6px;opacity:.5">└</span> Cancha ${gi + 1}</button>`;
    }
    submenu.innerHTML = sm;
  }

  // Sugerencia de rondas
  if (data.sugerencia) {
    const s   = data.sugerencia;
    const box = document.getElementById('hint-tiempo');
    box.style.display = 'block';
    box.innerHTML = `⏱ <strong>${cfg.tiempo_cancha || 90} min</strong> de cancha<br>
      Sugerido: <strong>${s.rondas_prel} rondas</strong> prel + ${s.rondas_final} final<br>
      ~${s.mins_x_partido} min/partido · Tiempo est: ${s.tiempo_total_est} min`;
  }

  if (skipFixtureRender && S.tab === 'fixture') updatePtsChips(data);
  else renderTab();
}

function updatePtsChips(data) {
  const { grupos, fixtures_prel, resultados } = data;
  if (!grupos) return;
  grupos.forEach((grupo, gi) => {
    (fixtures_prel[gi] || []).forEach(([j1, j2, j3, j4], ri) => {
      const res = (resultados || {})[`prel-${gi}-${ri}`] || {};
      if (res.ga == null || res.gb == null) return;
      const ga = +res.ga, gb = +res.gb;
      const p1 = ga > gb ? '3pts' : ga === gb ? '1pt' : '0pts';
      const p2 = gb > ga ? '3pts' : ga === gb ? '1pt' : '0pts';
      const el = document.getElementById(`chips-${gi}-${ri}`);
      if (el) el.innerHTML = chipsHTML(p1, p2);
    });
  });
}


// ── Navegación ────────────────────────────────────────────────────────────────
function setFixtureView(cancha) {
  S.tab = 'fixture';
  S.canchaVista = cancha;
  document.querySelectorAll('.sub-cancha-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.cancha == String(cancha))
  );
  document.getElementById('nav-fixture')?.classList.add('active');
  closeSidebar();
  renderTab();
}

function setTab(tab) {
  S.tab = tab;
  if (tab !== 'fixture') S.canchaVista = 'todas';
  ['fixture','posiciones','finales','mexicano','triangular','torneo','config','jugadores'].forEach(t => {
    document.getElementById(`nav-${t}`)?.classList.toggle('active', t === tab);
  });
  closeSidebar();
  renderTab();
}

function renderTab() {
  const el = document.getElementById('main-content');
  if (!S.state) {
    el.innerHTML = '<div class="empty"><div class="spinner"></div></div>';
    return;
  }
  const map = {
    fixture:     renderFixture,
    posiciones:  renderPosiciones,
    finales:     renderFinales,
    mexicano:    renderMexicano,
    triangular:  renderTriangular,
    torneo:      () => esSuper() ? renderTorneo()    : noAccess(),
    config:      () => esAdmin() ? renderConfig()    : noAccess(),
    jugadores:   () => esAdmin() ? renderJugadores() : noAccess(),
  };
  if (map[S.tab]) el.innerHTML = map[S.tab]();
}


// ── Auth ──────────────────────────────────────────────────────────────────────
function showLogin() {
  if (esAdmin()) {
    S.role = 'viewer'; S.password = '';
    try { localStorage.removeItem('auth'); } catch(e) {}
    updateRoleUI(); renderTab();
    return;
  }
  document.getElementById('login-wrap').style.display = 'flex';
  document.getElementById('login-pass').value = '';
  document.getElementById('login-err').textContent = '';
  setTimeout(() => document.getElementById('login-pass').focus(), 50);
}
function hideLogin() { document.getElementById('login-wrap').style.display = 'none'; }

async function doLogin() {
  const pass = document.getElementById('login-pass').value;
  const res  = await fetch('/api/auth', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: pass }),
  });
  if (res.ok) {
    const data = await res.json();
    S.role = data.role || 'admin'; S.password = pass;
    try { localStorage.setItem('auth', JSON.stringify({ role: S.role, password: pass })); } catch(e) {}
    hideLogin(); updateRoleUI(); renderTab();
    toast(S.role === 'superadmin' ? '✓ Modo Super Admin activado' : '✓ Modo admin activado');
  } else {
    document.getElementById('login-err').textContent = 'Contraseña incorrecta';
  }
}

async function restaurarAuth() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem('auth') || 'null'); } catch(e) {}
  if (!saved || !saved.password) return;
  try {
    const res = await fetch('/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: saved.password }),
    });
    if (res.ok) {
      const data = await res.json();
      S.role = data.role || 'admin';
      S.password = saved.password;
      updateRoleUI(); renderTab();
    } else {
      localStorage.removeItem('auth');
    }
  } catch(e) { /* sin conexión: se reintenta en la próxima carga */ }
}

function updateRoleUI() {
  const badge    = document.getElementById('role-badge');
  const adminSec = document.getElementById('sidebar-admin');
  const loginBtn = document.querySelector('.hdr-right .btn-ghost');
  const navTorneo = document.getElementById('nav-torneo');
  if (esAdmin()) {
    badge.textContent = esSuper() ? 'Super Admin' : 'Admin';
    badge.className = 'role-badge role-admin';
    adminSec.style.display = 'block';
    if (navTorneo) navTorneo.style.display = esSuper() ? '' : 'none';
    if (loginBtn) loginBtn.textContent = 'Salir admin';
    _aplicarKeepAlive();
  } else {
    badge.textContent = 'Viewer'; badge.className = 'role-badge role-viewer';
    adminSec.style.display = 'none';
    if (navTorneo) navTorneo.style.display = 'none';
    if (loginBtn) loginBtn.textContent = 'Admin';
  }
}


// ── Keep-alive ────────────────────────────────────────────────────────────────
function toggleKeepAlive() {
  S.keepAlive = !S.keepAlive;
  try { localStorage.setItem('ka', '' + S.keepAlive); } catch(e) {}
  _aplicarKeepAlive();
}

function _aplicarKeepAlive() {
  const dot = document.getElementById('ka-dot');
  const lbl = document.getElementById('ka-label');
  const btn = document.getElementById('btn-keepalive');
  clearInterval(S._kaTimer);
  if (S.keepAlive) {
    if (dot) dot.style.background = '#39FF14';
    if (lbl) lbl.textContent = 'Servidor activo 🟢';
    if (btn) { btn.style.borderColor = '#39FF14'; btn.style.color = '#39FF14'; }
    S._kaTimer = setInterval(() => fetch('/api/ping').catch(() => {}), 4 * 60 * 1000);
    fetch('/api/ping').catch(() => {});
  } else {
    if (dot) dot.style.background = 'var(--txt3)';
    if (lbl) lbl.textContent = 'Mantener activo';
    if (btn) { btn.style.borderColor = ''; btn.style.color = ''; }
  }
}


// ── Modos visibles ────────────────────────────────────────────────────────────
function toggleModo(modo, habilitado) {
  S.modosHabilitados[modo] = habilitado;
  try { localStorage.setItem('modos', JSON.stringify(S.modosHabilitados)); } catch(e) {}
  const btn = document.getElementById(`nav-${modo}`);
  if (btn) btn.style.display = habilitado ? '' : 'none';
  if (!habilitado && S.tab === modo) setTab('fixture');
}

function restaurarModos() {
  try {
    const saved = JSON.parse(localStorage.getItem('modos') || '{}');
    Object.assign(S.modosHabilitados, saved);
  } catch(e) {}
  ['mexicano', 'triangular'].forEach(modo => {
    const btn = document.getElementById(`nav-${modo}`);
    const chk = document.getElementById(`toggle-${modo}`);
    const hab = S.modosHabilitados[modo] !== false;
    if (btn) btn.style.display = hab ? '' : 'none';
    if (chk) chk.checked = hab;
  });
}


// ── Utilidades ────────────────────────────────────────────────────────────────
async function api(path, body) {
  try {
    const res = await fetch(path, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    if (!res.ok) {
      const e = await res.json();
      toast('Error: ' + (e.detail || res.status));
      return { ok: false };
    }
    return await res.json();
  } catch(e) {
    toast('Error de conexión');
    return { ok: false };
  }
}

function chipsHTML(p1, p2) {
  const cs = p =>
    `${p === '3pts' ? 'background:#39FF14;color:#000;font-weight:800'
      : p === '1pt'  ? 'background:rgba(255,215,0,.3);color:#FFD700;font-weight:700'
      : 'background:rgba(255,255,255,.08);color:#666'
    };border-radius:4px;padding:2px 8px;font-size:10px`;
  return `<span style="${cs(p1)}">${p1}</span>`
       + `<span style="color:var(--txt3);font-size:9px;margin:0 3px">vs</span>`
       + `<span style="${cs(p2)}">${p2}</span>`;
}

function noAccess() {
  return `<div class="empty"><div class="empty-ico">🔒</div>
    <div style="font-size:14px;margin-top:8px">Solo el admin puede ver esta sección</div></div>`;
}
function noJugadores() {
  return `<div class="empty"><div class="empty-ico">👥</div>
    <div style="font-size:14px;margin-top:8px">No hay jugadores cargados.</div></div>`;
}

let _toastTimer;
function toast(msg) {
  document.querySelectorAll('.toast').forEach(e => e.remove());
  const el = document.createElement('div');
  el.className = 'toast'; el.textContent = msg;
  document.body.appendChild(el);
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.remove(), 2500);
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('overlay').classList.toggle('show');
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('overlay').classList.remove('show');
}

function confirmReset() {
  if (!confirm('¿Empezar nuevo torneo? Se borran todos los puntajes y jugadores.')) return;
  api('/api/reset', { password: S.password }).then(r => {
    if (r.ok) { S.jugadores_edit = []; toast('Torneo reseteado'); }
  });
}


// ── Tamaño de letra (por dispositivo, localStorage) ──────────────────────────
const FZ_NIVELES = [1, 1.15, 1.3];

function setFontSize(nivel) {
  const n = Math.max(0, Math.min(FZ_NIVELES.length - 1, nivel));
  try { localStorage.setItem('fz', '' + n); } catch(e) {}
  aplicarFontSize();
}

function aplicarFontSize() {
  let n = 0;
  try { n = parseInt(localStorage.getItem('fz')) || 0; } catch(e) {}
  n = Math.max(0, Math.min(FZ_NIVELES.length - 1, n));
  document.body.style.zoom = FZ_NIVELES[n];
  document.querySelectorAll('.fz-btn').forEach((b, i) =>
    b.classList.toggle('active', i === n)
  );
}


// ── Init ──────────────────────────────────────────────────────────────────────
try { S.keepAlive = localStorage.getItem('ka') === 'true'; } catch(e) {}
try { S.tri = cargarTri(); } catch(e) {}

connectWS();
restaurarAuth();

setTimeout(() => {
  if (S.keepAlive) _aplicarKeepAlive();
  restaurarModos();
  aplicarFontSize();
}, 500);
