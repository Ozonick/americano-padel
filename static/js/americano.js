/**
 * americano.js — Modo de juego principal
 * Fixture, posiciones, finales, jugadores y configuración del torneo.
 */

// ── Fixture ───────────────────────────────────────────────────────────────────
function renderFixture() {
  const { grupos, fixtures_prel, config, resultados } = S.state;
  if (!grupos || !grupos.length)
    return `<div class="empty"><div class="empty-ico">👥</div>
      <div style="font-size:14px;margin-top:8px">No hay jugadores cargados.</div></div>`;

  const rp  = parseInt(config.rondas_prel)   || 7;
  const ng  = parseInt(config.games_partido) || 16;
  const dis = S.role !== 'admin' ? 'disabled' : '';

  const gruposFiltrados = S.canchaVista === 'todas'
    ? grupos.map((g, i) => ({ g, i }))
    : [{ g: grupos[S.canchaVista], i: S.canchaVista }].filter(x => x.g);

  const gridCols = S.canchaVista === 'todas'
    ? 'repeat(auto-fit,minmax(300px,1fr))'
    : '1fr';

  let html = `<div style="display:grid;grid-template-columns:${gridCols};gap:12px">`;

  gruposFiltrados.forEach(({ g: grupo, i: gi }) => {
    const col = COLORES[gi % COLORES.length];
    html += `<div class="card">
      <div class="card-hdr" style="background:${col.bg};border-bottom:2px solid ${col.txt}40">
        <span class="card-title" style="color:${col.txt}">Cancha ${gi + 1} · Grupo ${LETRAS[gi]}</span>
        <span class="badge" style="background:rgba(0,0,0,.25);color:${col.txt};border:none;font-size:10px">
          hasta ${ng} games
        </span>
      </div>
      <div style="padding:6px 12px 8px;background:${col.bg}55;border-bottom:1px solid ${col.txt}25">
        <span style="font-size:11px;color:${col.txt};opacity:.85;font-weight:500">
          ${grupo.join(' · ')}
        </span>
      </div>`;

    for (let r = 0; r < rp; r++) {
      if (!fixtures_prel[gi] || r >= fixtures_prel[gi].length) continue;
      const [j1, j2, j3, j4] = fixtures_prel[gi][r];
      const desc = grupo.filter(p => ![j1, j2, j3, j4].includes(p));
      const key  = `prel-${gi}-${r}`;
      const res  = (resultados || {})[key] || {};
      const ga   = res.ga ?? '';
      const gb   = res.gb ?? '';
      let p1 = '', p2 = '';
      if (ga !== '' && gb !== '') {
        const a = +ga, b = +gb;
        p1 = a > b ? '3pts' : a === b ? '1pt' : '0pts';
        p2 = b > a ? '3pts' : a === b ? '1pt' : '0pts';
      }

      html += `<div style="padding:9px 12px;border-bottom:1px solid var(--brd);${p1 ? 'background:rgba(0,0,0,.1)' : ''}">
        <div style="font-size:10px;font-weight:600;color:${col.txt};opacity:.6;text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px">
          Ronda ${r + 1} ${p1 ? '✓' : ''}
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
          <div style="flex:1;min-width:0">
            <div style="font-size:13px;font-weight:600;line-height:1.5">
              ${j1} + ${j2}
              <span style="color:var(--txt3);font-size:11px;font-weight:400;margin:0 4px">vs</span>
              ${j3} + ${j4}
            </div>
            ${desc.length ? `<div style="font-size:10px;color:var(--txt3);font-style:italic;margin-top:2px">
              Descansan: ${desc.join(', ')}</div>` : ''}
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:3px;flex-shrink:0">
            <div class="games-wrap">
              <input class="g-in" type="number" min="0" max="${ng}" value="${ga}" placeholder="—"
                style="border-color:${col.brd};width:40px;font-size:14px" ${dis}
                data-pair="${gi}-${r}" data-side="a" data-total="${ng}" data-key="${key}"
                oninput="autoFill(this)">
              <span class="g-dash">—</span>
              <input class="g-in" type="number" min="0" max="${ng}" value="${gb}" placeholder="—"
                style="border-color:${col.brd};width:40px;font-size:14px" ${dis}
                data-pair="${gi}-${r}" data-side="b" data-total="${ng}" data-key="${key}"
                oninput="autoFill(this)">
            </div>
            <div id="chips-${gi}-${r}" style="display:flex;gap:3px;font-size:10px;min-height:15px">
              ${(p1 && p2) ? chipsHTML(p1, p2) : ''}
            </div>
          </div>
        </div>
      </div>`;
    }
    html += `</div>`;
  });

  html += `</div>`;
  return html;
}

function autoFill(inputEl) {
  const val   = parseInt(inputEl.value);
  const total = parseInt(inputEl.dataset.total);
  const pair  = inputEl.dataset.pair;
  const side  = inputEl.dataset.side;
  const key   = inputEl.dataset.key;

  if (isNaN(val) || val < 0) return;

  const otroSide = side === 'a' ? 'b' : 'a';
  const elOtro   = document.querySelector(`input[data-pair="${pair}"][data-side="${otroSide}"]`);
  if (elOtro && val <= total) {
    elOtro.value = total - val;
    elOtro.style.boxShadow = '0 0 0 2px #39FF14';
    setTimeout(() => { elOtro.style.boxShadow = ''; }, 350);
  }

  const ga = side === 'a' ? val : (elOtro ? parseInt(elOtro.value) || 0 : total - val);
  const gb = side === 'b' ? val : (elOtro ? parseInt(elOtro.value) || 0 : total - val);

  const [gi, ri] = pair.split('-');
  const chipsEl  = document.getElementById(`chips-${gi}-${ri}`);
  if (chipsEl && ga + gb > 0) {
    const p1 = ga > gb ? '3pts' : ga === gb ? '1pt' : '0pts';
    const p2 = gb > ga ? '3pts' : ga === gb ? '1pt' : '0pts';
    chipsEl.innerHTML = chipsHTML(p1, p2);
  }

  const gaFinal = side === 'a' ? val : parseInt(elOtro?.value);
  const gbFinal = side === 'b' ? val : parseInt(elOtro?.value);
  if (isNaN(gaFinal) || isNaN(gbFinal)) return;

  clearTimeout(inputEl._t);
  inputEl._t = setTimeout(() => {
    api('/api/resultado', {
      password: S.password, id: key,
      games_a: gaFinal, games_b: gbFinal, fase: 'prel',
    }).then(r => { if (r.ok) toast('✓ Guardado'); });
  }, 400);
}


// ── Posiciones ────────────────────────────────────────────────────────────────
function calcStats() {
  const { grupos, fixtures_prel, resultados } = S.state;
  const stats = {};
  (grupos || []).forEach((g, gi) => {
    g.forEach(j => { stats[j] = { pj: 0, gf: 0, gc: 0, pts: 0, gi }; });
    (fixtures_prel[gi] || []).forEach(([j1, j2, j3, j4], ri) => {
      const res = (resultados || {})[`prel-${gi}-${ri}`];
      if (!res || res.ga == null) return;
      const ga = +res.ga, gb = +res.gb;
      [j1, j2].forEach(j => { if (stats[j]) { stats[j].gf += ga; stats[j].gc += gb; stats[j].pj++; } });
      [j3, j4].forEach(j => { if (stats[j]) { stats[j].gf += gb; stats[j].gc += ga; stats[j].pj++; } });
      const p1 = ga > gb ? 3 : ga === gb ? 1 : 0;
      const p2 = gb > ga ? 3 : ga === gb ? 1 : 0;
      [j1, j2].forEach(j => { if (stats[j]) stats[j].pts += p1; });
      [j3, j4].forEach(j => { if (stats[j]) stats[j].pts += p2; });
    });
  });
  return stats;
}

function sortGrupo(grupo, stats) {
  return [...grupo].sort((a, b) => {
    const sa = stats[a] || {}, sb = stats[b] || {};
    if ((sb.pts || 0) !== (sa.pts || 0)) return (sb.pts || 0) - (sa.pts || 0);
    const da = (sa.gf || 0) - (sa.gc || 0), db = (sb.gf || 0) - (sb.gc || 0);
    if (db !== da) return db - da;
    return (sb.gf || 0) - (sa.gf || 0);
  });
}

function renderPosiciones() {
  const { grupos } = S.state;
  if (!grupos || !grupos.length) return noJugadores();
  const stats = calcStats();
  let html = '';
  grupos.forEach((grupo, gi) => {
    const col    = COLORES[gi % COLORES.length];
    const sorted = sortGrupo(grupo, stats);
    html += `<div class="card"><div class="card-hdr">
      <span class="card-title">Grupo ${LETRAS[gi]}</span>
      <span class="badge" style="background:${col.bg};color:${col.txt};border-color:${col.brd}">
        ${grupo.length} jugadores
      </span>
    </div>
    <table class="pos-table">
      <thead><tr><th>Pos</th><th>Jugador</th><th>PJ</th><th>GF</th><th>GC</th><th>Dif</th><th>Pts</th></tr></thead>
      <tbody>`;
    sorted.forEach((j, pos) => {
      const s   = stats[j] || { pj: 0, gf: 0, gc: 0, pts: 0 };
      const dif = s.gf - s.gc;
      html += `<tr>
        <td><span class="rk ${pos === 0 ? 'g' : pos === 1 ? 's' : pos === 2 ? 'b' : ''}">${pos + 1}</span></td>
        <td>${j}</td>
        <td style="color:#7a9bbf">${s.pj}</td>
        <td style="color:#5db896">${s.gf}</td>
        <td style="color:#c47a7a">${s.gc}</td>
        <td class="${dif > 0 ? 'dif-p' : dif < 0 ? 'dif-n' : ''}">${dif > 0 ? '+' : ''}${dif}</td>
        <td><span class="pts-val" style="color:${col.txt}">${s.pts}</span></td>
      </tr>`;
    });
    html += `</tbody></table></div>`;
  });
  return html;
}


// ── Finales ───────────────────────────────────────────────────────────────────
function renderFinales() {
  const { grupos, resultados } = S.state;
  if (!grupos || !grupos.length) return noJugadores();
  const stats = calcStats();

  const copasDef = [
    { id: 'oro',    emoji: '🥇', label: 'Copa Oro',    posIdx: [0, 1], color: '#C9A84C', bg: 'rgba(201,168,76,.12)',   brd: 'rgba(201,168,76,.4)'    },
    { id: 'plata',  emoji: '🥈', label: 'Copa Plata',  posIdx: [2, 3], color: '#4da6ff', bg: 'rgba(10,132,255,.1)',    brd: 'rgba(10,132,255,.35)'   },
    { id: 'bronce', emoji: '🥉', label: 'Copa Bronce', posIdx: [4, 5], color: '#c4956a', bg: 'rgba(196,149,106,.12)',  brd: 'rgba(196,149,106,.4)'   },
  ];
  const dis = S.role !== 'admin' ? 'disabled' : '';
  let html  = '';

  copasDef.forEach(({ id, emoji, label, posIdx, color, bg, brd }) => {
    const cpg = grupos.map(g => sortGrupo(g, stats));
    const candidatos = [];
    posIdx.forEach(pos => cpg.forEach(sg => { if (sg[pos]) candidatos.push(sg[pos]); }));
    if (!candidatos.length) return;

    // Rankear globalmente y armar duos (1°+2°, 3°+4°, ...)
    const rankGlobal = [...candidatos].sort((a, b) => {
      const sa = stats[a] || {}, sb = stats[b] || {};
      if ((sb.pts || 0) !== (sa.pts || 0)) return (sb.pts || 0) - (sa.pts || 0);
      return ((sb.gf || 0) - (sb.gc || 0)) - ((sa.gf || 0) - (sa.gc || 0));
    });
    const duos = [];
    for (let i = 0; i + 1 < rankGlobal.length; i += 2) duos.push([rankGlobal[i], rankGlobal[i + 1]]);
    const partidos = [];
    for (let i = 0; i < duos.length; i++)
      for (let j = i + 1; j < duos.length; j++)
        partidos.push({ duoA: duos[i], duoB: duos[j], idx: partidos.length });

    html += `<div class="card" style="margin-bottom:14px">
      <div class="copa-bar" style="background:${bg};border-bottom:2px solid ${brd}">
        <span style="color:${color};font-size:14px;font-weight:700">${emoji} ${label}</span>
        <span style="font-size:11px;color:${color};opacity:.7">Round Robin · G = Ganó · P = Perdió</span>
      </div>
      <div style="padding:10px 14px;border-bottom:1px solid var(--brd);display:flex;flex-wrap:wrap;gap:8px">`;

    duos.forEach((duo, di) => {
      const pts = (stats[duo[0]]?.pts || 0) + (stats[duo[1]]?.pts || 0);
      html += `<div style="background:${bg};border:1px solid ${brd};border-radius:8px;padding:6px 12px;min-width:140px">
        <div style="font-size:10px;font-weight:700;color:${color};letter-spacing:.06em;margin-bottom:4px">
          DUO ${di + 1} · ${pts} pts
        </div>
        <div style="font-size:13px;font-weight:600">${duo[0]}</div>
        <div style="font-size:13px;font-weight:600">${duo[1]}</div>
      </div>`;
    });
    html += `</div>`;

    // Partidos
    if (partidos.length) {
      html += `<div style="display:flex;flex-direction:column">`;
      partidos.forEach(({ duoA, duoB, idx }) => {
        const key = `final-${id}-${idx}`;
        const res = (resultados || {})[key] || {};
        const rv  = res.ga;
        const bs  = val => `padding:6px 18px;border-radius:6px;font-size:13px;font-weight:700;cursor:pointer;
          border:2px solid ${rv == val ? color : 'var(--brd2)'};
          background:${rv == val ? bg : 'transparent'};
          color:${rv == val ? color : 'var(--txt2)'};
          ${dis ? 'opacity:.5;cursor:not-allowed' : ''}`;
        const duoNames = (duo, align) =>
          `<div style="display:flex;flex-direction:column;align-items:${align};gap:1px">
            <span style="font-weight:600;font-size:13px">${duo[0]}</span>
            <span style="color:var(--txt3);font-size:10px;line-height:1">+</span>
            <span style="font-weight:600;font-size:13px">${duo[1]}</span>
          </div>`;
        html += `<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 14px;border-bottom:1px solid var(--brd)">
          ${duoNames(duoA, 'flex-start')}
          <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
            <button style="${bs(1)}" ${dis} onclick="guardarFinal('${key}',1)">G</button>
            <span style="color:var(--txt3);font-size:12px">vs</span>
            <button style="${bs(2)}" ${dis} onclick="guardarFinal('${key}',2)">G</button>
          </div>
          ${duoNames(duoB, 'flex-end')}
        </div>`;
      });
      html += `</div>`;
    }

    // Tabla posiciones copa
    const cs = {};
    duos.forEach(duo => { cs[duo.join('+')] = { duo, g: 0, p: 0 }; });
    partidos.forEach(({ duoA, duoB, idx }) => {
      const rv = (resultados || {})[`final-${id}-${idx}`]?.ga;
      if (!rv) return;
      const kA = duoA.join('+'), kB = duoB.join('+');
      if (rv == 1) { cs[kA].g++; cs[kB].p++; } else { cs[kB].g++; cs[kA].p++; }
    });
    const rk = Object.values(cs).sort((a, b) => b.g - a.g);
    if (rk.some(r => r.g > 0 || r.p > 0)) {
      html += `<div style="padding:10px 14px;border-top:1px solid var(--brd)">
        <div style="font-size:10px;font-weight:600;color:var(--txt3);letter-spacing:.06em;margin-bottom:8px">
          POSICIONES COPA
        </div>
        <div style="display:flex;flex-direction:column;gap:4px">`;
      rk.forEach((r, pos) => {
        html += `<div style="display:flex;align-items:center;gap:10px;padding:5px 8px;border-radius:6px;background:${pos === 0 ? bg : 'transparent'}">
          <span style="width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;
            font-size:11px;font-weight:700;
            background:${pos === 0 ? color : 'var(--surf3)'};
            color:${pos === 0 ? '#000' : 'var(--txt2)'}">${pos + 1}</span>
          <span style="font-weight:500;font-size:13px">${r.duo[0]} + ${r.duo[1]}</span>
          <span style="margin-left:auto;font-size:12px">
            <span style="color:#39FF14;font-weight:700">${r.g}G</span>
            <span style="color:var(--txt3);margin:0 4px">·</span>
            <span style="color:var(--red)">${r.p}P</span>
          </span>
        </div>`;
      });
      html += `</div></div>`;
    }
    html += `</div>`;
  });

  return html || `<div class="empty"><div class="empty-ico">⏳</div>
    <div style="font-size:14px;margin-top:8px">Jugá la fase preliminar para ver las finales.</div></div>`;
}

async function guardarFinal(key, ganador) {
  if (S.role !== 'admin') return;
  const res = await api('/api/resultado', {
    password: S.password, id: key,
    games_a: ganador, games_b: 0, fase: 'final',
  });
  if (res.ok) toast('✓ Resultado guardado');
}


// ── Configuración ─────────────────────────────────────────────────────────────
function renderConfig() {
  const cfg = S.state.config || {};
  const s   = S.state.sugerencia || {};
  return `<div class="card"><div class="card-hdr">
    <span class="card-title">⚙️ Configuración del torneo</span></div>
    <div style="padding:16px;display:grid;gap:10px">
      <div class="param-row"><span class="param-lbl">Nombre del torneo</span>
        <input class="p-in" id="cfg-nombre" style="width:180px;text-align:left" value="${cfg.torneo_nombre || 'Super Americano'}"></div>
      <div class="param-row"><span class="param-lbl">Canchas / grupos</span>
        <input class="p-in" id="cfg-canchas" type="number" min="1" max="8" value="${cfg.canchas || 3}" oninput="updateSug()"></div>
      <div class="param-row"><span class="param-lbl">Rondas preliminar</span>
        <input class="p-in" id="cfg-rondas" type="number" min="1" max="15" value="${cfg.rondas_prel || 7}"></div>
      <div class="param-row"><span class="param-lbl">Rondas finales</span>
        <input class="p-in" id="cfg-rondas-f" type="number" min="1" max="10" value="${cfg.rondas_final || 5}"></div>
      <div class="param-row"><span class="param-lbl">Games por partido</span>
        <input class="p-in" id="cfg-games" type="number" min="4" max="40" value="${cfg.games_partido || 16}" oninput="updateSug()"></div>
      <div class="param-row"><span class="param-lbl">Tiempo de cancha (min)</span>
        <input class="p-in" id="cfg-tiempo" type="number" min="30" max="240" value="${cfg.tiempo_cancha || 90}" oninput="updateSug()"></div>
      <div class="hint-box" id="cfg-sug" style="line-height:1.7">
        ⏱ Con <strong>${cfg.tiempo_cancha || 90} min</strong> y ${s.n_x_grupo || 6} jug/grupo:<br>
        Máx sin repetir compañero: <strong>${s.rondas_max_sin_repetir || 5} rondas</strong><br>
        Por tiempo: <strong>${s.rondas_prel_x_tiempo || '?'}</strong> rondas disponibles<br>
        → Sugerido: <strong>${s.rondas_prel || '?'} prelim</strong> + ${s.rondas_final || 4} final · ~${s.tiempo_total_est || '?'} min total
      </div>
      <button class="btn-main" onclick="saveConfig()">Guardar configuración</button>
    </div></div>`;
}

async function updateSug() {
  const t = document.getElementById('cfg-tiempo')?.value || 90;
  const g = document.getElementById('cfg-games')?.value  || 16;
  const res = await fetch(`/api/sugerencia?tiempo=${t}&games=${g}`);
  const s   = await res.json();
  const el  = document.getElementById('cfg-sug');
  if (el) el.innerHTML = `⏱ Con <strong>${t} min</strong> y ${s.n_x_grupo} jug/grupo:<br>
    Máx sin repetir: <strong>${s.rondas_max_sin_repetir} rondas</strong> · Por tiempo: ${s.rondas_prel_x_tiempo}<br>
    → Sugerido: <strong>${s.rondas_prel} prelim</strong> + ${s.rondas_final} final · ~${s.tiempo_total_est} min total`;
}

async function saveConfig() {
  const res = await api('/api/config', {
    password: S.password,
    config: {
      torneo_nombre: document.getElementById('cfg-nombre').value,
      canchas:       document.getElementById('cfg-canchas').value,
      rondas_prel:   document.getElementById('cfg-rondas').value,
      rondas_final:  document.getElementById('cfg-rondas-f').value,
      games_partido: document.getElementById('cfg-games').value,
      tiempo_cancha: document.getElementById('cfg-tiempo').value,
    },
  });
  if (res.ok) toast('✓ Configuración guardada');
}


// ── Jugadores ─────────────────────────────────────────────────────────────────
function renderJugadores() {
  const { jugadores, config } = S.state;
  const nc = parseInt(config.canchas) || 3;

  if (!S.jugadores_edit.length) {
    if (jugadores?.length) S.jugadores_edit = jugadores.map(j => ({ ...j }));
    else S.jugadores_edit = Array.from({ length: 18 }, (_, i) => ({
      nombre: '', grupo: Math.floor(i / (Math.round(18 / nc))), orden: i,
    }));
  }

  let html = `<div class="card"><div class="card-hdr">
    <span class="card-title">👥 Jugadores</span>
    <div style="display:flex;gap:6px">
      <button class="badge" style="background:var(--amber-d);color:var(--amber);cursor:pointer;border:none"
        onclick="shuffleJugadores()">🔀 Sortear</button>
      <button class="badge" style="background:var(--green-d);color:var(--green);cursor:pointer;border:none"
        onclick="saveJugadores()">💾 Guardar</button>
    </div></div>
    <div style="padding:14px">
      <div style="font-size:12px;color:var(--txt2);margin-bottom:12px">
        Escribí los nombres. El grupo se asigna automáticamente según el orden.<br>
        Después de sortear podés ajustar el grupo de cada jugador.
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:6px;margin-bottom:14px">`;

  S.jugadores_edit.forEach((j, i) => {
    const col = COLORES[(j.grupo || 0) % COLORES.length];
    html += `<div class="jug-row" style="width:100%">
      <span class="jug-num">${i + 1}</span>
      <span class="jug-dot" style="background:${col.txt}"></span>
      <input class="jug-in" type="text" value="${j.nombre || ''}" placeholder="Jugador ${i + 1}"
        oninput="S.jugadores_edit[${i}].nombre=this.value" style="min-width:0;flex:1">
      <select class="grp-sel" onchange="changeGrupo(${i},+this.value)" style="flex-shrink:0">
        ${Array.from({ length: nc }, (_, g) =>
          `<option value="${g}" ${(j.grupo || 0) === g ? 'selected' : ''}>${LETRAS[g]}</option>`
        ).join('')}
      </select>
    </div>`;
  });

  html += `</div>
    <div style="display:flex;gap:8px">
      <button class="btn-sec" onclick="addJug()">+ Agregar jugador</button>
      <button class="btn-sec" onclick="removeJug()">− Quitar último</button>
    </div>
  </div></div>`;
  return html;
}

function addJug() {
  const nc  = parseInt(S.state?.config?.canchas) || 3;
  const n   = S.jugadores_edit.length;
  const tam = Math.max(4, Math.round((n + 1) / nc));
  S.jugadores_edit.push({ nombre: '', grupo: Math.floor(n / tam), orden: n });
  renderTab();
}
function removeJug() {
  if (S.jugadores_edit.length > 4) { S.jugadores_edit.pop(); renderTab(); }
}

async function shuffleJugadores() {
  const nombres = S.jugadores_edit.map(j => j.nombre).filter(n => n.trim());
  if (!nombres.length) { toast('Ingresá nombres primero'); return; }
  const res = await api('/api/shuffle', { password: S.password, nombres });
  if (res.ok) { S.jugadores_edit = []; toast('🔀 Grupos sorteados'); }
}

async function saveJugadores() {
  const jug = S.jugadores_edit
    .filter(j => j.nombre.trim())
    .map((j, i) => ({ nombre: j.nombre.trim(), grupo: j.grupo || 0, orden: i }));
  const res = await api('/api/jugadores', { password: S.password, jugadores: jug });
  if (res.ok) { S.jugadores_edit = []; toast('✓ Jugadores guardados'); }
}

function changeGrupo(idx, grupo) {
  S.jugadores_edit[idx].grupo = grupo;
  const rows = document.querySelectorAll('.jug-row');
  if (rows[idx]) {
    const dot = rows[idx].querySelector('.jug-dot');
    if (dot) dot.style.background = COLORES[grupo % COLORES.length].txt;
  }
}
