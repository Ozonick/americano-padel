/**
 * mexicano.js — Modo Mexicano
 * Render, autofill y acciones del modo mexicano.
 */

async function loadMexState() {
  try {
    const res = await fetch('/api/mexicano/state');
    S.mex = await res.json();
  } catch(e) { S.mex = null; }
}

function renderMexicano() {
  if (!S.mex) { loadMexState().then(renderTab); return `<div class="empty"><div class="spinner"></div></div>`; }

  const m      = S.mex;
  const cfg    = m.config || {};
  const estado = cfg.estado || 'idle';
  const ronda  = m.ronda_actual  || 0;
  const rondas = m.rondas_total  || 7;
  const games  = parseInt(cfg.games) || 16;
  const dis    = !esAdmin() ? 'disabled' : '';

  const badgeBg    = estado === 'jugando'    ? 'rgba(41,171,226,.15)'
                   : estado === 'finalizado' ? 'rgba(76,217,100,.15)'
                   : 'var(--surf3)';
  const badgeColor = estado === 'jugando'    ? '#29ABE2'
                   : estado === 'finalizado' ? '#4cd964'
                   : 'var(--txt2)';
  const badgeLabel = estado === 'idle'       ? 'Sin iniciar'
                   : estado === 'jugando'    ? `Ronda ${ronda} / ${rondas}`
                   : '🏆 Finalizado';

  let html = `<div class="card" style="margin-bottom:12px">
    <div class="card-hdr">
      <span class="card-title">🇲🇽 Modo Mexicano</span>
      <span class="badge" style="background:${badgeBg};color:${badgeColor}">${badgeLabel}</span>
    </div>`;

  // Configuración inicial (admin, idle)
  if (esAdmin() && estado === 'idle') {
    html += `<div style="padding:14px;display:grid;gap:8px">
      <div class="param-row"><span class="param-lbl">Canchas simultáneas</span>
        <input class="p-in" id="mex-canchas" type="number" min="1" max="8" value="${cfg.canchas || 3}"></div>
      <div class="param-row"><span class="param-lbl">Cantidad de rondas</span>
        <input class="p-in" id="mex-rondas" type="number" min="1" max="20" value="${cfg.rondas || 7}"></div>
      <div class="param-row"><span class="param-lbl">Games por partido</span>
        <input class="p-in" id="mex-games" type="number" min="4" max="40" value="${cfg.games || 16}"></div>
      <div style="font-size:11px;color:var(--txt2);padding:0 2px">
        Primera ronda sorteada aleatoriamente. Las siguientes según ranking.
      </div>
      <button class="btn-main" onclick="mexGuardarConfig()">Guardar y comenzar torneo</button>
    </div>`;
  }

  // Controles admin en juego
  if (esAdmin() && estado === 'jugando') {
    html += `<div style="padding:10px 14px;display:flex;gap:8px;border-bottom:1px solid var(--brd)">
      <button class="btn-sec" style="flex:1" onclick="mexSiguienteRonda()"
        ${m.ronda_completa && ronda < rondas ? '' : 'disabled'}>
        ➡️ Siguiente ronda ${ronda < rondas ? `(${ronda + 1}/${rondas})` : ''}
      </button>
      <button class="btn-sec" style="color:var(--red)" onclick="mexReset()">🗑 Reiniciar</button>
    </div>
    ${!m.ronda_completa ? `<div style="padding:6px 14px;font-size:11px;color:var(--amber)">
      ⚠️ Cargá todos los resultados de la ronda ${ronda} para avanzar
    </div>` : ''}`;
  }
  html += `</div>`;

  if (estado === 'idle' && !esAdmin())
    return html + `<div class="empty"><div class="empty-ico">⏳</div>
      <div style="font-size:14px;margin-top:8px">El admin aún no inició el torneo mexicano.</div></div>`;
  if (estado === 'idle') return html;

  // Partidos de la ronda actual
  if (m.partidos_actuales?.length) {
    const js    = new Set(m.partidos_actuales.flatMap(p => [p.j1, p.j2, p.j3, p.j4]));
    const desc  = (m.jugadores || []).map(j => j.nombre).filter(j => !js.has(j));

    html += `<div class="card" style="margin-bottom:12px">
      <div class="card-hdr">
        <span class="card-title">Ronda ${ronda} — Partidos en juego</span>
        <span class="badge" style="background:rgba(41,171,226,.1);color:#29ABE2">hasta ${games} games</span>
      </div>
      ${desc.length ? `<div style="padding:6px 16px;font-size:11px;color:var(--txt3);font-style:italic;border-bottom:1px solid var(--brd)">
        Descansan esta ronda: ${desc.join(', ')}
      </div>` : ''}`;

    m.partidos_actuales.forEach(p => {
      const ga = p.games_a ?? '', gb = p.games_b ?? '';
      let p1 = '', p2 = '';
      if (ga !== '' && gb !== '') {
        const a = +ga, b = +gb;
        p1 = a > b ? '3pts' : a === b ? '1pt' : '0pts';
        p2 = b > a ? '3pts' : a === b ? '1pt' : '0pts';
      }
      html += `<div class="partido-row" style="border-left:4px solid #29ABE2;padding-left:12px">
        <span class="g-pill" style="background:rgba(41,171,226,.15);color:#29ABE2;font-weight:800">${p.cancha}</span>
        <div class="equipos"><div class="e-names">
          <strong>${p.j1}</strong><span class="e-sep">+</span><strong>${p.j2}</strong>
          <span class="e-vs">vs</span>
          <strong>${p.j3}</strong><span class="e-sep">+</span><strong>${p.j4}</strong>
        </div></div>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
          <div class="games-wrap">
            <input class="g-in" type="number" min="0" max="${games}" value="${ga}" placeholder="—"
              style="border-color:rgba(41,171,226,.4)" ${dis}
              data-pair="mex-${p.cancha}" data-side="a" data-total="${games}" data-resid="${p.id}"
              oninput="autoFillMex(this)">
            <span class="g-dash">—</span>
            <input class="g-in" type="number" min="0" max="${games}" value="${gb}" placeholder="—"
              style="border-color:rgba(41,171,226,.4)" ${dis}
              data-pair="mex-${p.cancha}" data-side="b" data-total="${games}" data-resid="${p.id}"
              oninput="autoFillMex(this)">
          </div>
          ${p1 && p2 ? `<div style="display:flex;gap:4px;font-size:11px">${chipsHTML(p1, p2)}</div>` : ''}
        </div>
      </div>`;
    });
    html += `</div>`;
  }

  // Ranking acumulado
  if (m.ranking?.length) {
    html += `<div class="card"><div class="card-hdr">
      <span class="card-title">🏆 Ranking acumulado</span></div>
      <table class="pos-table">
        <thead><tr><th>Pos</th><th>Jugador</th><th>PJ</th><th>GF</th><th>GC</th><th>Dif</th><th>Pts</th></tr></thead>
        <tbody>`;
    m.ranking.forEach((j, pos) => {
      const s   = m.stats[j] || { pj: 0, gf: 0, gc: 0, pts: 0 };
      const dif = s.gf - s.gc;
      html += `<tr>
        <td><span class="rk ${pos === 0 ? 'g' : pos === 1 ? 's' : ''}">${pos + 1}</span></td>
        <td>${j}</td>
        <td style="color:#7a9bbf">${s.pj}</td>
        <td style="color:#5db896">${s.gf}</td>
        <td style="color:#c47a7a">${s.gc}</td>
        <td class="${dif > 0 ? 'dif-p' : dif < 0 ? 'dif-n' : ''}">${dif > 0 ? '+' : ''}${dif}</td>
        <td><span class="pts-val" style="color:#29ABE2">${s.pts}</span></td>
      </tr>`;
    });
    html += `</tbody></table></div>`;
  }

  // Campeón
  if (estado === 'finalizado') {
    const g = m.ranking[0];
    html += `<div class="card" style="margin-top:12px;border-color:#29ABE2">
      <div style="padding:20px;text-align:center">
        <div style="font-size:32px;margin-bottom:8px">🏆</div>
        <div style="font-size:18px;font-weight:600;color:#29ABE2">¡Campeón!</div>
        <div style="font-size:22px;font-weight:700;margin-top:4px">${g}</div>
        <div style="font-size:13px;color:var(--txt2);margin-top:8px">
          ${m.stats[g]?.pts || 0} pts · ${m.stats[g]?.gf || 0} games a favor
        </div>
        ${esAdmin() ? `<button class="btn-sec" style="margin-top:12px;width:auto;padding:8px 20px"
          onclick="mexReset()">Jugar de nuevo</button>` : ''}
      </div>
    </div>`;
  }
  return html;
}

// Autofill para inputs del mexicano
function autoFillMex(inputEl) {
  const val   = parseInt(inputEl.value);
  const total = parseInt(inputEl.dataset.total);
  const pair  = inputEl.dataset.pair;
  const side  = inputEl.dataset.side;
  const resId = inputEl.dataset.resid;

  if (isNaN(val) || val < 0) return;

  const otroSide = side === 'a' ? 'b' : 'a';
  const elOtro   = document.querySelector(
    `input[data-pair="${pair}"][data-side="${otroSide}"][data-resid="${resId}"]`
  );
  if (elOtro && val <= total) {
    elOtro.value = total - val;
    elOtro.style.boxShadow = '0 0 0 2px #39FF14';
    setTimeout(() => { elOtro.style.boxShadow = ''; }, 350);
  }

  const ga = side === 'a' ? val : parseInt(elOtro?.value) || 0;
  const gb = side === 'b' ? val : parseInt(elOtro?.value) || 0;
  if (isNaN(ga) || isNaN(gb)) return;

  clearTimeout(inputEl._t);
  inputEl._t = setTimeout(() => {
    api('/api/mexicano/resultado', {
      password: S.password, id: resId, games_a: ga, games_b: gb,
    }).then(r => { if (r.ok) toast('✓ Guardado'); });
  }, 400);
}

// Acciones admin
async function mexGuardarConfig() {
  const canchas = document.getElementById('mex-canchas')?.value || 3;
  const rondas  = document.getElementById('mex-rondas')?.value  || 7;
  const games   = document.getElementById('mex-games')?.value   || 16;
  const r1 = await api('/api/mexicano/config', {
    password: S.password, canchas: +canchas, rondas: +rondas, games: +games,
  });
  if (!r1.ok) return;
  const r2 = await api('/api/mexicano/iniciar', { password: S.password });
  if (r2.ok) toast('🇲🇽 Torneo mexicano iniciado');
}

async function mexSiguienteRonda() {
  const res = await api('/api/mexicano/siguiente', { password: S.password });
  if (res.ok) {
    if (res.finalizado) toast('🏆 Torneo finalizado');
    else toast(`➡️ Ronda ${res.ronda} iniciada`);
  }
}

async function mexReset() {
  if (!confirm('¿Reiniciar el torneo mexicano?')) return;
  const res = await api('/api/mexicano/reset', { password: S.password });
  if (res.ok) toast('Torneo mexicano reiniciado');
}
