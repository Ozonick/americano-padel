/**
 * beta.js — Versión beta (/beta)
 * Es la misma app (admin, configuración, finales y demás modos), pero el Fixture y las
 * Posiciones se ven con el tablero nuevo: canchas con fichas, tabla por ronda y "mis partidos".
 * En la versión normal (/) este archivo no hace nada.
 */
(() => {
  if (location.pathname.replace(/\/+$/, '') !== '/beta') return;

  // ── Preferencias de este dispositivo ──────────────────────────────────────
  const VISTAS = ['cancha', 'tabla', 'jugador'];
  const B = { vista: 'cancha', ronda: null, jug: '' };
  try {
    const p = JSON.parse(localStorage.getItem('beta-panteras') || '{}');
    if (VISTAS.includes(p.vista)) B.vista = p.vista;
    if (typeof p.jug === 'string') B.jug = p.jug;
  } catch (e) {}
  function guardarPrefs() {
    try { localStorage.setItem('beta-panteras', JSON.stringify({ vista: B.vista, jug: B.jug })); } catch (e) {}
  }

  // ── Utilidades ────────────────────────────────────────────────────────────
  const esc = s => String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const listaY = xs => xs.length <= 1 ? xs.join('') : xs.slice(0, -1).join(', ') + ' y ' + xs[xs.length - 1];
  const nombres = xs => listaY(xs.map(esc));
  const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
  const ptsTxt = n => n === 1 ? '1 pt' : `${n} pts`;
  const chipPts = n => `<span class="bt-chip ${n === PTS_GANA ? 'g' : n === PTS_EMPATA ? 'e' : 'p'}">+${ptsTxt(n)}</span>`;
  const games = () => parseInt(S.state?.config?.games_partido) || 16;

  // Mismo corte que la pestaña Finales: 1°-2° Oro, 3°-4° Plata, 5°-6° Bronce
  const COPAS = [
    { nombre: 'Copa Oro',    color: '#C9A84C', pos: [0, 1] },
    { nombre: 'Copa Plata',  color: '#4da6ff', pos: [2, 3] },
    { nombre: 'Copa Bronce', color: '#c4956a', pos: [4, 5] },
  ];
  const copaDe = i => COPAS.find(c => c.pos.includes(i));


  // ── Modelo: grupos con sus rondas y resultados ────────────────────────────
  function modelo() {
    const { grupos, fixtures_prel, resultados, config } = S.state;
    const rp = parseInt(config?.rondas_prel) || 7;
    return (grupos || []).map((noms, gi) => ({
      gi, nombres: noms, col: COLORES[gi % COLORES.length],
      rondas: ((fixtures_prel || [])[gi] || []).slice(0, rp).map(([j1, j2, j3, j4], ri) => {
        const res    = (resultados || {})[`prel-${gi}-${ri}`] || {};
        const jugado = res.ga != null && res.gb != null;
        return {
          ri, a: [j1, j2], b: [j3, j4], rest: noms.filter(n => ![j1, j2, j3, j4].includes(n)),
          jugado, ga: jugado ? +res.ga : null, gb: jugado ? +res.gb : null,
        };
      }),
    }));
  }
  const visibles = M => S.canchaVista === 'todas' ? M : M.filter(g => g.gi === S.canchaVista);
  const nRondas  = gs => gs.reduce((m, g) => Math.max(m, g.rondas.length), 0);

  // Primera ronda que todavía tiene algún partido sin resultado
  function rondaActual(gs) {
    const n = nRondas(gs);
    for (let i = 0; i < n; i++) if (gs.some(g => g.rondas[i] && !g.rondas[i].jugado)) return i;
    return Math.max(0, n - 1);
  }


  // ── Piezas comunes ────────────────────────────────────────────────────────
  function barraHTML() {
    let fz = 0;
    try { fz = parseInt(localStorage.getItem('fz')) || 0; } catch (e) {}
    const vistas = [['cancha', 'En cancha'], ['tabla', 'Tabla'], ['jugador', 'Mis partidos']];
    return `<div class="bt-barra">
      <div class="bt-seg" role="group" aria-label="Forma de ver el fixture">
        ${vistas.map(([v, t]) => `<button type="button" data-bt-vista="${v}" aria-pressed="${B.vista === v}">${t}</button>`).join('')}
      </div>
      <div class="bt-fz" role="group" aria-label="Tamaño de letra"><span>Letra</span>
        ${['A', 'A+', 'A++'].map((t, i) => `<button type="button" data-bt-fz="${i}" aria-pressed="${fz === i}">${t}</button>`).join('')}
      </div>
    </div>`;
  }

  // Inputs de games: mismos atributos que el fixture normal, así se reutiliza autoFill()
  function inputsHTML(g, r) {
    const ng = games();
    const inp = (side, val, par) => `<input class="g-in" type="number" inputmode="numeric" min="0" max="${ng}"
      value="${val ?? ''}" placeholder="—" style="border-color:${g.col.brd}"
      data-pair="${g.gi}-${r.ri}" data-side="${side}" data-total="${ng}" data-key="prel-${g.gi}-${r.ri}"
      aria-label="Games de ${esc(par.join(' y '))}" oninput="autoFill(this)">`;
    return `<div class="games-wrap">${inp('a', r.ga, r.a)}<span class="g-dash">—</span>${inp('b', r.gb, r.b)}</div>`;
  }

  // Centro del partido: inputs para el admin, marcador para el resto
  function centroHTML(g, r) {
    const chips = r.jugado ? chipsHTML(ptsLabel(ptsPartido(r.ga, r.gb)), ptsLabel(ptsPartido(r.gb, r.ga))) : '';
    const centro = esAdmin() ? inputsHTML(g, r)
      : r.jugado ? `<span class="bt-res">${r.ga} – ${r.gb}</span>`
      : '<span class="bt-pend">por jugar</span>';
    return `${centro}<div id="chips-${g.gi}-${r.ri}" class="bt-chips">${chips}</div>`;
  }


  // ── Vista: En cancha ──────────────────────────────────────────────────────
  const POS = {
    a: [{ x: 24, y: 20.83 }, { x: 24, y: 48.61 }],
    b: [{ x: 76, y: 20.83 }, { x: 76, y: 48.61 }],
  };
  // Lugares en el banco según cuántos descansan (una fila hasta 3, después dos filas)
  function posBanco(n) {
    const fila = (k, y) => {
      const span = k < 2 ? 0 : k === 2 ? 32 : 52;
      return Array.from({ length: k }, (_, i) => ({ x: k < 2 ? 60 : 60 - span / 2 + i * span / (k - 1), y }));
    };
    if (n <= 3) return fila(n, 84.72);
    const arriba = Math.ceil(n / 2);
    return fila(arriba, 78.5).concat(fila(n - arriba, 92));
  }
  const LINEAS = '<svg viewBox="0 0 200 100" preserveAspectRatio="none" aria-hidden="true">'
    + '<g fill="none" stroke="#fff" stroke-width="1.6">'
    + '<rect x="2" y="2" width="196" height="96" vector-effect="non-scaling-stroke"/>'
    + '<line x1="30.5" y1="2" x2="30.5" y2="98" vector-effect="non-scaling-stroke"/>'
    + '<line x1="169.5" y1="2" x2="169.5" y2="98" vector-effect="non-scaling-stroke"/>'
    + '<line x1="30.5" y1="50" x2="169.5" y2="50" vector-effect="non-scaling-stroke"/></g>'
    + '<line x1="100" y1="2" x2="100" y2="98" stroke="#fff" stroke-width="3.2" stroke-dasharray="3 2" vector-effect="non-scaling-stroke"/></svg>';

  // Una cancha por grupo que se reutiliza entre renders, así las fichas se animan al cambiar de ronda
  const CAJAS = {};
  let ULTIMO = [];
  function cajaDe(g) {
    const key = g.nombres.join('\n');
    if (CAJAS[g.gi]?.dataset.key === key) return CAJAS[g.gi];
    const caja = document.createElement('div');
    caja.className = 'bt-pista-caja'; caja.dataset.key = key;
    caja.innerHTML = `<div class="bt-pista">${LINEAS}</div><span class="bt-banco">Descansan</span>`
      + g.nombres.map(n => `<div class="bt-ficha" style="--x:50%;--y:50%">${esc(n)}</div>`).join('');
    caja.querySelectorAll('.bt-ficha').forEach((f, i) => { f.dataset.n = g.nombres[i]; });
    return (CAJAS[g.gi] = caja);
  }
  function pintarCancha(caja, r) {
    const banco = posBanco(r.rest.length);
    caja.querySelectorAll('.bt-ficha').forEach(f => {
      const n = f.dataset.n;
      let i, p, cls;
      if ((i = r.a.indexOf(n)) > -1)      { p = POS.a[i]; cls = 'par-a'; }
      else if ((i = r.b.indexOf(n)) > -1) { p = POS.b[i]; cls = 'par-b'; }
      else                                { p = banco[r.rest.indexOf(n)]; cls = 'libre'; }
      f.hidden = !p;
      if (!p) return;
      f.style.setProperty('--x', p.x + '%');
      f.style.setProperty('--y', p.y + '%');
      f.className = `bt-ficha ${cls}${n === B.jug ? ' yo' : ''}`;
    });
    caja.querySelector('.bt-banco').hidden = !r.rest.length;
  }
  // Se llama después de que renderTab() puso el HTML: mete cada cancha en su lugar y mueve las fichas
  function montarCanchas() {
    document.querySelectorAll('#main-content .bt-caja[data-g]').forEach(ph => {
      const g = ULTIMO[+ph.dataset.g], r = g?.rondas[B.ronda];
      if (!r) return;
      const caja = cajaDe(g);
      if (caja.parentNode !== ph) ph.appendChild(caja);
      caja.getBoundingClientRect();   // fuerza layout para que la transición arranque desde la ronda anterior
      pintarCancha(caja, r);
    });
  }

  function vistaCancha(vis) {
    const n = nRondas(vis), actual = rondaActual(vis);
    const botones = Array.from({ length: n }, (_, i) => {
      const hecha = vis.every(g => !g.rondas[i] || g.rondas[i].jugado);
      return `<button type="button" class="bt-rb${hecha ? ' hecha' : ''}${i === actual ? ' actual' : ''}"
        data-bt-ronda="${i}" aria-pressed="${i === B.ronda}"
        aria-label="Ronda ${i + 1}${hecha ? ', con resultado' : i === actual ? ', en juego' : ''}">${i + 1}</button>`;
    }).join('');

    const canchas = vis.map(g => {
      const r = g.rondas[B.ronda];
      const estado = !r ? '' : r.jugado ? '✓ Jugado' : `hasta ${games()} games`;
      const cuerpo = !r ? '<div class="bt-sin">Sin partido en esta ronda</div>'
        : `<div class="bt-caja" data-g="${g.gi}"></div>
           <div class="bt-score">
             <div class="bt-par${r.jugado && r.ga > r.gb ? ' gano' : ''}">${esc(r.a[0])}<br>${esc(r.a[1])}</div>
             <div class="bt-centro">${centroHTML(g, r)}</div>
             <div class="bt-par der${r.jugado && r.gb > r.ga ? ' gano' : ''}">${esc(r.b[0])}<br>${esc(r.b[1])}</div>
           </div>`;
      return `<section class="card">
        <div class="card-hdr" style="background:${g.col.bg};border-bottom:2px solid ${g.col.txt}40">
          <span class="card-title" style="color:${g.col.txt}">Cancha ${g.gi + 1} · Grupo ${LETRAS[g.gi]}</span>
          ${estado ? `<span class="badge" style="background:rgba(0,0,0,.25);color:${g.col.txt};border:none">${estado}</span>` : ''}
        </div>${cuerpo}</section>`;
    }).join('');

    return `<div class="bt-rondas"><span class="etq">Ronda</span>${botones}
        <span class="bt-ley"><i></i>con resultado</span></div>
      <div class="bt-canchas${vis.length === 1 ? ' una' : ''}">${canchas}</div>`;
  }


  // ── Vista: Tabla (ronda × cancha) ─────────────────────────────────────────
  function vistaTabla(vis) {
    let filas = '';
    for (let i = 0; i < nRondas(vis); i++) {
      filas += `<tr class="${i === B.ronda ? 'act' : ''}"><th scope="row" class="rd">${i + 1}</th>` + vis.map(g => {
        const r = g.rondas[i], etq = `Cancha ${g.gi + 1} · Grupo ${LETRAS[g.gi]}`;
        if (!r) return `<td data-c="${etq}"><div class="ds">Sin partido</div></td>`;
        return `<td data-c="${etq}">
          <div class="p${r.jugado && r.ga > r.gb ? ' gano' : ''}">${esc(r.a[0])} + ${esc(r.a[1])}</div>
          <div class="bt-fila-res">${centroHTML(g, r)}</div>
          <div class="p${r.jugado && r.gb > r.ga ? ' gano' : ''}">${esc(r.b[0])} + ${esc(r.b[1])}</div>
          ${r.rest.length ? `<div class="ds">Descansan ${nombres(r.rest)}</div>` : ''}</td>`;
      }).join('') + '</tr>';
    }
    return `<div class="card bt-tabla"><table class="bt-mx">
      <thead><tr><th scope="col">Ronda</th>${vis.map(g =>
        `<th scope="col" style="color:${g.col.txt}">Cancha ${g.gi + 1} · Grupo ${LETRAS[g.gi]}</th>`).join('')}</tr></thead>
      <tbody>${filas}</tbody></table></div>`;
  }


  // ── Vista: Mis partidos ───────────────────────────────────────────────────
  function vistaJugador(vis) {
    const selector = vis.map(g => `<div class="bt-elegir-g">
        <span class="lbl" style="color:${g.col.txt}">Cancha ${g.gi + 1}</span>
        ${g.nombres.map(n => `<button type="button" class="bt-jb" data-bt-jug="${esc(n)}" aria-pressed="${n === B.jug}">${esc(n)}</button>`).join('')}
      </div>`).join('');
    const g = vis.find(x => x.nombres.includes(B.jug));
    const cab = `<div class="card"><div class="card-hdr"><span class="card-title">¿Quién sos?</span></div>
      <div class="bt-elegir">${selector}</div></div>`;
    if (!g) return cab + '<p class="bt-hint">Tocá tu nombre para ver tus partidos, tu puesto y tus puntos.</p>';

    const yo = B.jug, items = [], descansa = [], comp = new Set();
    let partidos = 0, jugados = 0;
    g.rondas.forEach((r, i) => {
      const enA = r.a.includes(yo), enB = r.b.includes(yo);
      if (!enA && !enB) {
        descansa.push(i + 1);
        items.push(`<li class="descansa"><span class="r">Ronda ${i + 1}</span><span>${r.jugado ? 'Descansaste' : 'Descansás'}</span></li>`);
        return;
      }
      partidos++;
      const mia = enA ? r.a : r.b, rival = enA ? r.b : r.a, c = mia.find(q => q !== yo);
      comp.add(c);
      let res = '';
      if (r.jugado) {
        jugados++;
        const pro = enA ? r.ga : r.gb, con = enA ? r.gb : r.ga;
        res = `<span class="res-l">${pro > con ? 'Ganaste' : pro === con ? 'Empataste' : 'Perdiste'} ${pro} – ${con} ${chipPts(ptsPartido(pro, con))}</span>`;
      }
      items.push(`<li class="juega${i === B.ronda ? ' act' : ''}"><span class="r">Ronda ${i + 1}</span><span>${r.jugado ? 'Jugaste' : 'Jugás'}
        con <strong>${esc(c)}</strong> contra ${nombres(rival)}${res}</span></li>`);
    });

    const stats = calcStats(), orden = sortGrupo(g.nombres, stats), puesto = orden.indexOf(yo), copa = copaDe(puesto);
    let txt = `<strong>${esc(yo)}</strong>, `;
    if (g.rondas.some(r => r.jugado)) {
      txt += `vas <b>${puesto + 1}°</b> en el Grupo ${LETRAS[g.gi]} con <b>${ptsTxt(stats[yo]?.pts || 0)}</b>`
        + (copa ? ` (hoy entrás a la ${copa.nombre})` : '') + `. Jugaste ${jugados} de ${plural(partidos, 'partido', 'partidos')}`;
    } else {
      txt += `jugás <b>${plural(partidos, 'partido', 'partidos')}</b>`;
    }
    txt += ` con ${plural(comp.size, 'compañero distinto', 'compañeros distintos')}. `
      + (descansa.length ? `Descansás en ${descansa.length === 1 ? 'la ronda' : 'las rondas'} <b>${listaY(descansa)}</b>.` : 'No descansás ninguna ronda.');

    return cab + `<div class="card"><p class="bt-resumen">${txt}</p><ul class="bt-linea">${items.join('')}</ul></div>`;
  }


  // ── Fixture (reemplaza al de americano.js) ────────────────────────────────
  function renderFixtureBeta() {
    pendiente = false;
    const M = modelo();
    if (!M.length) return noJugadores();
    ULTIMO = M;
    const vis = visibles(M);
    if (B.ronda == null) B.ronda = rondaActual(M);
    B.ronda = Math.min(B.ronda, Math.max(0, nRondas(vis) - 1));
    const cuerpo = B.vista === 'tabla' ? vistaTabla(vis) : B.vista === 'jugador' ? vistaJugador(vis) : vistaCancha(vis);
    if (B.vista === 'cancha') queueMicrotask(montarCanchas);
    return barraHTML() + cuerpo;
  }


  // ── Posiciones (reemplaza a la de americano.js) ───────────────────────────
  function comoSePuntua(M) {
    const ng = games(), r = M[0]?.rondas[0];
    const a = r ? `${esc(r.a[0])} + ${esc(r.a[1])}` : 'Pareja 1', b = r ? `${esc(r.b[0])} + ${esc(r.b[1])}` : 'Pareja 2';
    const gana = Math.min(ng, Math.floor(ng / 2) + 2);
    return `<details class="card bt-punt"><summary>Cómo se puntúa</summary><div class="bt-punt-in">
      <p>Cada partido es a <strong>${ng} games</strong>. Cada jugador de la pareja suma
        <span class="bt-chip g">${ptsTxt(PTS_GANA)}</span> si gana,
        <span class="bt-chip e">${ptsTxt(PTS_EMPATA)}</span> si empata y
        <span class="bt-chip p">${ptsTxt(PTS_PIERDE)}</span> si pierde.</p>
      <div class="bt-ej"><span>${a}</span><span class="res">${gana} – ${ng - gana}</span><span>${b}</span>
        <span class="bt-chip g">${ptsTxt(PTS_GANA)} c/u</span><span class="bt-chip p">${ptsTxt(PTS_PIERDE)} c/u</span></div>
      ${ng % 2 === 0 ? `<div class="bt-ej"><span>${a}</span><span class="res">${ng / 2} – ${ng / 2}</span><span>${b}</span>
        <span class="bt-chip e">${ptsTxt(PTS_EMPATA)} c/u</span></div>` : ''}
      <p>La tabla se ordena por <strong>puntos</strong>, después por <strong>diferencia de games</strong> y después por <strong>games a favor</strong>.
        Al terminar, 1° y 2° de cada grupo van a la Copa Oro, 3° y 4° a la Plata y 5° y 6° a la Bronce.</p>
    </div></details>`;
  }

  function renderPosicionesBeta() {
    const M = modelo();
    if (!M.length) return noJugadores();
    const stats = calcStats();
    const tarjetas = M.map(g => {
      const gep = {};
      g.nombres.forEach(n => { gep[n] = { g: 0, e: 0, p: 0 }; });
      g.rondas.forEach(r => {
        if (!r.jugado) return;
        const k = (pro, con) => pro > con ? 'g' : pro === con ? 'e' : 'p';
        r.a.forEach(n => { if (gep[n]) gep[n][k(r.ga, r.gb)]++; });
        r.b.forEach(n => { if (gep[n]) gep[n][k(r.gb, r.ga)]++; });
      });
      const jugadas = g.rondas.filter(r => r.jugado).length;
      const filas = sortGrupo(g.nombres, stats).map((n, i) => {
        const s = stats[n] || { pj: 0, gf: 0, gc: 0, pts: 0 }, d = s.gf - s.gc, copa = copaDe(i), x = gep[n];
        return `<tr class="${n === B.jug ? 'yo' : ''}"${copa ? ` style="--copa:${copa.color}"` : ''}>
          <td class="ps">${i + 1}</td><td class="l nm">${esc(n)}</td>
          <td class="pt" style="color:${g.col.txt}">${s.pts}</td><td class="anc">${s.pj}</td>
          <td>${x.g}-${x.e}-${x.p}</td>
          <td class="${d > 0 ? 'mas' : d < 0 ? 'menos' : ''}">${d > 0 ? '+' : ''}${d}</td><td class="anc">${s.gf}</td></tr>`;
      }).join('');
      return `<section class="card">
        <div class="card-hdr" style="background:${g.col.bg};border-bottom:2px solid ${g.col.txt}40">
          <span class="card-title" style="color:${g.col.txt}">Grupo ${LETRAS[g.gi]} · Cancha ${g.gi + 1}</span>
          <span class="badge" style="background:rgba(0,0,0,.25);color:${g.col.txt};border:none">
            ${jugadas ? `${jugadas}/${g.rondas.length} rondas` : 'sin resultados'}</span>
        </div>
        <table class="bt-pos">
          <thead><tr><th>#</th><th class="l">Jugador</th><th>Pts</th><th class="anc">PJ</th>
            <th title="Ganados - Empatados - Perdidos">G-E-P</th><th title="Diferencia de games">Dif</th>
            <th class="anc" title="Games a favor">GF</th></tr></thead>
          <tbody>${filas}</tbody>
        </table></section>`;
    }).join('');
    const maxJug = Math.max(...M.map(g => g.nombres.length));
    const copas = COPAS.filter(c => c.pos[0] < maxJug).map(c =>
      `<li style="--copa:${c.color}"><i></i>${c.nombre} · ${c.pos[0] + 1}° y ${c.pos[1] + 1}°</li>`).join('');
    return `<div class="bt-pos-grid">${tarjetas}</div><ul class="bt-copas">${copas}</ul>${comoSePuntua(M)}`;
  }


  // ── Enganche con la app ───────────────────────────────────────────────────
  window.renderFixture    = renderFixtureBeta;
  window.renderPosiciones = renderPosicionesBeta;

  // Mientras el admin escribe un resultado la app no redibuja (solo los chips).
  // Al salir del input se redibuja una vez para mostrar marcadores y rondas al día.
  let pendiente = false;
  const updatePtsChipsOrig = window.updatePtsChips;
  window.updatePtsChips = (data) => { pendiente = true; updatePtsChipsOrig(data); };
  document.addEventListener('focusout', (e) => {
    if (!e.target.classList?.contains('g-in') || e.relatedTarget) return;
    if (pendiente && S.tab === 'fixture') setTimeout(renderTab, 0);
  });

  // Letra grande: además del zoom de la app, agranda las fichas y libera lugar en el header del celular
  const aplicarFontSizeOrig = window.aplicarFontSize;
  window.aplicarFontSize = () => {
    aplicarFontSizeOrig();
    let n = 0;
    try { n = parseInt(localStorage.getItem('fz')) || 0; } catch (e) {}
    document.documentElement.dataset.btFz = n;
  };
  window.aplicarFontSize();

  // Botones de las vistas nuevas (un solo listener para todo el contenido)
  document.getElementById('main-content').addEventListener('click', (e) => {
    const t = e.target.closest('[data-bt-vista],[data-bt-ronda],[data-bt-jug],[data-bt-fz]');
    if (!t) return;
    const d = t.dataset;
    let sel;
    if (d.btVista)           { B.vista = d.btVista; guardarPrefs(); sel = `[data-bt-vista="${d.btVista}"]`; }
    else if (d.btRonda)      { B.ronda = +d.btRonda; sel = `[data-bt-ronda="${d.btRonda}"]`; }
    else if (d.btJug != null) { B.jug = d.btJug; guardarPrefs(); sel = `[data-bt-jug="${CSS.escape(d.btJug)}"]`; }
    else                     { setFontSize(+d.btFz); sel = `[data-bt-fz="${d.btFz}"]`; }
    renderTab();
    document.querySelector(`#main-content ${sel}`)?.focus({ preventScroll: true });
  });

  // Header: el botón amarillo pasa a ser "volver a la versión actual"
  document.title = 'Panteras Pádel · Beta';
  document.head.insertAdjacentHTML('beforeend', '<link rel="stylesheet" href="/static/beta.css">');
  const btn = document.querySelector('.beta-btn');
  if (btn) {
    btn.href = '/';
    btn.classList.add('en-beta');
    btn.title = 'Volver a la versión actual';
    btn.setAttribute('aria-label', 'Volver a la versión actual');
    btn.querySelector('.beta-largo').textContent = '← Versión actual';
    btn.querySelector('.beta-corto').textContent = '← Actual';
  }

  // El estado puede haber llegado por WebSocket mientras se descargaba este archivo
  if (S.state) renderTab();
})();
