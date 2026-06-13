/**
 * torneo.js — Torneo de Parejas (solo superadmin)
 * 16 parejas fijas · 4 zonas de 4 · round robin a 1 set
 * Clasifican 2 por zona → Cuartos → Semis → Final
 */

const TOR_COLS = ['#29ABE2', '#D4A800', '#ff6b62', '#bf5af2'];
const TOR_BGS  = ['rgba(41,171,226,.12)', 'rgba(255,215,0,.12)', 'rgba(255,69,58,.12)', 'rgba(191,90,242,.12)'];

async function loadTorneoState() {
  try {
    const res = await fetch('/api/torneo/state');
    S.torneo = await res.json();
  } catch (e) { S.torneo = null; }
}

function torNombre(t, idx) {
  if (idx === null || idx === undefined) return null;
  const p = t.parejas[idx];
  if (!p || (!p.j1 && !p.j2)) return `Pareja ${idx + 1}`;
  return `${p.j1} + ${p.j2}`;
}

function renderTorneo() {
  if (!S.torneo) {
    loadTorneoState().then(renderTab);
    return '<div class="empty"><div class="spinner"></div></div>';
  }
  const t = S.torneo;

  let html = `<div class="card" style="margin-bottom:12px">
    <div class="card-hdr">
      <span class="card-title">🏆 Torneo de Parejas</span>
      <span class="badge" style="background:${t.estado === 'config' ? 'var(--surf3)' : t.estado === 'finalizado' ? 'rgba(76,217,100,.15)' : 'rgba(41,171,226,.15)'};color:${t.estado === 'config' ? 'var(--txt2)' : t.estado === 'finalizado' ? '#4cd964' : '#29ABE2'}">
        ${t.estado === 'config' ? 'Configuración' : t.estado === 'zonas' ? 'Fase de zonas' : t.estado === 'playoffs' ? 'Playoffs' : '🏆 Finalizado'}
      </span>
    </div>`;

  if (t.estado !== 'config') {
    html += `<div style="padding:8px 14px;border-bottom:1px solid var(--brd)">
      <button class="btn-sec" style="color:var(--red);margin-top:0" onclick="torReset()">🗑 Reiniciar torneo de parejas</button>
    </div>`;
  }
  html += `</div>`;

  if (t.estado === 'config') html += torRenderConfig(t);
  else {
    html += torRenderZonas(t);
    if (t.estado === 'zonas') {
      html += `<div style="margin:14px 0">
        <button class="btn-main" onclick="torGenerarPlayoffs()" ${t.zonas_completas ? '' : 'disabled style="opacity:.4;cursor:not-allowed"'}>
          ${t.zonas_completas ? '⚡ Generar playoffs' : '⏳ Cargá todos los sets de zona para generar playoffs'}
        </button>
      </div>`;
    }
    if (t.playoffs) html += torRenderPlayoffs(t);
  }
  return html;
}

// ── Configuración: 16 parejas en 4 bloques de zona ────────────────────────────
function torRenderConfig(t) {
  let html = `<div class="card"><div class="card-hdr">
      <span class="card-title">Cargá las 16 parejas</span>
      <span class="badge" style="background:var(--surf3);color:var(--txt2)">4 zonas de 4</span>
    </div>
    <div style="padding:14px;display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px">`;

  for (let z = 0; z < 4; z++) {
    const col = TOR_COLS[z], bg = TOR_BGS[z];
    html += `<div style="border:1px solid ${col}40;border-radius:8px;overflow:hidden">
      <div style="background:${bg};padding:8px 12px;font-size:11px;font-weight:700;color:${col};letter-spacing:.08em">ZONA ${LETRAS[z]}</div>
      <div style="padding:10px;display:flex;flex-direction:column;gap:8px">`;
    for (let p = 0; p < 4; p++) {
      const idx = z * 4 + p;
      const par = t.parejas[idx] || { j1: '', j2: '' };
      html += `<div style="display:flex;align-items:center;gap:6px">
        <span style="font-size:10px;color:var(--txt3);font-family:'DM Mono',monospace;min-width:18px">${idx + 1}</span>
        <input class="jug-in" placeholder="Jugador 1" value="${par.j1 || ''}"
          data-tpar="${idx}" data-tj="j1" oninput="torEditPareja(this)">
        <input class="jug-in" placeholder="Jugador 2" value="${par.j2 || ''}"
          data-tpar="${idx}" data-tj="j2" oninput="torEditPareja(this)">
      </div>`;
    }
    html += `</div></div>`;
  }

  html += `</div>
    <div style="padding:0 14px 14px;display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn-sec" style="flex:1;margin-top:0" onclick="torGuardarParejas(false)">💾 Guardar parejas</button>
      <button class="btn-sec" style="flex:1;margin-top:0" onclick="torGuardarParejas(true)">🔀 Guardar y sortear zonas</button>
      <button class="btn-main" style="flex:1;margin-top:0" onclick="torIniciar()">▶ Iniciar torneo</button>
    </div></div>`;
  return html;
}

// Edición local con debounce: acumula cambios y los manda juntos
let _torEditTimer = null;
function torEditPareja(el) {
  const idx = parseInt(el.dataset.tpar);
  const campo = el.dataset.tj;
  if (!S.torneo) return;
  S.torneo.parejas[idx][campo] = el.value;
}

async function torGuardarParejas(sortear) {
  const parejas = S.torneo.parejas.map(p => ({ j1: (p.j1 || '').trim(), j2: (p.j2 || '').trim() }));
  const res = await api('/api/torneo/parejas', { password: S.password, parejas, sortear });
  if (res.ok) toast(sortear ? '🔀 Parejas guardadas y sorteadas' : '✓ Parejas guardadas');
}

async function torIniciar() {
  // Guardar primero lo que esté en pantalla
  const parejas = S.torneo.parejas.map(p => ({ j1: (p.j1 || '').trim(), j2: (p.j2 || '').trim() }));
  const r1 = await api('/api/torneo/parejas', { password: S.password, parejas, sortear: false });
  if (!r1.ok) return;
  const r2 = await api('/api/torneo/iniciar', { password: S.password });
  if (r2.ok) toast('🏆 Torneo de parejas iniciado');
}

// ── Zonas ─────────────────────────────────────────────────────────────────────
function torRenderZonas(t) {
  const editable = t.estado === 'zonas' && esSuper();
  let html = `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px">`;

  t.zonas.forEach(z => {
    const col = TOR_COLS[z.zona], bg = TOR_BGS[z.zona];
    html += `<div class="card">
      <div class="card-hdr" style="background:${bg};border-bottom:2px solid ${col}40">
        <span class="card-title" style="color:${col}">Zona ${z.letra}</span>
        <span class="badge" style="background:rgba(0,0,0,.25);color:${col};border:none;font-size:10px">1 set · clasifican 2</span>
      </div>`;

    // Tabla de posiciones
    html += `<table class="pos-table"><thead><tr><th>Pos</th><th>Pareja</th><th>PJ</th><th>PG</th><th>Dif</th></tr></thead><tbody>`;
    z.tabla.forEach((row, pos) => {
      const dif = row.gf - row.gc;
      const clasifica = pos < 2;
      html += `<tr style="${clasifica ? `background:${bg}` : ''}">
        <td><span class="rk ${pos === 0 ? 'g' : pos === 1 ? 's' : ''}">${pos + 1}</span></td>
        <td style="font-size:12px">${torNombre(t, row.idx)}${clasifica ? ' <span style="font-size:9px;color:' + col + '">✓</span>' : ''}</td>
        <td style="color:#7a9bbf">${row.pj}</td>
        <td><span class="pts-val" style="color:${col};font-size:14px">${row.pg}</span></td>
        <td class="${dif > 0 ? 'dif-p' : dif < 0 ? 'dif-n' : ''}">${dif > 0 ? '+' : ''}${dif}</td>
      </tr>`;
    });
    html += `</tbody></table>`;

    // Partidos
    z.partidos.forEach(m => {
      const ok = m.ga !== null;
      html += `<div style="padding:8px 12px;border-top:1px solid var(--brd);display:flex;align-items:center;gap:8px;${ok ? 'background:rgba(0,0,0,.1)' : ''}">
        <div style="flex:1;min-width:0;font-size:12px;font-weight:500;line-height:1.5">
          ${torNombre(t, m.a)}<span style="color:var(--txt3);font-size:10px;margin:0 4px">vs</span>${torNombre(t, m.b)}
        </div>
        <div class="games-wrap">
          <input class="g-in" type="number" min="0" max="7" value="${m.ga ?? ''}" placeholder="—"
            style="border-color:${col}66;width:38px;font-size:14px" ${editable ? '' : 'disabled'}
            data-tid="${m.id}" data-tside="a" oninput="torInputSet(this)">
          <span class="g-dash">—</span>
          <input class="g-in" type="number" min="0" max="7" value="${m.gb ?? ''}" placeholder="—"
            style="border-color:${col}66;width:38px;font-size:14px" ${editable ? '' : 'disabled'}
            data-tid="${m.id}" data-tside="b" oninput="torInputSet(this)">
        </div>
      </div>`;
    });

    html += `</div>`;
  });
  html += `</div>`;
  return html;
}

// Guardar resultado de set cuando ambos campos están completos.
// SIN autofill: un set no suma una cantidad fija de games.
function torInputSet(inputEl) {
  const tid = inputEl.dataset.tid;
  const otro = document.querySelector(`input[data-tid="${tid}"][data-tside="${inputEl.dataset.tside === 'a' ? 'b' : 'a'}"]`);
  const ga = inputEl.dataset.tside === 'a' ? parseInt(inputEl.value) : parseInt(otro?.value);
  const gb = inputEl.dataset.tside === 'b' ? parseInt(inputEl.value) : parseInt(otro?.value);
  if (isNaN(ga) || isNaN(gb)) return;
  if (ga === gb) { toast('⚠️ Un set no puede empatar'); return; }

  clearTimeout(inputEl._t);
  inputEl._t = setTimeout(() => {
    api('/api/torneo/resultado', { password: S.password, id: tid, ga, gb })
      .then(r => { if (r.ok) toast('✓ Set guardado'); });
  }, 500);
}

async function torGenerarPlayoffs() {
  const res = await api('/api/torneo/playoffs', { password: S.password });
  if (res.ok) toast('⚡ Playoffs generados');
}

// ── Playoffs: Cuartos → Semis → Final ─────────────────────────────────────────
function torRenderPlayoffs(t) {
  const po = t.playoffs;
  const editable = esSuper() && t.estado !== 'config';
  let html = `<div class="card" style="margin-top:14px">
    <div class="card-hdr" style="background:rgba(201,168,76,.12);border-bottom:2px solid rgba(201,168,76,.4)">
      <span class="card-title" style="color:#C9A84C">⚡ Playoffs</span>
      <span class="badge" style="background:rgba(0,0,0,.25);color:#C9A84C;border:none;font-size:10px">1 set por cruce</span>
    </div>`;

  const fases = [
    { label: 'CUARTOS DE FINAL', matches: po.cuartos },
    { label: 'SEMIFINALES',      matches: po.semis },
    { label: 'FINAL',            matches: po.final },
  ];

  fases.forEach(({ label, matches }) => {
    html += `<div style="padding:8px 14px 2px;font-size:10px;font-weight:700;color:#C9A84C;letter-spacing:.08em;border-top:1px solid var(--brd)">${label}</div>`;
    matches.forEach(m => {
      const nA = torNombre(t, m.a), nB = torNombre(t, m.b);
      const definido = m.a !== null && m.b !== null;
      const ok = m.ga !== null;
      html += `<div style="padding:8px 14px;display:flex;align-items:center;gap:8px;${ok ? 'background:rgba(0,0,0,.1)' : ''}">
        <div style="flex:1;min-width:0;font-size:13px;font-weight:500;line-height:1.5;${!definido ? 'color:var(--txt3);font-style:italic' : ''}">
          ${nA || 'Por definir'}<span style="color:var(--txt3);font-size:10px;margin:0 5px">vs</span>${nB || 'Por definir'}
        </div>
        <div class="games-wrap">
          <input class="g-in" type="number" min="0" max="7" value="${m.ga ?? ''}" placeholder="—"
            style="border-color:rgba(201,168,76,.5);width:38px;font-size:14px" ${editable && definido ? '' : 'disabled'}
            data-tid="${m.id}" data-tside="a" oninput="torInputSet(this)">
          <span class="g-dash">—</span>
          <input class="g-in" type="number" min="0" max="7" value="${m.gb ?? ''}" placeholder="—"
            style="border-color:rgba(201,168,76,.5);width:38px;font-size:14px" ${editable && definido ? '' : 'disabled'}
            data-tid="${m.id}" data-tside="b" oninput="torInputSet(this)">
        </div>
      </div>`;
    });
  });

  if (t.campeon !== null && t.campeon !== undefined) {
    html += `<div style="padding:24px;text-align:center;border-top:1px solid var(--brd)">
      <div style="font-size:36px;margin-bottom:8px">🏆</div>
      <div style="font-size:16px;font-weight:700;color:#C9A84C">¡Campeones del torneo!</div>
      <div style="font-size:22px;font-weight:700;margin-top:6px">${torNombre(t, t.campeon)}</div>
    </div>`;
  }

  html += `</div>`;
  return html;
}

async function torReset() {
  if (!confirm('¿Reiniciar el torneo de parejas? Se borran parejas, zonas y playoffs.')) return;
  const res = await api('/api/torneo/reset', { password: S.password });
  if (res.ok) toast('Torneo de parejas reiniciado');
}
