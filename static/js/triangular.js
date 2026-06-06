/**
 * triangular.js — Modo Triangular
 * 3 parejas fijas por cancha. Sistema de puntos pádel (0-15-30-40-Juego).
 * Primero en llegar a 6 juegos gana el set (tie-break en 6-6).
 * Estado persistido en localStorage.
 */

const PUNTOS_SEQ = [0, 15, 30, 40];
const puntosLabel = p => p >= 3 ? (p === 3 ? '40' : 'AD') : PUNTOS_SEQ[p].toString();


// ── Estado ────────────────────────────────────────────────────────────────────
function triGrupoInicial() {
  return {
    parejas: [['', ''], ['', ''], ['', '']],
    partidos: [
      { pA: 0, pB: 1, juegos: [0, 0], puntos: [0, 0], historial: [], ganador: null },
      { pA: 1, pB: 2, juegos: [0, 0], puntos: [0, 0], historial: [], ganador: null },
      { pA: 0, pB: 2, juegos: [0, 0], puntos: [0, 0], historial: [], ganador: null },
    ],
  };
}

function triEstadoInicial(ncanchas = 1) {
  return {
    canchas: ncanchas,
    estado:  'idle',
    grupos:  Array.from({ length: ncanchas }, () => triGrupoInicial()),
  };
}

function cargarTri() {
  try { const s = localStorage.getItem('tri'); if (s) return JSON.parse(s); } catch(e) {}
  return triEstadoInicial(1);
}

function guardarTri() {
  try { localStorage.setItem('tri', JSON.stringify(S.tri)); } catch(e) {}
}


// ── Render ────────────────────────────────────────────────────────────────────
function renderTriangular() {
  if (!S.tri) S.tri = cargarTri();
  const tri    = S.tri;
  const dis    = S.role !== 'admin' ? 'disabled' : '';
  const cols   = ['#29ABE2', '#D4A800', '#ff6b62'];
  const colsBg = ['rgba(41,171,226,.12)', 'rgba(255,215,0,.12)', 'rgba(255,69,58,.12)'];

  let html = `<div class="card" style="margin-bottom:12px">
    <div class="card-hdr">
      <span class="card-title">🔺 Modo Triangular</span>
      <span class="badge" style="background:${tri.estado === 'jugando' ? 'rgba(41,171,226,.15)' : 'var(--surf3)'};
        color:${tri.estado === 'jugando' ? '#29ABE2' : 'var(--txt2)'}">
        ${tri.estado === 'idle' ? 'Sin iniciar'
          : tri.estado === 'jugando' ? `${tri.canchas} cancha${tri.canchas > 1 ? 's' : ''}`
          : '🏆 Finalizado'}
      </span>
    </div>`;

  // Setup (admin, idle)
  if (S.role === 'admin' && tri.estado === 'idle') {
    html += `<div style="padding:14px;display:flex;flex-direction:column;gap:12px">
      <div style="font-size:12px;color:var(--txt2)">
        3 parejas fijas por cancha · Sistema de puntos pádel (0-15-30-40-Juego)
      </div>
      <div class="param-row">
        <span class="param-lbl">Cantidad de canchas</span>
        <input class="p-in" type="number" min="1" max="6" id="tri-ncanchas"
          value="${tri.canchas || 1}" oninput="triCambiarCanchas(+this.value)">
      </div>`;

    tri.grupos.forEach((grupo, ci) => {
      html += `<div style="border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:10px 12px">
        <div style="font-size:11px;font-weight:700;color:var(--txt2);margin-bottom:10px">CANCHA ${ci + 1}</div>`;
      for (let p = 0; p < 3; p++) {
        html += `<div style="margin-bottom:8px">
          <div style="font-size:10px;font-weight:700;color:${cols[p]};letter-spacing:.06em;margin-bottom:5px">PAREJA ${p + 1}</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <input class="p-in" style="flex:1;min-width:90px;text-align:left;width:auto"
              placeholder="Jugador A" value="${grupo.parejas[p]?.[0] || ''}"
              oninput="triSetJugador(${ci},${p},0,this.value)">
            <input class="p-in" style="flex:1;min-width:90px;text-align:left;width:auto"
              placeholder="Jugador B" value="${grupo.parejas[p]?.[1] || ''}"
              oninput="triSetJugador(${ci},${p},1,this.value)">
          </div>
        </div>`;
      }
      html += `</div>`;
    });

    html += `<div style="display:flex;gap:8px">
      <button class="btn-sec" onclick="triSortear()" style="flex:1">🔀 Sortear</button>
      <button class="btn-main" onclick="triIniciar()" style="flex:1;margin-top:0">▶ Iniciar</button>
    </div></div>`;
  }

  if (S.role === 'admin' && tri.estado === 'jugando') {
    html += `<div style="padding:8px 14px;border-bottom:1px solid var(--brd)">
      <button class="btn-sec" style="color:var(--red);margin-top:0" onclick="triReset()">
        🗑 Reiniciar triangular
      </button>
    </div>`;
  }
  html += `</div>`;

  if (tri.estado === 'idle' && S.role !== 'admin')
    return html + `<div class="empty"><div class="empty-ico">⏳</div>
      <div style="font-size:14px;margin-top:8px">El admin aún no inició el triangular.</div></div>`;
  if (tri.estado === 'idle') return html;

  // Una sección por cancha
  tri.grupos.forEach((grupo, ci) => {
    const todosGanados = grupo.partidos.every(pt => pt.ganador !== null);
    html += `<div class="card" style="margin-bottom:12px">
      <div class="card-hdr" style="background:rgba(255,255,255,.03)">
        <span class="card-title">Cancha ${ci + 1}</span>
        <span class="badge" style="background:${todosGanados ? 'rgba(76,217,100,.15)' : 'rgba(41,171,226,.12)'};
          color:${todosGanados ? '#4cd964' : '#29ABE2'}">
          ${todosGanados ? '✓ Finalizado' : 'En juego'}
        </span>
      </div>`;

    // Resumen parejas
    html += `<div style="display:flex;gap:6px;padding:8px 12px;flex-wrap:wrap;border-bottom:1px solid var(--brd)">`;
    grupo.parejas.forEach((par, pi) => {
      const wins = grupo.partidos.filter(
        pt => (pt.pA === pi && pt.ganador === 0) || (pt.pB === pi && pt.ganador === 1)
      ).length;
      html += `<div style="background:${colsBg[pi]};border:1px solid ${cols[pi]}40;
        border-radius:7px;padding:6px 10px;flex:1;min-width:90px">
        <div style="font-size:9px;font-weight:700;color:${cols[pi]};margin-bottom:3px">P${pi + 1} · ${wins}G</div>
        <div style="font-weight:600;font-size:12px;line-height:1.3">${par[0]}</div>
        <div style="font-size:9px;color:var(--txt3)">+</div>
        <div style="font-weight:600;font-size:12px;line-height:1.3">${par[1]}</div>
      </div>`;
    });
    html += `</div>`;

    // Partidos
    grupo.partidos.forEach((pt, pti) => {
      const parA  = grupo.parejas[pt.pA];
      const parB  = grupo.parejas[pt.pB];
      const ganado = pt.ganador !== null;
      const pA = pt.puntos[0], pB = pt.puntos[1];
      const esDeuce = pA >= 3 && pB >= 3;
      const lblA = esDeuce && pA > pB ? 'AD' : puntosLabel(pA);
      const lblB = esDeuce && pB > pA ? 'AD' : puntosLabel(pB);

      html += `<div style="padding:10px 12px;border-bottom:1px solid var(--brd);${ganado ? 'background:rgba(0,0,0,.1)' : ''}">
        <div style="font-size:9px;font-weight:600;color:var(--txt3);letter-spacing:.06em;margin-bottom:6px">
          PARTIDO ${pti + 1} ${ganado ? '✓' : '▶'}
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <div style="flex:1;min-width:0">
            <div style="font-weight:600;font-size:12px;color:${cols[pt.pA]};line-height:1.3">${parA[0]}</div>
            <div style="font-size:9px;color:var(--txt3)">+</div>
            <div style="font-weight:600;font-size:12px;color:${cols[pt.pA]};line-height:1.3">${parA[1]}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:center;gap:4px;flex-shrink:0">
            <div style="display:flex;align-items:center;gap:6px">
              <span style="font-family:'DM Mono',monospace;font-size:18px;font-weight:700;
                color:${pt.juegos[0] > pt.juegos[1] ? cols[pt.pA] : 'var(--txt)'}">
                ${pt.juegos[0]}
              </span>
              <span style="color:var(--txt3);font-size:10px">-</span>
              <span style="font-family:'DM Mono',monospace;font-size:18px;font-weight:700;
                color:${pt.juegos[1] > pt.juegos[0] ? cols[pt.pB] : 'var(--txt)'}">
                ${pt.juegos[1]}
              </span>
            </div>
            ${!ganado ? `<div style="font-size:12px;font-weight:600">
              <span style="color:${pA > pB ? cols[pt.pA] : 'var(--txt2)'}">${lblA}</span>
              <span style="color:var(--txt3);margin:0 3px">-</span>
              <span style="color:${pB > pA ? cols[pt.pB] : 'var(--txt2)'}">${lblB}</span>
            </div>`
            : `<div style="font-size:10px;color:${cols[pt.ganador === 0 ? pt.pA : pt.pB]};font-weight:600">
              Ganó P${(pt.ganador === 0 ? pt.pA : pt.pB) + 1}
            </div>`}
            ${!ganado && S.role === 'admin' ? `
              <div style="display:flex;gap:4px;margin-top:2px">
                <button onclick="triPunto(${ci},${pti},0)"
                  style="padding:5px 10px;border-radius:5px;font-size:11px;font-weight:600;
                    border:2px solid ${cols[pt.pA]};background:${colsBg[pt.pA]};color:${cols[pt.pA]};cursor:pointer">
                  +P${pt.pA + 1}
                </button>
                <button onclick="triPunto(${ci},${pti},1)"
                  style="padding:5px 10px;border-radius:5px;font-size:11px;font-weight:600;
                    border:2px solid ${cols[pt.pB]};background:${colsBg[pt.pB]};color:${cols[pt.pB]};cursor:pointer">
                  +P${pt.pB + 1}
                </button>
              </div>
              <button onclick="triDeshacerPunto(${ci},${pti})"
                style="font-size:10px;color:var(--txt3);background:transparent;border:none;cursor:pointer">
                ↩ Deshacer
              </button>` : ''}
          </div>
          <div style="flex:1;min-width:0;text-align:right">
            <div style="font-weight:600;font-size:12px;color:${cols[pt.pB]};line-height:1.3">${parB[0]}</div>
            <div style="font-size:9px;color:var(--txt3)">+</div>
            <div style="font-weight:600;font-size:12px;color:${cols[pt.pB]};line-height:1.3">${parB[1]}</div>
          </div>
        </div>
      </div>`;
    });

    // Resultado de la cancha
    if (todosGanados) {
      const wins = grupo.parejas.map((_, pi) =>
        grupo.partidos.filter(pt =>
          (pt.pA === pi && pt.ganador === 0) || (pt.pB === pi && pt.ganador === 1)
        ).length
      );
      const maxW = Math.max(...wins);
      const cam  = grupo.parejas.filter((_, pi) => wins[pi] === maxW);
      html += `<div style="padding:12px;text-align:center;border-top:1px solid var(--brd)">
        <div style="font-size:11px;font-weight:700;color:#4cd964">
          🏆 ${cam.map(c => c.join('+')).join(' · ')} ${cam.length > 1 ? '(empate)' : ''}
        </div>
        <div style="font-size:10px;color:var(--txt3);margin-top:3px">
          ${grupo.parejas.map((p, pi) => `P${pi + 1}: ${wins[pi]}G`).join(' · ')}
        </div>
      </div>`;
    }
    html += `</div>`;
  });

  return html;
}


// ── Lógica de juego ───────────────────────────────────────────────────────────
function triCambiarCanchas(n) {
  n = Math.max(1, Math.min(6, n || 1));
  S.tri.canchas = n;
  while (S.tri.grupos.length < n) S.tri.grupos.push(triGrupoInicial());
  while (S.tri.grupos.length > n) S.tri.grupos.pop();
  guardarTri();
  renderTab();
}

function triSetJugador(cancha, pareja, pos, nombre) {
  S.tri.grupos[cancha].parejas[pareja][pos] = nombre;
  guardarTri();
}

function triSortear() {
  if (!S.state?.jugadores?.length) { toast('Cargá jugadores primero'); return; }
  const nombres = S.state.jugadores.map(j => j.nombre).filter(n => n);
  for (let i = nombres.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [nombres[i], nombres[j]] = [nombres[j], nombres[i]];
  }
  S.tri.grupos.forEach((grupo, ci) => {
    const base = ci * 6;
    grupo.parejas = [
      [nombres[base]     || '', nombres[base + 1] || ''],
      [nombres[base + 2] || '', nombres[base + 3] || ''],
      [nombres[base + 4] || '', nombres[base + 5] || ''],
    ];
  });
  guardarTri();
  renderTab();
  toast('🔀 Parejas sorteadas');
}

function triIniciar() {
  for (const g of S.tri.grupos) {
    if (g.parejas.some(par => !par[0].trim() || !par[1].trim())) {
      toast('Completá todos los jugadores de todas las canchas');
      return;
    }
  }
  S.tri.estado = 'jugando';
  guardarTri();
  renderTab();
  toast('🔺 Triangular iniciado');
}

function triReset() {
  if (!confirm('¿Reiniciar el triangular?')) return;
  S.tri = triEstadoInicial(S.tri.canchas || 1);
  guardarTri();
  renderTab();
}

function triPunto(canchaIdx, partidoIdx, quien) {
  const pt = S.tri.grupos[canchaIdx].partidos[partidoIdx];
  if (pt.ganador !== null) return;

  // Guardar estado para deshacer
  pt.historial.push({
    puntos:  [...pt.puntos],
    juegos:  [...pt.juegos],
    ganador: pt.ganador,
  });

  pt.puntos[quien]++;
  const pA = pt.puntos[0], pB = pt.puntos[1];
  const esDeuce = pA >= 3 && pB >= 3;

  let ganoJuego = false;
  let quienJuego = quien;

  if (!esDeuce) {
    if (pt.puntos[quien] >= 4) ganoJuego = true;
  } else {
    if (Math.abs(pA - pB) >= 2) {
      ganoJuego  = true;
      quienJuego = pA > pB ? 0 : 1;
    }
  }

  if (ganoJuego) {
    pt.juegos[quienJuego]++;
    pt.puntos = [0, 0];
    const jA = pt.juegos[0], jB = pt.juegos[1];

    let ganoSet = false;
    if      (jA >= 6 && jA - jB >= 2) ganoSet = true;
    else if (jB >= 6 && jB - jA >= 2) ganoSet = true;
    else if (jA === 7 || jB === 7)     ganoSet = true; // tie-break

    if (ganoSet) {
      pt.ganador = jA > jB ? 0 : 1;
      // ¿Terminó todo?
      const todosEnCancha = S.tri.grupos[canchaIdx].partidos.every(p => p.ganador !== null);
      if (todosEnCancha && S.tri.grupos.every(g => g.partidos.every(p => p.ganador !== null)))
        S.tri.estado = 'finalizado';
    }
  }

  guardarTri();
  renderTab();
}

function triDeshacerPunto(canchaIdx, partidoIdx) {
  const pt = S.tri.grupos[canchaIdx].partidos[partidoIdx];
  if (!pt.historial.length) return;
  const prev = pt.historial.pop();
  pt.puntos  = prev.puntos;
  pt.juegos  = prev.juegos;
  pt.ganador = prev.ganador;
  if (S.tri.estado === 'finalizado') S.tri.estado = 'jugando';
  guardarTri();
  renderTab();
}
