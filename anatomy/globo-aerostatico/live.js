
const D = __DATA__;
/*__LEVER__*/
const stage = document.querySelector(".gb-stage");
const balloonParts = [stage.querySelector('[data-part="balloon-back"]'), stage.querySelector('[data-part="balloon-front"]')];
const frontGroup = balloonParts[1];
const envEl = stage.querySelector('[data-part="env"]');
const wiresBackEl = stage.querySelector('[data-part="wires-back"]');
const carriageEl = stage.querySelector('[data-part="carriage"]');
const shadowEl = stage.querySelector('[data-part="shadow"]');
const basketHalo = stage.querySelector('[data-part="basket-halo"]');
const leverEl = stage.querySelector('[data-part="lever"]');
const bladesEl = stage.querySelector('[data-part="fan-blades"]');
const fallbackEl = stage.querySelector('[data-part="fallback"]');
const readout = document.querySelector("[data-readout]");
const buttons = [...document.querySelectorAll(".gb-btn")];
const still = matchMedia("(prefers-reduced-motion: reduce)");
const lightNow = () => ((stage.closest("[data-theme]")?.getAttribute("data-theme") ?? "light") !== "dark" ? 1 : 0);
let LIGHT = lightNow();
const TIME_SCALE = 8;
const liftOf = (alt) => D.liftMax * (1 - Math.exp(-alt / D.liftK));
const kit = { iso, lineSvg, solidSvg, dotsSvg, fadedSvg, segment };
const ENV = makeEnvelope(kit, G, D.P, D.C);

const FRAGMENT = `
uniform float uFlame;
uniform float uPilot;
uniform vec3 uBase;
uniform vec3 uDir;
uniform float uReach;
uniform float uLight;
uniform float uVent;
uniform vec3 uCrown;
uniform vec3 uAxis;
uniform float uCrownR;
const float NOZZLE=${D.nozzle.toFixed(2)};
const vec3 PILOT=vec3(${D.pilot.map((v) => v.toFixed(2)).join(",")});
const vec3 BODY=vec3(1.,.50,.10);
const vec3 YELLOW=vec3(1.,.80,.28);
const vec3 CORE=vec3(1.,.96,.84);
vec4 inkFor(vec3 seen,float cover){vec3 absorbed=1.-seen;float a=max(max(absorbed.r,max(absorbed.g,absorbed.b)),cover);return vec4(vec3(a)-absorbed,a);}
vec4 over(vec4 top,vec4 under){return top+under*(1.-top.a);}
void main(){
  vec2 vb=viewOf(gl_FragCoord.xy);
  vec4 ink=vec4(0.);
  vec3 glow=vec3(0.);
  if(uFlame>.002){
    // Distancia del rayo de este píxel al eje de la llama (dos rectas que se cruzan).
    vec3 V=towardViewer();
    vec3 N=uBase+vec3(0.,0.,NOZZLE);
    vec3 w=rayOf(vb)-N;
    float b=dot(uDir,V),d=dot(uDir,w),e=dot(V,w);
    float den=max(1.-b*b,1e-3);
    float zl=(d-b*e)/den;
    float t=(b*d-e)/den;
    vec3 gap=w+t*V-zl*uDir;
    float side=dot(gap,normalize(cross(uDir,V)));
    float len=min(30.*(.3+.7*uFlame),uReach);
    float x=zl/len;
    float tt=uTime;
    float sway=sin(zl*.21-tt*7.3)*1.1+sin(zl*.47-tt*11.7)*.45;
    float u=side-sway*smoothstep(0.,.9,x);
    float rf=1.5+4.4*sin(3.14159*pow(clamp(x,0.,1.),.62))*(1.-.4*clamp(x,0.,1.));
    float rag=fbm2(vec2(u*.32,zl*.11-tt*3.4));
    float along=smoothstep(-.03,.06,x)*(1.-smoothstep(.45,1.05+.25*rag,x));
    float body=exp(-pow(u/(rf*(.85+.35*rag)),2.))*along;
    float core=exp(-pow(u/(rf*.42),2.))*(1.-smoothstep(.05,.55,x))*smoothstep(-.02,.04,x);
    float en=body*uFlame*(.75+.5*rag)*mix(1.,1.3-.6*smoothstep(0.,rf,abs(u)),uLight);
    float m=1.-exp(-2.6*en);
    float c=core*uFlame;
    vec3 seen=mix(vec3(1.),BODY,smoothstep(.04,.5,m));
    seen=mix(seen,YELLOW,smoothstep(.5,.85,m)*.8);
    seen=mix(seen,CORE,smoothstep(.2,.8,c));
    float cover=.9*smoothstep(.45,.9,max(m,c));
    ink=inkFor(seen,cover)*smoothstep(0.,.08,m+c);
    glow=BODY*m*2.2+YELLOW*m*m*1.2+CORE*c*1.4;
  }
  if(uVent>.002){
    // Chorro de aire caliente que sale por la corona: sube por el eje y se abre al mezclarse.
    vec3 V=towardViewer();
    vec3 w=rayOf(vb)-uCrown;
    float b=dot(uAxis,V),d=dot(uAxis,w),e=dot(V,w);
    float den=max(1.-b*b,1e-3);
    float h=(d-b*e)/den;
    float t=(b*d-e)/den;
    vec3 gap=w+t*V-h*uAxis;
    float side=dot(gap,normalize(cross(uAxis,V)));
    float tt=uTime;
    float wid=uCrownR*.85+.32*max(h,0.);
    float rag=fbm2(vec2(side*.09,h*.06-tt*2.6*(.4+uVent)));
    float rag2=fbm2(vec2(side*.21+3.1,h*.15-tt*4.1));
    float u=side+sin(h*.05-tt*1.7)*3.*smoothstep(10.,60.,h);
    float col=exp(-pow(u/(wid*(.8+.4*rag)),2.));
    float run=smoothstep(-2.,6.,h)*exp(-max(h,0.)/(28.+70.*uVent));
    // Sale por el hueco anular entre el paracaídas y la tela: más denso junto al borde.
    float ring=exp(-pow((abs(u)-uCrownR*(1.+.012*max(h,0.)))/(4.+.25*max(h,0.)),2.))*exp(-max(h,0.)/14.);
    float dens=(col+1.4*ring)*run*uVent*(.45+.9*rag*rag2)*smoothstep(0.,uCanvas.y*.14,uCanvas.y-gl_FragCoord.y);
    float m=1.-exp(-3.2*dens);
    vec3 seen=mix(vec3(1.),vec3(.93,.80,.67),smoothstep(.03,.6,m));
    vec4 haze=inkFor(seen,.0)*smoothstep(0.,.05,m)*.85;
    ink=over(ink,haze);
    glow+=vec3(1.,.55,.25)*m*.45;
  }
  vec2 pp=project(PILOT+uBase);
  vec2 dp=(vb-pp)/uK;
  float pe=exp(-(dp.x*dp.x)/.35-max(-dp.y,0.)*max(-dp.y,0.)/2.4-max(dp.y,0.)*max(dp.y,0.)/.25)*uPilot*(.85+.15*sin(uTime*23.));
  vec3 pilotSeen=mix(vec3(1.),vec3(.32,.52,1.),smoothstep(.02,.6,pe));
  pilotSeen=mix(pilotSeen,vec3(.92,.96,1.),smoothstep(.75,1.,pe));
  vec4 pilotInk=inkFor(pilotSeen,.6*smoothstep(.6,1.,pe))*smoothstep(0.,.05,pe);
  vec4 lightOut=over(ink,pilotInk);
  vec3 col=tonemap(glow+vec3(.35,.55,1.)*pe*1.2,1.15);
  float a=max(col.r,max(col.g,col.b));
  vec4 o=mix(vec4(col,a),lightOut,uLight);
  float n=(hash12(gl_FragCoord.xy+fract(uTime*.61)*91.)+hash12(gl_FragCoord.yx*1.37+fract(uTime*.37)*57.)-1.)/255.;
  o=max(o+n*smoothstep(0.,1.5/255.,o.a),0.);
  o.rgb=min(o.rgb,vec3(o.a));
  gl_FragColor=o;
}`;

const canvas = stage.querySelector(".gb-gl");
const layer = glLayer({ canvas, fragment: FRAGMENT, view: [D.W, D.H], camera: D.camera, uniforms: ["uFlame", "uPilot", "uBase", "uDir", "uReach", "uLight", "uVent", "uCrown", "uAxis", "uCrownR"] });
if (layer) stage.setAttribute("data-gl", "");
const blend = () => { LIGHT = lightNow(); canvas.style.mixBlendMode = LIGHT ? "normal" : "screen"; };
blend();
new MutationObserver(blend).observe(stage.closest("[data-theme]") ?? document.body, { attributes: true, attributeFilter: ["data-theme"] });

// Estado: el modelo de vuelo más el inflado de la envoltura.
const sim = initial();
sim.t = ambientT(0);
const inf = { fill: D.start.fill, stand: { x: 0, v: 0 } };
const flame = { x: 0, v: 0 };
const jet = { x: 0, v: 0 };
let coolRate = 0;
const ventPos = { x: 0, v: 0 };
const valve = { x: 0, v: 0 };
const fanSpin = { x: 0, v: 0 };
const input = { burn: false, vent: false, fan: false };
let touring = !still.matches, idle = 0, clock = 0, last = 0, frame = 0, visible = false, bladeAngle = 0;
let shown = null, lastBuild = 0, pose = null;
const auto = { phase: "cold", burn: 0, vent: 0, fan: 0, hold: 0, clock: 0 };

const upright = () => inf.stand.x > 0.985;
const airborne = () => sim.z > 0.01;
const canBurn = () => inf.fill >= 0.7 || inf.stand.x > 0.3 || airborne();

// Piloto automático: inflar en frío, levantar con el quemador, volar, aterrizar y recoger.
const PLAN = [[300, 95], [120, 60], [0, 70]];
const PLAN_T = PLAN.reduce((a, [, d]) => a + d, 0);
function targetAt(t) {
  let acc = 0;
  for (const [alt, d] of PLAN) { if (t < acc + d) return alt; acc += d; }
  return 0;
}
function autopilot(dt) {
  auto.clock += dt;
  auto.fan = 0; auto.vent = 0;
  if (auto.phase === "cold") {
    auto.fan = 1; auto.burn = 0;
    if (inf.fill >= COLD_FILL - 0.005) { auto.phase = "hot"; auto.clock = 0; }
    return;
  }
  if (auto.phase === "hot") {
    auto.fan = inf.stand.x < 0.5 ? 1 : 0;
    if (auto.hold <= 0) { auto.burn = auto.burn ? 0 : 1; auto.hold = auto.burn ? 3 : 1.5; }
    auto.hold -= dt;
    if (upright() && sim.t > equilibriumT(0) - 3) { auto.phase = "fly"; auto.clock = 0; auto.hold = 0; }
    return;
  }
  if (auto.phase === "fly") {
    const target = targetAt(auto.clock);
    const want = Math.max(-2.2, Math.min(2.4, (target - sim.z) / 45));
    const needT = equilibriumT(sim.z) + 9 * (want - sim.v) + 2.5 * want;
    auto.hold -= dt;
    if (auto.hold <= 0) {
      const burnNow = sim.t < needT - 0.4 && sim.t < T_MAX - 6 && !(target === 0 && sim.z < 2);
      if (burnNow !== !!auto.burn) { auto.burn = burnNow ? 1 : 0; auto.hold = burnNow ? 2.5 : 1.5; }
    }
    auto.vent = target < sim.z - 20 && sim.v > want + 0.6 && sim.z > 15 ? 1 : 0;
    if (auto.clock > PLAN_T && !airborne()) { auto.phase = "pack"; auto.clock = 0; auto.burn = 0; }
    return;
  }
  if (auto.phase === "pack") {
    auto.burn = 0; auto.vent = 1;
    if (inf.fill <= 0.13 && inf.stand.x < 0.01) { auto.phase = "rest"; auto.clock = 0; }
    return;
  }
  if (auto.phase === "rest") {
    auto.burn = 0;
    if (auto.clock > 25) { auto.phase = "cold"; auto.clock = 0; }
  }
}

function inflate(dt, fanOn, ventOn) {
  const vol = inf.fill * inf.fill;
  const lying = inf.stand.x < 0.05 && !airborne();
  if (fanOn && inf.stand.x < 0.6 && !airborne()) {
    const cap = COLD_FILL * COLD_FILL;
    if (vol < cap) inf.fill = Math.sqrt(Math.min(cap, vol + (FAN_Q / V) * dt));
    // El aire del ventilador está a temperatura ambiente: renueva el de dentro.
    sim.t += (ambientT(0) - sim.t) * Math.min(1, (FAN_Q / (Math.max(vol, 0.02) * V)) * dt) * (1 - inf.stand.x);
  }
  if (ventOn && lying) inf.fill = Math.sqrt(Math.max(0.12 * 0.12, vol - (SQUEEZE_Q / V) * dt));
  // Se levanta cuando el aire caliente sostiene el peso de la tela.
  const dT = sim.t - ambientT(sim.z), need = standT(sim.z) - ambientT(sim.z);
  const r = Math.max(0, Math.min(1, (dT / need - 0.3) / 0.7));
  const target = airborne() ? 1 : inf.fill >= 0.7 ? r * r * (3 - 2 * r) : 0;
  return target;
}

const fmt = (v, d = 0) => v.toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });
function rebuild(now, force) {
  const key = [inf.fill.toFixed(3), inf.stand.x.toFixed(3)].join();
  if (!force && (key === shown || now - lastBuild < 45)) return;
  shown = key; lastBuild = now;
  pose = ENV.poseOf({ fill: inf.fill + (1 - COLD_FILL) * inf.stand.x * (inf.fill >= COLD_FILL - 0.01 ? 1 : 0), stand: inf.stand.x, upright: D.upright });
  const out = ENV.pose(pose);
  envEl.innerHTML = out.front;
  wiresBackEl.innerHTML = out.back;
}
function crownOf(lift) {
  const m = pose ? pose.mouth : D.upright;
  const ax = pose ? ENV.frameFor(pose.theta, pose.mouth).a : [0, 0, 1];
  const s = D.crownS + 1;
  return { uVent: upright() ? jet.x : 0, uCrown: [D.B[0] + m[0] + ax[0] * s, D.B[1] + m[1] + ax[1] * s, lift + m[2] + ax[2] * s], uAxis: ax, uCrownR: D.C.R_CROWN };
}
function draw(now) {
  rebuild(now, false);
  const lift = liftOf(sim.z);
  const tr = translateAlong(D.P, [D.B[0], D.B[1], lift]);
  for (const g of balloonParts) g.setAttribute("transform", tr);
  carriageEl.setAttribute("transform", translateAlong(D.P, [0, 0, D.floorZ + lift]));
  shadowEl.style.opacity = String(0.4 * Math.exp(-lift / 30) * inf.stand.x);
  basketHalo.style.opacity = String(Math.exp(-lift / 1.5));
  const vent = frontGroup.querySelector('[data-part="vent"]');
  if (vent && pose) {
    const a = ENV.frameFor(pose.theta, pose.mouth).a;
    vent.setAttribute("transform", translateAlong(D.P, a.map((c) => -c * D.ventDrop * ventPos.x)));
  }
  leverEl.setAttribute("d", leverAt(valve.x));
  if (fanSpin.x > 0.002) {
    bladeAngle += fanSpin.x * 0.35;
    bladesEl.setAttribute("d", G.spokesOf(D.fanF, 0, 2.4, 10.2, 5, D.P, { phase: 0.2 + bladeAngle, sweep: 0.5 }));
  }
  const a = stateAt(sim);
  frontGroup.style.setProperty("--heat", Math.max(0, Math.min(1, (sim.t - a.ta) / 105)).toFixed(3));
  if (fallbackEl) fallbackEl.style.opacity = String(0.8 * flame.x * (upright() ? 1 : 0));
  const T = fmt(sim.t - 273.15);
  let text;
  if (!upright() && !airborne()) {
    const pct = fmt(Math.min(100, (inf.fill + (1 - COLD_FILL) * inf.stand.x) ** 2 * 100));
    if (inf.stand.x > 0.02) text = `levantándose · ${T} °C · ${fmt(inf.stand.x * 90)}°`;
    else if (input.burn && !canBurn()) text = "infla antes con el ventilador";
    else if (fanSpin.x > 0.05) text = `inflado en frío · ${pct} % · ${T} °C`;
    else text = `tendido · ${pct} % lleno · ${T} °C`;
  } else {
    const dir = sim.v > 0.05 ? "↑" : sim.v < -0.05 ? "↓" : "";
    if (ventPos.x > 0.3 && coolRate > 0.05) text = `válvula · ${T} °C (−${fmt(coolRate, 1)} °C/s) · ${dir ? dir + fmt(Math.abs(sim.v), 1) + " m/s · " : ""}${fmt(sim.z)} m`;
    else text = `${T} °C · ${a.net >= 0 ? "+" : "−"}${fmt(Math.abs(a.net))} N · ${dir ? dir + fmt(Math.abs(sim.v), 1) + " m/s · " : ""}${fmt(sim.z)} m`;
  }
  if (readout.textContent !== text) readout.textContent = text;
  stage.setAttribute("aria-valuetext", text);
}

function tick(now) {
  const dt = last ? Math.min((now - last) / 1000, 1 / 20) : 1 / 60;
  last = now;
  clock += dt;
  const calm = still.matches;
  idle += dt;
  if (!touring && idle > 6 && !input.burn && !input.vent && !input.fan && !calm) touring = true;
  const simDt = dt * TIME_SCALE;
  if (touring) autopilot(simDt);
  const fanOn = touring ? auto.fan : input.fan ? 1 : 0;
  const wantBurn = touring ? auto.burn : input.burn ? 1 : 0;
  const burnOn = wantBurn && canBurn() ? 1 : 0;
  const ventOn = touring ? auto.vent : input.vent ? 1 : 0;
  settle(valve, burnOn, dt, 0.05, calm);
  const ventWant = ventOn && inf.stand.x > 0.05 ? 1 : 0;
  settle(ventPos, ventWant, dt, ventWant > ventPos.x ? 0.07 : 0.2, calm);
  settle(flame, burnOn, dt, burnOn > flame.x ? 0.07 : 0.16, calm);
  settle(fanSpin, fanOn, dt, 0.6, calm);
  const n = Math.max(1, Math.ceil(simDt / 0.05));
  const t0 = sim.t;
  for (let i = 0; i < n; i++) {
    const h = simDt / n;
    step(sim, valve.x, ventPos.x, h);
    if (!upright()) { sim.z = 0; sim.v = 0; }
    const target = inflate(h, fanOn, ventOn);
    settle(inf.stand, target, h / TIME_SCALE, 1.1, calm);
  }
  if (dt > 0) coolRate += ((t0 - sim.t) / dt - coolRate) * Math.min(1, dt * 4);
  settle(jet, Math.min(1, sim.mdotVent / 14), dt, sim.mdotVent / 14 > jet.x ? 0.04 : 0.25, calm);
  draw(now);
  if (layer) {
    const nozzle = [0, 0, D.nozzle];
    const m = pose ? pose.mouth : D.upright;
    const to = [m[0] - nozzle[0], m[1] - nozzle[1], m[2] - nozzle[2]];
    const reach = Math.hypot(...to);
    layer.draw({ uFlame: flame.x, uPilot: 1, uBase: [D.B[0], D.B[1], liftOf(sim.z)], uDir: to.map((c) => c / reach), uReach: reach + 6, uLight: LIGHT, ...crownOf(liftOf(sim.z)) }, calm ? 0.8 : clock);
  }
  frame = visible ? requestAnimationFrame(tick) : 0;
}
const run = () => { if (!frame && visible) { last = 0; frame = requestAnimationFrame(tick); } };
new IntersectionObserver((entries) => { visible = entries[entries.length - 1].isIntersecting; if (visible) run(); }, { rootMargin: "120px 0px" }).observe(stage);

const take = () => { if (touring) { touring = false; auto.burn = 0; auto.vent = 0; auto.fan = 0; } idle = 0; };
const set = (what, on) => {
  take();
  input[what] = on;
  for (const b of buttons) b.toggleAttribute("data-on", !!input[b.dataset.hold]);
  run();
};
stage.addEventListener("pointerdown", (e) => { stage.setPointerCapture?.(e.pointerId); set("burn", true); });
for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) stage.addEventListener(type, () => set("burn", false));
for (const b of buttons) {
  b.addEventListener("pointerdown", (e) => { e.preventDefault(); b.setPointerCapture?.(e.pointerId); set(b.dataset.hold, true); });
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) b.addEventListener(type, () => set(b.dataset.hold, false));
  b.addEventListener("keydown", (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); set(b.dataset.hold, true); } });
  b.addEventListener("keyup", (e) => { if (e.key === " " || e.key === "Enter") set(b.dataset.hold, false); });
}
const keyOf = (e) => (e.key === " " || e.key === "ArrowUp" ? "burn" : e.key === "ArrowDown" || e.key === "v" || e.key === "V" ? "vent" : e.key === "f" || e.key === "F" ? "fan" : null);
stage.addEventListener("keydown", (e) => { const what = keyOf(e); if (!what) return; e.preventDefault(); if (!input[what]) set(what, true); });
stage.addEventListener("keyup", (e) => { const what = keyOf(e); if (what) set(what, false); });
rebuild(performance.now(), true);
draw(performance.now());
