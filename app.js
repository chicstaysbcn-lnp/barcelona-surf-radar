/* BCN Surf Radar · web movil sin dependencias ni APIs secretas en cliente. */
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const state = { snapshot: null, profiles: [], day: 0, profile: 'intermedio', selected: null };
  const tm = new Intl.DateTimeFormat('es-ES', { timeZone: 'Europe/Madrid', hour: '2-digit', minute: '2-digit', hour12: false });
  const dayFormatter = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Madrid', day: '2-digit', month: '2-digit', year: 'numeric' });
  const dateTitle = new Intl.DateTimeFormat('es-ES', { timeZone: 'Europe/Madrid', weekday: 'short', day: 'numeric', month: 'short' });
  const exactDate = new Intl.DateTimeFormat('es-ES', { timeZone: 'Europe/Madrid', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
  const safe = x => (x == null || !Number.isFinite(Number(x))) ? '—' : String(x);
  const fmt = (x, digits = 1) => x == null || !Number.isFinite(Number(x)) ? '—' : Number(x).toLocaleString('es-ES', { maximumFractionDigits: digits, minimumFractionDigits: digits });
  const dt = iso => new Date(iso);
  const clock = iso => tm.format(dt(iso));
  const alertThreshold = () => state.snapshot?.alert_threshold ?? 76;
  const scoreClass = n => n >= 72 ? 'score-good' : n >= 48 ? 'score-mid' : 'score-poor';
  const gradeText = n => n >= 81 ? 'Muy buenas' : n >= 72 ? 'Buenas' : n >= 58 ? 'Aceptables' : n >= 40 ? 'Flojas' : 'Sin condiciones';
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'];
  const cardinal = degrees => degrees == null ? '—' : dirs[Math.round(((Number(degrees) + 360) % 360) / 45) % 8];
  const weatherDesc = (code, rain) => {
    if (code === 95 || code === 96 || code === 99) return 'Tormenta prevista';
    if ((rain || 0) > 1.2 || (code >= 61 && code <= 82)) return 'Probable lluvia';
    if (code === 0) return 'Despejado';
    if (code <= 3) return 'Nubes y claros';
    if ((rain || 0) > .15) return 'Lluvia ligera';
    return 'Variable';
  };
  const pad = x => String(x).padStart(2,'0');
  function dateParts(date) {
    const p = Object.fromEntries(dayFormatter.formatToParts(date).filter(x => x.type !== 'literal').map(x => [x.type, x.value]));
    return { day: Number(p.day), month: Number(p.month), year: Number(p.year) };
  }
  function dateKey(date) {
    const d = dateParts(date);
    return `${d.year}-${pad(d.month)}-${pad(d.day)}`;
  }
  function targetDate(dayOffset) {
    const d = dateParts(new Date());
    const civil = new Date(Date.UTC(d.year, d.month - 1, d.day + dayOffset, 12));
    return `${civil.getUTCFullYear()}-${pad(civil.getUTCMonth()+1)}-${pad(civil.getUTCDate())}`;
  }
  function dateMatch(iso, date) { return dateKey(dt(iso)) === date; }
  function loadPreferences() { try { const s=localStorage.getItem('bcn-surf-profile'); if (['principiante','intermedio','avanzado'].includes(s)) state.profile=s; } catch(_){} }
  function currentAndDayHours(spot, offset) {
    const date = targetDate(offset), earliest = Date.now() - 40 * 60 * 1000;
    return (spot.hours || []).filter(h => dateMatch(h.time, date) && Date.parse(h.time) >= earliest).sort((a,b)=>Date.parse(a.time)-Date.parse(b.time));
  }
  function session(spot, offset) {
    const hours = currentAndDayHours(spot, offset).filter(h => h.is_day && !h.danger && h.wave_m != null && h.wind_kn != null);
    const pairCandidates = [];
    for (let i = 0; i < hours.length - 1; i++) {
      if (Date.parse(hours[i+1].time) - Date.parse(hours[i].time) !== 3600000) continue;
      const a=hours[i], b=hours[i+1];
      pairCandidates.push({hour:a, next:b, duration:2, score:Math.round((a.scores[state.profile]+b.scores[state.profile])/2),
        meanWave:(a.wave_m+b.wave_m)/2, meanWind:(a.wind_kn+b.wind_kn)/2});
    }
    if (pairCandidates.length) return pairCandidates.sort((a,b)=>b.score-a.score || Date.parse(a.hour.time)-Date.parse(b.hour.time))[0];
    if (hours.length) {
      const h=hours.sort((a,b)=>b.scores[state.profile]-a.scores[state.profile] || Date.parse(a.time)-Date.parse(b.time))[0];
      return {hour:h,next:null,duration:1,score:h.scores[state.profile],meanWave:h.wave_m,meanWind:h.wind_kn};
    }
    return {hour:null,next:null,duration:0,score:0,meanWave:null,meanWind:null};
  }
  function ranking() {
    return (state.snapshot?.spots || []).map(spot=> ({ spot, s: session(spot, state.day) })).sort((a,b)=>b.s.score-a.s.score || a.spot.name.localeCompare(b.spot.name,'es'));
  }
  function displayTime(s){ return s.hour ? `${clock(s.hour.time)} — ${pad((Number(clock(s.hour.time).split(':')[0])+s.duration)%24)}:${clock(s.hour.time).split(':')[1]}` : 'Sin ventana'; }
  function spotSummary(item){const h=item.s.hour;return h ? `${fmt(h.wave_m,2)} m · ${fmt(h.period_s,0)} s · ${fmt(h.wind_kn,0)} kn` : 'Sin datos suficientes';}
  function stat(label,value,unit){return `<div class="stat-box"><label>${label}</label><strong>${value} <small>${unit}</small></strong></div>`;}
  function overview() {
    const order=ranking(), a=order[0], b=order[1], c=order[2];
    if (!a || !a.s.hour) {
      $('#overview').innerHTML = `<div class="empty-state"><div class="empty-mark">〰</div><h2>No hay ventanas diurnas disponibles</h2><p>Seleccioná otro día o volvé cuando haya un nuevo pronóstico.</p></div>`;
      $('#overview').style.minHeight='auto';return;
    }
    const h=a.s.hour, n=a.s.score, duration=a.s.duration;
    const sub = n>=alertThreshold() ? 'Hay una ventana con condiciones favorables.' : n>=60 ? 'Podría haber algo para aprovechar.' : 'No se ve una sesión especialmente buena.';
    const closeScores = b && Math.abs(n - b.s.score)<=5 ? 'Los primeros puestos están a ≤5 puntos: empate técnico probable. ' : '';
    const mini = (item,index) => {
      if (!item) return '';
      return `<button type="button" data-select="${esc(item.spot.id)}" class="mini-card select-spot" aria-label="Ver pronóstico de ${esc(item.spot.name)}"><div class="mini-l"><div class="rank-line"><span class="rank-medal">0${index}</span> ${index===3?'TERCERA OPCIÓN':'SEGUNDA OPCIÓN'}</div><h3>${esc(item.spot.name)}</h3><div class="mini-summary">${esc(item.s.hour ? displayTime(item.s) : 'Sin ventana')}<br>${esc(spotSummary(item))}</div></div><div class="mini-score ${scoreClass(item.s.score)}">${item.s.score}<small>/100</small></div></button>`;
    };
    $('#overview').innerHTML = `<div class="hero-overview"><article class="best-card"><div class="topline"><span class="tag-top">MEJOR OPCIÓN DEL DÍA</span><span class="grade"><span class="grade-dot"></span>${esc(gradeText(n))}</span></div><div class="best-main"><div><h2>${esc(a.spot.name)}</h2><a href="#detalle" class="time-range" data-select="${esc(a.spot.id)}">◷ ${esc(displayTime(a.s))} <span aria-hidden="true">↗</span></a></div><div class="score-ring" style="--score:${Math.max(0,Math.min(100,n))}"><div class="score-inner"><span class="score-num">${n}</span><span class="score-unit">/ 100</span></div></div></div><div class="best-stats">${stat('ALTURA',fmt(h.wave_m,2),'m')}${stat('PERÍODO',fmt(h.period_s,0),'s')}${stat('VIENTO',fmt(h.wind_kn,0),'kn')}${stat('SWELL',cardinal(h.swell_dir),'')}</div></article><div class="top-other">${mini(b,2)}${mini(c,3)}</div></div><p class="recommend-note"><strong>${esc(sub)}</strong> ${esc(closeScores)}Ventana recomendada de ${duration} h · Previsión orientativa mar adentro, no altura de ola rompiendo. Avisos automáticos: ≥${alertThreshold()}/100 y 2 h seguidas, si hay fuentes suficientes.</p>`;
  }
  function chart(spot) {
    if (!spot) {$('#forecast-chart').textContent='Todavía no hay datos para el gráfico.';$('#hourly-strip').innerHTML='';return;}
    const hours=(spot.hours||[]).filter(h=>Date.parse(h.time) >= Date.now()-3600000 && Date.parse(h.time)<=Date.now()+72*3600000).slice(0,72);
    if (hours.length<2) {$('#forecast-chart').textContent='Pronóstico no disponible en este momento.'; $('#hourly-strip').innerHTML='';return;}
    const w=705, top=19, bottom=167, left=36, right=688;
    const X=i=>left+(i/(hours.length-1))*(right-left);
    const Y=val=>bottom-(val/100)*(bottom-top);
    const poly=hours.map((h,i)=>`${X(i).toFixed(1)},${Y(h.scores?.[state.profile]||0).toFixed(1)}`).join(' ');
    const area=`${left},${bottom} ${poly} ${right},${bottom}`;
    const horizontal=[25,50,75,100].map(n=>`<line x1="${left}" y1="${Y(n)}" x2="${right}" y2="${Y(n)}" stroke="#36505a" stroke-dasharray="3 8" stroke-width=".7"/><text x="${left-10}" y="${Y(n)+3}" fill="#779aa0" text-anchor="end" font-size="10">${n}</text>`).join('');
    const ticks=[0,Math.floor((hours.length-1)*.33),Math.floor((hours.length-1)*.67),hours.length-1].map(i=>`<text x="${X(i)}" y="195" fill="#93aeb2" text-anchor="middle" font-size="10">${esc(dateTitle.format(dt(hours[i].time)))}</text>`).join('');
    const shadeStart=hours.findIndex(h=>h.scores?.[state.profile]>=alertThreshold() && h.is_day);
    const points=shadeStart>=0?`<circle cx="${X(shadeStart)}" cy="${Y(hours[shadeStart].scores[state.profile])}" r="5" fill="#80f9dc" stroke="#0c2832" stroke-width="3"/>`:'';
    $('#forecast-chart').classList.remove('loading-chart');
    $('#forecast-chart').innerHTML=`<svg viewBox="0 0 ${w} 204" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Puntuación de surf de ${esc(spot.name)} durante las próximas 72 horas, entre 0 y 100"><defs><linearGradient id="fillScore" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#58dcb8" stop-opacity=".29"/><stop offset="1" stop-color="#58dcb8" stop-opacity="0"/></linearGradient></defs>${horizontal}<line x1="${left}" x2="${right}" y1="${Y(alertThreshold())}" y2="${Y(alertThreshold())}" stroke="#77c7b4" stroke-dasharray="3 4" stroke-opacity=".6"/><polygon points="${area}" fill="url(#fillScore)"/><polyline points="${poly}" stroke="#7cf2d6" stroke-width="2.5" fill="none" stroke-linejoin="round" stroke-linecap="round"/>${points}${ticks}</svg><div class="chart-legend"><span class="legend-point"></span> ${esc(spot.name)} <span>·</span> <span>Línea discontinua: umbral de aviso (${alertThreshold()})</span><span>·</span><span>Noche = 0</span></div>`;
    const strip=hours.filter(h=>dateMatch(h.time,targetDate(state.day)) && h.is_day).slice(0,12);
    $('#hourly-strip').innerHTML=strip.map(h=>`<div class="hour-tile" title="${esc(fmt(h.wave_m,2))} m, período ${esc(fmt(h.period_s,0))} s"><span class="hour-time">${esc(clock(h.time))}</span><strong class="${scoreClass(h.scores?.[state.profile]||0)}">${h.scores?.[state.profile]??0}</strong><small>${fmt(h.wave_m,2)} m</small></div>`).join('') || '<p class="muted">No hay franjas con luz diurna disponibles para este día.</p>';
  }
  function spotProfile(id) { return state.profiles.find(p=>p.id===id) || null; }
  function profilesPanel() {
    const root=$('#spot-profile-list');
    if (!state.profiles.length) {root.innerHTML='<p class="muted">No se pudieron cargar las fichas individuales.</p>';return;}
    root.innerHTML=state.profiles.map(p=>{
      const confirmed=p.classification==='documentado';
      const source=p.sources?.[0];
      return `<details class="spot-fact-card" id="perfil-${esc(p.id)}"><summary><span class="profile-summary-left"><strong>${esc(p.name)}</strong><small>${esc(p.type)}</small></span><span class="profile-status ${confirmed?'profile-sourced':'profile-to-calibrate'}">${confirmed?'Guía publicada':'Por calibrar'}</span></summary><div class="profile-facts-body"><div class="profile-core"><div><small>SWELL FAVORABLE</small><b>${esc(p.swell_label)}</b></div><div><small>VIENTO FAVORABLE</small><b>${esc(p.wind_label)}</b></div><div><small>MAREA</small><b>${esc(p.tide_label)}</b></div><div><small>MEJOR ÉPOCA</small><b>${esc(p.season)}</b></div></div><div class="profile-conditions"><div><h4>✓ Cuando mejora</h4><ul>${p.best.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div><div><h4>× Cuando empeora</h4><ul>${p.worst.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div></div><p class="profile-risk"><strong>Atención:</strong> ${esc(p.hazards)}</p><p class="profile-uncertainty">${esc(p.confidence_note)}</p>${source?`<a href="${esc(source)}" target="_blank" rel="noopener noreferrer" class="profile-reference">Consultar referencia ↗</a>`:''}</div></details>`;
    }).join('');
  }
  function spotDiagnosis(spot,h) {
    const p=spotProfile(spot.id);
    if(!p || !h) return '';
    const level=p.classification==='documentado'?'Direcciones respaldadas por guía':'Orientaciones por comprobar';
    return `<div class="spot-diagnosis"><div class="diagnosis-header"><strong>Perfil de playa · ${esc(level)}</strong><a href="#perfil-${esc(p.id)}">Ver ficha completa ↗</a></div><div class="diagnosis-rows"><span>Swell: <b>${esc(h.swell_fit||'sin dato')}</b></span><span>Viento: <b>${esc(h.wind_fit||'sin dato')}</b></span></div><p><b>Ideal:</b> ${esc(p.swell_label)} · ${esc(p.wind_label)}. ${esc(p.tide_label)}.</p><p class="muted">${esc(p.confidence_note)}</p></div>`;
  }

  function observation(h) {
    if (!h) return 'Sin información meteorológica suficiente.';
    const lines=[];
    if ((h.wave_m||0)<.35) lines.push('Oleaje demasiado pequeño para una sesión consistente.');
    else if ((h.period_s||0)<5) lines.push('Período corto: probablemente mar de viento poco ordenado.');
    else if ((h.period_s||0)>=7) lines.push('Período razonable para el Mediterráneo; podría ordenar las series.');
    else lines.push('Período intermedio: calidad dependiente del banco y la dirección.');
    if ((h.wind_kn||0)>15) lines.push('Viento fuerte; vigilá las rachas y el mar cruzado.');
    else if ((h.wind_kn||0)<=5) lines.push('Viento flojo, con posibilidad de superficie limpia.');
    else lines.push(`Viento ${cardinal(h.wind_dir)} de ${fmt(h.wind_kn,0)} kn; evaluá si entra de tierra a mar.`);
    if ((h.wave_spread_m||0)>.45) lines.push('Los modelos de olas discrepan de forma significativa.');
    if (h.danger) lines.push('Precaución: se detectaron condiciones potencialmente peligrosas.');
    return lines.join(' ');
  }
  function detail(item) {
    if (!item) {$('#insight-content').innerHTML='<p class="muted">No hay datos disponibles.</p>';return;}
    const h=item.s.hour, score=item.s.score;
    if (!h) {$('#insight-content').innerHTML=`<div class="active-location"><h3>${esc(item.spot.name)}</h3></div><p class="muted">No hay datos diurnos para la fecha elegida.</p>`;return;}
    const modelRows=(h.models||[]).map(m=>`<div class="model-row"><span>${esc(m.name)}</span><b>${m.type==='olas' ? `${fmt(m.wave_m,2)} m · ${fmt(m.period_s,0)} s` : `${fmt(m.wind_kn,1)} kn · ${cardinal(m.wind_dir)}`}</b></div>`).join('');
    const displayTide=h.sea_level_m==null?'Sin dato modelado':`${fmt(h.sea_level_m,2)} m · ${esc(h.tide_trend||'sin tendencia')}`;
    $('#insight-content').innerHTML=`${h.danger?'<div class="warning-box">⚠️ Precaución: temporal, rachas fuertes o tormenta. No recomendar la entrada.</div>':''}<div class="active-location"><div><h3>${esc(item.spot.name)}</h3><p>Mejor ventana · ${esc(displayTime(item.s))}</p></div><div class="rating-text ${scoreClass(score)}">${score}/100</div></div><p class="insight-note">${esc(observation(h))}</p>${spotDiagnosis(item.spot,h)}<div class="detail-grid"><div class="detail-mini"><span>Temperatura aire / agua</span><strong>${fmt(h.temp_c,0)}° / ${fmt(h.sea_temp_c,0)}°</strong></div><div class="detail-mini"><span>Tiempo y lluvia</span><strong>${esc(weatherDesc(h.weather_code,h.rain_mm))}</strong></div><div class="detail-mini"><span>Mar de fondo / dirección</span><strong>${fmt(h.swell_m,2)} m · ${cardinal(h.swell_dir)}</strong></div><div class="detail-mini"><span>Nivel del mar / tendencia</span><strong>${displayTide}</strong></div><div class="detail-mini"><span>Ráfagas / dirección</span><strong>${fmt(h.gust_kn,0)} kn · ${cardinal(h.wind_dir)}</strong></div><div class="detail-mini"><span>Confianza de modelos</span><strong>${esc(h.confidence)} · ${h.marine_n} marinos</strong></div></div><div class="model-section"><h4>Comparación por modelo</h4>${modelRows||'<p class="muted">Comparativas no disponibles.</p>'}<p class="model-warning">La marea se muestra como nivel relativo modelado, no como pleamar/bajamar oficial. Los modelos pueden compartir una misma malla cerca de la costa; la puntuación no mide la calidad real del banco de arena.</p></div><p style="margin:17px 0 0"><a style="color:var(--aqua);font-weight:700" href="https://www.google.com/maps?q=${encodeURIComponent(item.spot.lat+','+item.spot.lon)}" target="_blank" rel="noopener noreferrer">Abrir ubicación del spot ↗</a></p>`;
  }
  function beaches(order) {
    $('#beach-list').innerHTML=order.map((item,i)=>`<button type="button" class="beach-row select-spot ${item.spot.id===state.selected?'active':''}" data-select="${esc(item.spot.id)}" aria-label="Seleccionar ${esc(item.spot.name)}"><span class="beach-rank">${pad(i+1)}</span><span class="beach-body"><strong>${esc(item.spot.name)}</strong><small>${esc(item.s.hour?displayTime(item.s):'Sin ventana')} · ${esc(spotSummary(item))}</small></span><span class="beach-score ${scoreClass(item.s.score)}">${item.s.score}</span><span class="beach-arrow" aria-hidden="true">›</span></button>`).join('');
  }
  function sources() {
    const data=state.snapshot;
    const names=[...new Set((data?.spots||[]).flatMap(s=>s.source_names||[]))];
    const tags=names.length ? names : ['Sin pronósticos automáticos todavía'];
    if (data?.sources?.windy_api && !tags.includes('Windy AROME')) tags.push('Windy API configurada (comprobar disponibilidad)');
    tags.push('Windguru · revisión manual','Surf-Forecast · revisión manual');
    $('#source-summary').innerHTML=tags.map(t=>`<span>${esc(t)}</span>`).join('');
  }
  function refresh() {
    if (!state.snapshot?.spots?.length) return;
    overview();
    const order=ranking();
    if (!state.selected || !state.snapshot.spots.find(s=>s.id===state.selected)) state.selected=order[0]?.spot?.id || null;
    const item=order.find(s=>s.spot.id===state.selected)||order[0];
    chart(item?.spot);detail(item);beaches(order);sources();
  }
  function setUpdated(snapshot) {
    const pill=$('#data-pill'), last=$('#last-update');
    if (snapshot.status==='pending' || !snapshot.generated_at) {
      pill.className='data-pill pending'; pill.innerHTML='<span class="pulse-dot"></span> Pendiente de primera carga';
      last.textContent='Sin actualización realizada';return;
    }
    const ageHours=(Date.now()-Date.parse(snapshot.generated_at))/3600000;
    const good=ageHours>=0 && ageHours<=8;
    pill.className='data-pill '+(good?'live':'stale');pill.innerHTML=`<span class="pulse-dot"></span> ${good?'Datos recientes':'Datos antiguos'}`;
    last.textContent=`Actualizado el ${exactDate.format(new Date(snapshot.generated_at))} (Barcelona)${snapshot.status==='partial'?' · Cobertura parcial':''}`;
    if (!good) pill.title='El parte tiene más de 8 horas. Confirmá en las fuentes antes de ir.';
  }
  function bind() {
    document.querySelectorAll('.day-tab').forEach(button => button.addEventListener('click', () => {
      state.day=Number(button.dataset.day);
      document.querySelectorAll('.day-tab').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-selected',String(b===button));});
      state.selected=null;
      refresh();
    }));
    $('#profile').value=state.profile;
    $('#profile').addEventListener('change',event=>{state.profile=event.target.value;try{localStorage.setItem('bcn-surf-profile',state.profile);}catch(_){}state.selected=null;refresh();});
    document.addEventListener('click',event=>{
      const element=event.target.closest('[data-select]');
      if (!element)return;
      const id=element.dataset.select;
      if (state.snapshot?.spots?.some(s=>s.id===id)){
        state.selected=id;refresh();
        if (element.classList.contains('beach-row')||element.classList.contains('mini-card'))$('#detalle').scrollIntoView({behavior:'smooth',block:'start'});
      }
    });
  }
  async function init() {
    loadPreferences();bind();
    try {
      const profilesResponse=await fetch('./data/spot_profiles.json',{cache:'no-store'});
      if (!profilesResponse.ok) throw new Error('Sin perfiles');
      const profileDoc=await profilesResponse.json();
      if (!Array.isArray(profileDoc.spots)) throw new Error('Perfiles inválidos');
      state.profiles=profileDoc.spots;
    } catch (_) { state.profiles=[]; }
    profilesPanel();
    try {
      const response=await fetch('./data/latest.json?ts='+Date.now(),{cache:'no-store'});
      if (!response.ok) throw new Error('No se pudo acceder al archivo de datos');
      const content=await response.json();
      if (!content||!Array.isArray(content.spots)) throw new Error('Archivo con formato no reconocido');
      state.snapshot=content;
      setUpdated(content);
      if (!content.spots.length) {
        $('#overview').innerHTML=`<div class="empty-state"><div class="empty-mark">〰</div><h2>Radar listo para recibir datos</h2><p>Falta ejecutar la primera actualización automática en GitHub Actions. La web no muestra pronósticos de ejemplo como si fueran reales.</p></div>`;
        $('#beach-list').innerHTML='<div class="beach-placeholder">Las 7 playas aparecerán tras la primera actualización.</div>';
        $('#forecast-chart').textContent='No hay pronósticos disponibles todavía.';
        sources();
      } else refresh();
    } catch(e) {
      $('#data-pill').className='data-pill stale';
      $('#data-pill').innerHTML='<span class="pulse-dot"></span> Sin conexión';
      $('#overview').innerHTML=`<div class="empty-state"><div class="empty-mark">〰</div><h2>No se pudo cargar el parte</h2><p>Revisá la conexión y volvé a intentar. No se mostrará un pronóstico inventado.</p></div>`;
      $('#last-update').textContent='Consulta fallida';
      $('#beach-list').innerHTML='<div class="beach-placeholder">No hay datos para mostrar.</div>';
      $('#forecast-chart').textContent='Sin datos.';
    }
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(()=>{});
  }
  init();
})();
