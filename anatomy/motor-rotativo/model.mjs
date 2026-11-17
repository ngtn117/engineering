// Modelo de un motor rotativo (Wankel) genérico de un rotor.
// Unidades del dibujo: 1 = 1,5 mm. R = radio generador, E = excentricidad, B = ancho del rotor.
export const MM = 1.5;
export const R = 70;   // 105 mm
export const E = 10;   // 15 mm
export const B = 40;   // 60 mm
export const SAG_K = 0.82; // el flanco del rotor queda al 82 % de la envolvente máxima

const TAU = Math.PI * 2;
export const housing = (a) => [E * Math.cos(3 * a) + R * Math.cos(a), E * Math.sin(3 * a) + R * Math.sin(a)];
export const centre = (phi) => [E * Math.cos(phi), E * Math.sin(phi)];
export const rotorTurn = (phi) => phi / 3;

const HN = 720;
export const housingRing = (n = HN) => Array.from({ length: n }, (_, i) => housing((i / n) * TAU));

function inside([px, py], poly) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}
const toWorld = ([u, v], phi) => {
  const t = phi / 3, [cx, cy] = centre(phi);
  return [cx + u * Math.cos(t) - v * Math.sin(t), cy + u * Math.sin(t) + v * Math.cos(t)];
};
// Sagita máxima del flanco (envolvente interior) a lo largo del eje de la cara, a 60°.
function envelopeSag() {
  const H = housingRing();
  const dir = [Math.cos(Math.PI / 3), Math.sin(Math.PI / 3)];
  const ok = (s) => {
    const r = R / 2 + s;
    for (let i = 0; i < 1440; i++) if (!inside(toWorld([dir[0] * r, dir[1] * r], (i / 1440) * TAU * 3), H)) return false;
    return true;
  };
  let lo = 0, hi = R;
  for (let k = 0; k < 30; k++) { const m = (lo + hi) / 2; if (ok(m)) lo = m; else hi = m; }
  return lo;
}
export const ENV_SAG = 15.0; // medido con envelopeSag(); se comprueba en check()
export const SAG = ENV_SAG * SAG_K;

// Flanco: arco de circunferencia entre dos vértices, en el marco del rotor.
const CH = R * Math.sqrt(3);
const RHO = (CH * CH / 4 + SAG * SAG) / (2 * SAG);
const OFF = R / 2 + SAG - RHO;
export function flank(k, n = 40) {
  const mid = (TAU * k) / 3 + Math.PI / 3;
  const ox = OFF * Math.cos(mid), oy = OFF * Math.sin(mid);
  const half = Math.asin(CH / 2 / RHO);
  const out = [];
  for (let i = 0; i <= n; i++) {
    const a = mid - half + (2 * half * i) / n;
    out.push([ox + RHO * Math.cos(a), oy + RHO * Math.sin(a)]);
  }
  return out;
}
export const rotorLocal = (n = 40) => [0, 1, 2].flatMap((k) => flank(k, n).slice(0, -1));
export const rotorWorld = (phi, n = 40) => rotorLocal(n).map((p) => toWorld(p, phi));
export const apexWorld = (phi, k) => toWorld([R * Math.cos((TAU * k) / 3), R * Math.sin((TAU * k) / 3)], phi);

// Cámara de la cara k: flanco del vértice k al k+1 y vuelta por la carcasa.
export function chamber(phi, k, n = 40) {
  const f = flank(k, n).map((p) => toWorld(p, phi));
  const a0 = phi / 3 + (TAU * k) / 3;
  const h = [];
  for (let i = n; i >= 0; i--) h.push(housing(a0 + ((TAU / 3) * i) / n));
  return [...f, ...h.slice(1, -1)];
}
const area = (p) => Math.abs(p.reduce((s, [x, y], i) => { const [u, v] = p[(i + 1) % p.length]; return s + x * v - u * y; }, 0)) / 2;
export const volumeCc = (phi, k) => (area(chamber(phi, k, 120)) * MM * MM * B * MM) / 1000;

// Dirección de la cara (ψ) y fase. Giro antihorario; bujías en +y, lumbreras en −y.
export const faceAngle = (phi, k) => phi / 3 + (TAU * k) / 3 + Math.PI / 3;
export const PHASES = ["admisión", "compresión", "expansión", "escape"];
export function phaseOf(phi, k) {
  const psi = (((faceAngle(phi, k) + Math.PI / 2) % TAU) + TAU) % TAU; // 0 en la cintura de las lumbreras
  return Math.min(3, Math.floor(psi / (Math.PI / 2)));
}

export function check() {
  const env = envelopeSag();
  const H = housingRing();
  let bad = 0;
  for (let i = 0; i < 720; i++) for (const p of rotorWorld((i / 720) * TAU * 3, 30)) if (!inside(p, H)) bad++;
  let vmin = Infinity, vmax = 0;
  for (let i = 0; i < 1080; i++) { const v = volumeCc((i / 1080) * TAU * 3, 0); vmin = Math.min(vmin, v); vmax = Math.max(vmax, v); }
  return { env, bad, vmin, vmax, disp: vmax - vmin, cr: vmax / vmin, formula: 3 * Math.sqrt(3) * R * E * B * MM ** 3 / 1000 };
}
