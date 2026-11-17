import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "./skill/kit/iso-kit.mjs";
import * as G from "./skill/kit/lathe.mjs";
import { kitScript } from "./skill/scripts/inline-kit.mjs";
import * as M from "./model.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = process.argv.find((a) => a.startsWith("--out="))?.slice(6) ?? HERE;
const theme = process.argv.includes("--dark") ? "dark" : "light";
const TAU = Math.PI * 2;

// Unidades: 1 = 1,5 mm (las mismas del modelo).
const W = 620;
const H = 500;
const PLATE = { x: -134, y: -136, w: 268, d: 268, r: 10 };
const PLATE_H = 10;
const FOOT_H = 5;
const STAND_Z = 0;
const REAR_Z = 8;          // tapa trasera (carcasa lateral)
const Z0 = 22;             // suelo de la cámara
const Z1 = Z0 + M.B;       // cara superior de la carcasa trocoidal
const ZR = Z1 - 2;         // cara del rotor
const HOUSE = { x: -106, y: -92, w: 212, d: 184, r: 20 };
const REAR = k.insetPlan(HOUSE, -4);
const PORT_Z = Z0 + M.B / 2;
const INTAKE_X = 22;
const EXHAUST_X = -24;
const PIPE_Y = HOUSE.y - 18;
const PLUG_A = [Math.PI / 2 - 0.2, Math.PI / 2 + 0.2]; // bujía delantera y trasera
const HUB_TOP = Z1 + 11;

const P = k.fitProjection(
  [...k.boxCorners(PLATE, -PLATE_H - FOOT_H, 0), [INTAKE_X, PIPE_Y, Z1 + 60], [EXHAUST_X, PIPE_Y, Z1 + 50], [0, HOUSE.y + HOUSE.d + 26, PORT_Z]],
  W,
  H,
  { pad: 26, azimuth: 45, elevation: 38 },
);
const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (points, style) => k.dotsSvg(points, style);
const poly = (pts, z, close = true) => {
  const s = pts.map((p) => at([p[0], p[1], z]));
  return "M" + s.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join("L") + (close ? "Z" : "");
};
const byDepth = (items, key) => [...items].sort((a, b) => k.depthOf(key(a), P) - k.depthOf(key(b), P));

// Curva desplazada de la carcasa (normal hacia fuera), para juntas, tornillos y canales de agua.
const housingNormal = (a) => {
  const h = 1e-4;
  const [x0, y0] = M.housing(a - h), [x1, y1] = M.housing(a + h);
  const tx = x1 - x0, ty = y1 - y0, l = Math.hypot(tx, ty);
  return [ty / l, -tx / l];
};
const offsetAt = (a, d) => { const [x, y] = M.housing(a); const [nx, ny] = housingNormal(a); return [x + nx * d, y + ny * d]; };
const TROCH = M.housingRing(240);
const TROCH_OPEN = poly(TROCH, Z1);

// ---------- base ----------
function plate() {
  const out = [`<path class="iso-halo" d="${k.haloOf(PLATE, -PLATE_H - FOOT_H, PLATE_H, P)}"/>`];
  for (const [x, y] of byDepth(k.corners(PLATE, 22), ([x, y]) => [x, y, 0])) {
    out.push(S(k.cylinder(x, y, 7, -PLATE_H - FOOT_H, 1.6, P, 28), { tone: "lo" }));
    out.push(S(k.cylinder(x, y, 5.4, -PLATE_H - FOOT_H + 1.6, FOOT_H - 1.6, P, 28), { tone: "mid" }));
  }
  out.push(S(k.slabOf(PLATE, -PLATE_H, PLATE_H, P, 8, 1.6), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(PLATE, 5), 0, P), { tone: "lo" }));
  const screws = k.corners(PLATE, 10);
  out.push(L(screws.map(([x, y]) => k.ring(x, y, 2.2, 0, P, 16)).join(""), { tone: "lo" }));
  out.push(D(screws.map(([x, y]) => at([x, y, 0])), { size: 0.5 }));
  // regla a lo largo del borde delantero (x)
  const strip = { x: PLATE.x + 20, y: PLATE.y + PLATE.d - 16, w: 120, d: 7, r: 1 };
  out.push(S(k.slabOf(strip, 0, 0.6, P, 3), { tone: "lo", crease: "none" }));
  const ticks = k.topTicks(strip.x + 4, strip.x + strip.w - 4, 4, 5, strip.y + 0.8, 0.6, [2, 3.6], P);
  out.push(L(ticks.minor, { tone: "lo" }), L(ticks.major, { tone: "mid" }));
  out.push(D([at([strip.x + 2, strip.y + 3.5, 0.6]), at([strip.x + strip.w - 2, strip.y + 3.5, 0.6])], { size: 0.45 }));
  // placa de características
  const tag = { x: PLATE.x + PLATE.w - 18, y: PLATE.y + 40, w: 8, d: 60, r: 1 };
  out.push(S(k.slabOf(tag, 0, 0.8, P, 3, 0.3), { tone: "hi", crease: "none" }));
  for (let i = 0; i < 3; i++) out.push(L(k.lineOnTop([tag.x + 2 + i * 2, tag.y + 8], [tag.x + 2 + i * 2, tag.y + (i === 2 ? 34 : 52)], 0.8, P), { tone: "lo", free: true }));
  out.push(D([at([tag.x + 4, tag.y + 3, 0.8]), at([tag.x + 4, tag.y + tag.d - 3, 0.8])], { size: 0.4 }));
  return out.join("");
}

// ---------- lumbreras y tubos de la parte trasera (−y) ----------
function farPipes() {
  const out = [];
  const pipe = (x, r, top, kind) => {
    const parts = [];
    const Fh = G.frameAlong([x, HOUSE.y, PORT_Z], [0, -1, 0]);
    parts.push(S(G.disc(0, 3, r + 5, Fh, P), { tone: "mid" }));
    parts.push(S(G.disc(3, 16, r, Fh, P), { tone: "mid", crease: "none" }));
    parts.push(S(G.sphereOf([x, PIPE_Y, PORT_Z], r + 1.2, P), { tone: "mid" }));
    parts.push(S(k.cylinder(x, PIPE_Y, r, PORT_Z, top - PORT_Z, P, 40), { tone: "mid", crease: "none" }));
    if (kind === "intake") {
      // cuerpo de mariposa y trompeta
      const tz = PORT_Z + 34;
      parts.push(S(k.cylinder(x, PIPE_Y, r + 2.5, tz, 10, P, 40, 0.4), { tone: "mid" }));
      parts.push(S(k.slabOf({ x: x + r + 1.5, y: PIPE_Y - 2, w: 6, d: 4, r: 1 }, tz + 3, 4, P, 2), { tone: "mid", crease: "none" }));
      parts.push(D([at([x + r + 6, PIPE_Y, tz + 7])], { size: 0.5 }));
      const F = G.frameAlong([x, PIPE_Y, top], [0, 0, 1]);
      const bell = [];
      for (let i = 0; i <= 10; i++) { const s = (i / 10) * 14; bell.push([s, r + 6.5 * (s / 14) ** 2, 1]); }
      bell[0] = [0, r]; bell[10] = [14, r + 6.5];
      parts.push(S(G.lathe(bell, F, P, { hole: [14, r + 4.6] }), { tone: "mid" }));
      parts.push(L(G.arcOf(F, 14, r + 5.5, P, { least: -1 }), { tone: "lo" }));
    } else {
      // cubierta térmica con abrazaderas
      for (const z of [PORT_Z + 20, PORT_Z + 46]) {
        parts.push(S(k.cylinder(x, PIPE_Y, r + 1.4, z, 4, P, 40), { tone: "mid" }));
        parts.push(D([at([x + (r + 1.4) * Math.SQRT1_2, PIPE_Y + (r + 1.4) * Math.SQRT1_2, z + 2])], { size: 0.45 }));
      }
      parts.push(S(k.cylinder(x, PIPE_Y, r + 1.8, top, 3, P, 40, 0.4), { tone: "mid" }));
      parts.push(`<path class="mr-deep" d="${poly(k.circleRing(x, PIPE_Y, r - 0.6, 40), top + 3)}"/>`);
    }
    return parts.join("");
  };
  out.push(pipe(EXHAUST_X, 8, Z1 + 44, "exhaust"));
  out.push(pipe(INTAKE_X, 7, Z1 + 44, "intake"));
  return out.join("");
}

// ---------- bloque del motor ----------
function engineBlock() {
  const out = [];
  // patas del soporte
  for (const [x, y] of byDepth(k.corners(REAR, 16), ([x, y]) => [x, y, 0])) {
    out.push(S(k.slabOf({ x: x - 9, y: y - 9, w: 18, d: 18, r: 2 }, STAND_Z, REAR_Z - STAND_Z, P, 3, 0.4), { tone: "lo" }));
  }
  out.push(`<path class="iso-halo" d="${k.haloOf(REAR, REAR_Z, 0.1, P)}" style="filter:blur(4px)"/>`);
  // tapa trasera
  out.push(S(k.slabOf(REAR, REAR_Z, Z0 - REAR_Z, P, 8, 0.6), { tone: "mid", inner: L(k.sideSeam(REAR, REAR_Z + 4, P, 8), { tone: "faint" }) }));
  // carcasa del rotor (trocoide)
  out.push(S(k.slabOf(HOUSE, Z0, M.B, P, 8, 1.2), { tone: "mid", inner: L(k.sideSeam(HOUSE, Z1 - 4, P, 8), { tone: "faint" }) + L(k.sideSeam(HOUSE, Z0 + 4, P, 8), { tone: "faint" }) }));
  // junta de agua alrededor de la trocoide
  out.push(L(poly(Array.from({ length: 240 }, (_, i) => offsetAt((i / 240) * TAU, 5)), Z1), { tone: "faint" }));
  // canales de agua (ranuras cerradas) y tornillos pasantes
  const bolts = [], slots = [];
  for (let i = 0; i < 16; i++) {
    const a = (i / 16) * TAU + TAU / 32;
    bolts.push(offsetAt(a, 17));
    const a0 = a + TAU / 32 - 0.07, a1 = a + TAU / 32 + 0.07;
    const side = [];
    for (let j = 0; j <= 6; j++) side.push(offsetAt(a0 + ((a1 - a0) * j) / 6, 9.5));
    for (let j = 6; j >= 0; j--) side.push(offsetAt(a0 + ((a1 - a0) * j) / 6, 13));
    slots.push(side);
  }
  out.push(slots.map((s) => `<path class="mr-deep" d="${poly(s, Z1)}"/>`).join(""));
  out.push(L(slots.map((s) => poly(s, Z1)).join(""), { tone: "lo" }));
  out.push(L(bolts.map(([x, y]) => k.ring(x, y, 2.6, Z1, P, 16)).join(""), { tone: "lo" }));
  out.push(D(bolts.map(([x, y]) => at([x, y, Z1])), { size: 0.6 }));
  // pasadores de centrado
  for (const [x, y] of [[HOUSE.x + 9, HOUSE.y + 9], [HOUSE.x + HOUSE.w - 9, HOUSE.y + HOUSE.d - 9]]) {
    out.push(S(k.cylinder(x, y, 2, Z1, 2.4, P, 20), { tone: "hi" }));
  }
  return out.join("");
}

// ---------- interior: lo que se ve por la abertura ----------
function portWindow(a0, a1, z0, z1) {
  const n = 12, pts = [];
  for (let i = 0; i <= n; i++) { const [x, y] = M.housing(a0 + ((a1 - a0) * i) / n); pts.push(at([x, y, z0])); }
  for (let i = n; i >= 0; i--) { const [x, y] = M.housing(a0 + ((a1 - a0) * i) / n); pts.push(at([x, y, z1])); }
  return "M" + pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join("L") + "Z";
}
const angleOfX = (x, around) => { // parámetro de la carcasa en la cintura −y con esa x
  let lo = around - 0.8, hi = around + 0.8;
  for (let i = 0; i < 40; i++) { const m = (lo + hi) / 2; if (M.housing(m)[0] < x) lo = m; else hi = m; }
  return (lo + hi) / 2;
};
const A_IN = angleOfX(INTAKE_X, -Math.PI / 2);
const A_EX = angleOfX(EXHAUST_X, -Math.PI / 2);

function gearRing(n, rp, add, ded, internal, steps = 8) {
  const pts = [];
  for (let i = 0; i < n * steps; i++) {
    const t = (i / (n * steps)) * TAU;
    let u = ((t * n) / TAU) % 1; if (u > 0.5) u -= 1; u = Math.abs(u);
    const w = u < 0.16 ? 1 : u > 0.34 ? 0 : 1 - (u - 0.16) / 0.18;
    const r = internal ? rp + ded - (add + ded) * w : rp - ded + (add + ded) * w;
    pts.push([r * Math.cos(t), r * Math.sin(t)]);
  }
  return pts;
}
const STAT = gearRing(34, 2 * M.E, 1.6, 1.8, false);
const ROTOR_GEAR = gearRing(51, 3 * M.E, 1.6, 1.8, true);
const JOURNAL_R = 18.6;

function interiorStatic() {
  const out = [];
  out.push(`<path class="mr-wall" d="${TROCH_OPEN}"/>`);
  out.push(`<path class="mr-floor" d="${poly(TROCH, Z0)}"/>`);
  out.push(L(poly(TROCH, Z0), { tone: "lo" }));
  // ventanas de las lumbreras en la pared del fondo
  out.push(`<path class="mr-deep" d="${portWindow(A_IN - 0.16, A_IN + 0.16, Z0 + 9, Z1 - 9)}"/>`);
  out.push(`<path class="mr-deep" d="${portWindow(A_EX - 0.14, A_EX + 0.14, Z0 + 10, Z1 - 10)}"/>`);
  out.push(L(portWindow(A_IN - 0.16, A_IN + 0.16, Z0 + 9, Z1 - 9) + portWindow(A_EX - 0.14, A_EX + 0.14, Z0 + 10, Z1 - 10), { tone: "lo" }));
  // eje en el suelo (se ve en el hueco del rotor)
  return out.join("");
}

const stationary = () => {
  const out = [];
  out.push(`<path class="iso-top mr-gear" d="${poly(STAT, ZR)}"/>`);
  out.push(L(poly(STAT, ZR), { tone: "mid" }));
  return out.join("");
};

// ---------- bujías en la cara +y ----------
function plugs() {
  const out = [];
  const face = HOUSE.y + HOUSE.d;
  for (const a of byDepth(PLUG_A, (a) => [M.housing(a)[0], face, 0])) {
    const x = M.housing(a)[0];
    out.push(S(k.slabOf({ x: x - 8, y: face - 1, w: 16, d: 6, r: 2 }, Z0 + 8, M.B - 16, P, 3, 0.4), { tone: "mid" }));
    const F = G.frameAlong([x, face + 5, PORT_Z], [0, 1, 0]);
    const hex = Array.from({ length: 6 }, (_, i) => [6.2 * Math.cos((i * TAU) / 6 + TAU / 12), 6.2 * Math.sin((i * TAU) / 6 + TAU / 12)]);
    out.push(S(G.disc(0, 1.2, 6.4, F, P), { tone: "mid" }));
    out.push(S(G.prismOf(F, hex, 1.2, 6, P), { tone: "mid" }));
    out.push(S(G.disc(6, 7.4, 4.2, F, P), { tone: "hi" }));
    out.push(S(G.solidOf([[7.4, 3.6], [19, 3.0], [21, 2.0], [21.6, 1.4]], F, P), { tone: "hi", inner: L([9.5, 12, 14.5, 17].map((s) => G.arcOf(F, s, 3.6 - (0.6 * (s - 7.4)) / 11.6, P, { slope: -0.05 })).join(""), { tone: "faint" }) }));
    out.push(S(G.solidOf([[21.6, 2.4], [24.4, 2.4], [25.4, 1.6]], F, P), { tone: "mid" }));
  }
  return out.join("");
}

// ---------- eje: cubo con marca ----------
function hub() {
  const out = [];
  out.push(S(k.cylinder(0, 0, 6, ZR, HUB_TOP - 4 - ZR, P, 32), { tone: "mid", crease: "none" }));
  out.push(S(k.cylinder(0, 0, 10, HUB_TOP - 4, 4, P, 48, 0.5), { tone: "mid" }));
  out.push(L(k.knurl(0, 0, 10, HUB_TOP - 4, HUB_TOP, 40, P, 0.3), { tone: "lo" }));
  out.push(L(k.ring(0, 0, 3, HUB_TOP, P, 20), { tone: "lo" }));
  out.push(D([at([0, 0, HUB_TOP])], { size: 0.5 }));
  return out.join("");
}

const flash = `<radialGradient id="mr-glow"><stop offset="0" stop-color="var(--mr-flame-core)" stop-opacity="1"/><stop offset=".45" stop-color="var(--mr-flame)" stop-opacity=".75"/><stop offset="1" stop-color="var(--mr-flame)" stop-opacity="0"/></radialGradient>`;
const plugIn = M.housing(Math.PI / 2);
const glowAt = at([plugIn[0], plugIn[1] - 8, ZR]);

const svg = k.figureSvg({
  width: W,
  height: H,
  label:
    "Motor rotativo de un rotor con la tapa delantera quitada, sobre un banco. Dentro de la carcasa en forma de epitrocoide gira un rotor triangular de flancos curvos sobre la excéntrica del eje. Sus tres vértices rozan siempre la carcasa y dejan tres cámaras que crecen y menguan: admisión, compresión, expansión tras la chispa de las bujías, y escape.",
  body: [
    `<defs>${flash}<clipPath id="mr-open"><path d="${TROCH_OPEN}"/></clipPath><clipPath id="mr-burn"><path data-part="burnclip"/></clipPath></defs>`,
    plate(),
    farPipes(),
    engineBlock(),
    `<g clip-path="url(#mr-open)">`,
    interiorStatic(),
    `<g data-part="rotor"></g>`,
    `<g data-part="gas"></g>`,
    `<path class="mr-deep" data-part="bore"/>`,
    stationary(),
    `<g data-part="journal"></g>`,
    `<ellipse data-part="glow" cx="${glowAt[0].toFixed(1)}" cy="${glowAt[1].toFixed(1)}" rx="${(70 * P.scale).toFixed(1)}" ry="${(40 * P.scale).toFixed(1)}" fill="url(#mr-glow)" clip-path="url(#mr-burn)" opacity="0" style="mix-blend-mode:var(--mr-blend)"/>`,
    `</g>`,
    L(TROCH_OPEN, { tone: "mid" }),
    hub(),
    `<path data-part="mark" class="iso-line" data-tone="lit" data-free="end" style="stroke-width:1.4"/>`,
    plugs(),
    `<g data-part="spark"></g>`,
  ],
});

const MODEL = readFileSync(join(HERE, "model.mjs"), "utf8").replace(/^export /gm, "");
const live = `
const P = ${JSON.stringify(P)};
const ZR = ${ZR}, Z0 = ${Z0}, HUB_TOP = ${HUB_TOP}, JOURNAL_R = ${JOURNAL_R};
const ROTOR_GEAR = ${JSON.stringify(ROTOR_GEAR.map(([x, y]) => [+x.toFixed(2), +y.toFixed(2)]))};
const PLUGS = ${JSON.stringify(PLUG_A.map((a) => M.housing(a)[0]))}, PLUG_FACE = ${HOUSE.y + HOUSE.d + 5}, PORT_Z = ${PORT_Z};
// TAU viene del modelo
const stage = document.querySelector(".iso-stage");
const svg = stage.querySelector("svg");
const $ = (n) => svg.querySelector('[data-part="' + n + '"]');
const burnClip = $("burnclip"), rotorG = $("rotor"), gasG = $("gas"), bore = $("bore"), journalG = $("journal"), glow = $("glow"), mark = $("mark"), spark = $("spark");
const readout = document.querySelector("[data-readout]");
const still = matchMedia("(prefers-reduced-motion: reduce)");
const pts = (list, z) => "M" + list.map((p) => { const s = iso([p[0], p[1], z], P); return s[0].toFixed(1) + " " + s[1].toFixed(1); }).join("L") + "Z";
const rot = ([u, v], phi) => { const t = phi / 3, c = centre(phi); return [c[0] + u * Math.cos(t) - v * Math.sin(t), c[1] + u * Math.sin(t) + v * Math.cos(t)]; };
const LOCAL = rotorLocal(24);
const SEAL = LOCAL.map(([u, v]) => { const l = Math.hypot(u, v); return [u * (l - 4) / l, v * (l - 4) / l]; });
const CORNER = [0, 1, 2].map((i) => [(R - 7) * Math.cos(TAU * i / 3), (R - 7) * Math.sin(TAU * i / 3)]);
const circ = (cx, cy, r, n = 16) => Array.from({ length: n }, (_, i) => [cx + r * Math.cos(TAU * i / n), cy + r * Math.sin(TAU * i / n)]);
const PH_CLASS = ["mr-in", "mr-comp", "mr-exp", "mr-ex"];
const burnOf = (psi) => { // 0 → 1 en la chispa (ψ ≈ 86°), se apaga hacia 150°
  const d = ((psi * 180 / Math.PI - 84) % 360 + 360) % 360;
  if (d > 300) return 0;
  return d < 4 ? d / 4 : Math.exp(-(d - 4) / 22);
};
function draw(phi) {
  const ring = LOCAL.map((p) => rot(p, phi));
  rotorG.innerHTML = solidSvg(extrude(ring, Z0, ZR - Z0, P, { bevel: 0.6 }), { tone: "hi", crease: "lo" })
    + lineSvg(pts(SEAL.map((p) => rot(p, phi)), ZR), { tone: "faint" })
    + lineSvg(CORNER.map(([u, v]) => pts(circ(u, v, 2.2).map((p) => rot(p, phi)), ZR)).join(""), { tone: "lo" })
    + dotsSvg([0, 1, 2].map((i) => iso([...apexWorld(phi, i), ZR], P)), { size: 0.9, tone: "hi" })
    + dotsSvg([iso([...rot([ (R / 2 + SAG - 9) * Math.cos(Math.PI / 3), (R / 2 + SAG - 9) * Math.sin(Math.PI / 3)], phi), ZR], P)], { size: 1.3, tone: "lit" });
  let gas = "", burn = 0;
  for (let i = 0; i < 3; i++) {
    const ph = phaseOf(phi, i);
    const b = burnOf(faceAngle(phi, i));
    if (b >= burn) { burn = b; burnClip.setAttribute("d", pts(chamber(phi, i, 24), ZR)); }
    gas += '<path class="mr-gas ' + PH_CLASS[ph] + '" d="' + pts(chamber(phi, i, 24), ZR) + '"/>';
  }
  gasG.innerHTML = gas;
  bore.setAttribute("d", pts(ROTOR_GEAR.map((p) => rot(p, phi)), ZR));
  const c = centre(phi);
  journalG.innerHTML = '<path class="iso-top mr-journal" d="' + pts(circ(c[0], c[1], JOURNAL_R, 48), ZR + 0.5) + '"/>'
    + lineSvg(pts(circ(c[0], c[1], JOURNAL_R, 48), ZR + 0.5), { tone: "mid" })
    + lineSvg(pts(circ(c[0], c[1], JOURNAL_R - 3, 48), ZR + 0.5), { tone: "faint" })
    + dotsSvg([iso([c[0] + 12 * Math.cos(phi), c[1] + 12 * Math.sin(phi), ZR + 0.5], P)], { size: 0.8, tone: "mid" });
  const a = iso([3.4 * Math.cos(phi), 3.4 * Math.sin(phi), HUB_TOP], P), b = iso([9 * Math.cos(phi), 9 * Math.sin(phi), HUB_TOP], P);
  mark.setAttribute("d", "M" + a[0].toFixed(1) + " " + a[1].toFixed(1) + "L" + b[0].toFixed(1) + " " + b[1].toFixed(1));
  glow.setAttribute("opacity", (0.95 * burn).toFixed(3));
  const tip = burn > 0.6 ? PLUGS.map((x) => iso([x, PLUG_FACE + 26, PORT_Z], P)) : [];
  spark.innerHTML = tip.length ? dotsSvg(tip, { size: 1.6, tone: "lit", pulse: false }) : "";
  const deg = Math.round(((phi * 180 / Math.PI) % 1080 + 1080) % 1080);
  const text = "eje " + deg + "° · rotor " + Math.round(deg / 3) + "° · ● " + PHASES[phaseOf(phi, 0)] + " · " + Math.round(volumeCc(phi, 0)) + " cm³";
  if (readout.textContent !== text) readout.textContent = text;
  stage.setAttribute("aria-valuetext", text);
}
const RATE = TAU * 0.45; // 0,45 vueltas de eje por segundo (cámara lenta)
let phi = TAU * 0.25, target = phi, frame = 0, last = 0, visible = false, running = !still.matches, idle = 0, drag = null;
function tick(now) {
  const dt = last ? Math.min((now - last) / 1000, 1 / 20) : 1 / 60;
  last = now;
  if (running && !drag) target += RATE * dt;
  phi += (target - phi) * (drag ? 1 - Math.exp(-dt / 0.08) : 1);
  draw(phi);
  frame = visible && (running || Math.abs(target - phi) > 1e-4) ? requestAnimationFrame(tick) : 0;
}
const run = () => { if (!frame && visible) { last = 0; frame = requestAnimationFrame(tick); } };
const pause = () => { running = false; clearTimeout(idle); idle = setTimeout(() => { running = !still.matches; run(); }, 4000); };
new IntersectionObserver((e) => { visible = e[e.length - 1].isIntersecting; if (visible) run(); }, { rootMargin: "120px 0px" }).observe(stage);
stage.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, from: target }; stage.setPointerCapture(e.pointerId); pause(); run(); });
stage.addEventListener("pointermove", (e) => { if (!drag) return; const w = svg.getBoundingClientRect().width; target = drag.from + ((e.clientX - drag.x) / w) * TAU * 3; pause(); run(); });
const end = () => { drag = null; };
stage.addEventListener("pointerup", end); stage.addEventListener("pointercancel", end);
stage.addEventListener("keydown", (e) => {
  const step = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[e.key];
  if (e.key === " ") { e.preventDefault(); running = !running; clearTimeout(idle); run(); return; }
  if (!step) return;
  e.preventDefault(); target = Math.round(target / (Math.PI / 4)) * (Math.PI / 4) + step * Math.PI / 4; pause(); run();
});
draw(phi);
`;

const ART_CSS_COMMON = `
.iso{--mr-flame:#ff7a1a;--mr-flame-core:#ffd27a;--mr-blend:multiply;--mr-exhaust:#9a7440}
.iso[data-theme="dark"]{--mr-flame:#ff6a10;--mr-flame-core:#ffd890;--mr-blend:screen;--mr-exhaust:#c99a5c}
.mr-wall{fill:var(--anatomy-faint)}
.mr-floor{fill:var(--anatomy-paper)}
.mr-deep{fill:var(--anatomy-lo)}
.iso[data-theme="dark"] .mr-deep{fill:#070707}
.mr-gear{fill:var(--anatomy-face)}
.iso[data-theme="dark"] .mr-gear{fill:var(--anatomy-lo)}
.mr-journal{fill:var(--anatomy-top)}
.mr-gas{stroke:none;fill-opacity:.26}
.iso[data-theme="dark"] .mr-gas{fill-opacity:.3}
.mr-in{fill:var(--anatomy-blue)}
.mr-comp{fill:var(--anatomy-green)}
.mr-exp{fill:var(--anatomy-red)}
.mr-ex{fill:var(--mr-exhaust)}
.iso-swatch[data-mark="dim"] path{stroke:var(--mr-exhaust)}
.iso-stage{touch-action:pan-y;cursor:grab}
.iso-stage:active{cursor:grabbing}
`;

const body = k.plateHtml({
  fig: "Fig 2",
  title: "Motor rotativo",
  hint: "Arrastra para girar",
  readout: "eje 90° · rotor 30°",
  keys: [
    { mark: "blue", label: "Admisión: la cámara crece y aspira mezcla" },
    { mark: "green", label: "Compresión: la cámara mengua hacia las bujías" },
    { mark: "red", label: "Expansión: la chispa enciende y el gas empuja el rotor" },
    { mark: "dim", label: "Escape: la cámara mengua y expulsa el gas" },
    { mark: "lit", label: "Marca de la cara que sigue la lectura" },
  ],
  caption: `Un rotor triangular gira sobre la excéntrica del eje dentro de una carcasa con forma de epitrocoide (R = ${M.R * M.MM} mm, e = ${M.E * M.MM} mm, ancho ${M.B * M.MM} mm). Un engranaje interior de 51 dientes en el rotor rueda sobre uno fijo de 34, así que el rotor da una vuelta por cada tres del eje. Cada cara pasa por las cuatro fases en una vuelta del rotor y barre ${Math.round(M.check().disp)} cm³, con una relación de compresión geométrica de ${M.check().cr.toFixed(1).replace(".", ",")}:1; como las tres caras trabajan a la vez, hay una explosión por cada vuelta del eje.`,
  body: `<div class="iso-stage" tabindex="0" role="slider" aria-label="Motor rotativo: arrastra o usa las flechas para girar el eje" aria-valuemin="0" aria-valuemax="1080">${svg}</div>`,
});

const script = kitScript() + MODEL + live;
if (process.argv.includes("--artifact")) {
  const ART_CSS = `
:root{--mr-page:#f2f2ef}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--mr-page:#0b0b0b;color-scheme:dark}}
:root[data-theme="dark"]{--mr-page:#0b0b0b;color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--mr-page);margin:0;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
#mr-root{background:var(--anatomy-page);color:var(--anatomy-text);font:14px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
.iso-page{width:min(640px,100%);margin:0 auto;padding-block:32px 48px}
`;
  const sync = `(function(){var r=document.documentElement,w=document.getElementById("mr-root"),mq=matchMedia("(prefers-color-scheme: dark)");function f(){w.setAttribute("data-theme",r.getAttribute("data-theme")||(mq.matches?"dark":"light"))}f();mq.addEventListener("change",f);new MutationObserver(f).observe(r,{attributes:true,attributeFilter:["data-theme"]})})();`;
  const html = `<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Motor rotativo</title>\n<style>${k.ISO_CSS}${ART_CSS_COMMON}${ART_CSS}</style></head><body>\n<div class="iso" id="mr-root" data-theme="light"><main class="iso-page">${body}</main></div>\n<script>${sync}</script>\n<script type="module">${script.replace(/<\/(script)/gi, "<\\/$1")}</script></body></html>\n`;
  writeFileSync(join(OUT, "motor-rotativo-artifact.html"), html);
  console.log("wrote", join(OUT, "motor-rotativo-artifact.html"));
}
const name = theme === "light" ? "motor-rotativo.html" : "motor-rotativo-dark.html";
const page = k.pageHtml({ title: "Motor rotativo", theme, body, script, width: 640 }).replace('<html lang="en">', '<html lang="es">').replace("</style>", ART_CSS_COMMON + "</style>");
writeFileSync(join(OUT, name), page);
console.log("wrote", join(OUT, name));
