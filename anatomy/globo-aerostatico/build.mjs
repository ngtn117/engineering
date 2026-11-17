import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "./skill/kit/iso-kit.mjs";
import * as G from "./skill/kit/lathe.mjs";
import { tubePieces, tubeSvg } from "./skill/kit/tube.mjs";
import { glCamera } from "./skill/kit/gl.mjs";
import { kitScript, glScript } from "./skill/scripts/inline-kit.mjs";
import * as M from "./model.mjs";
import { makeEnvelope } from "./envelope.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = process.argv.find((a) => a.startsWith("--out="))?.slice(6) ?? HERE;
const theme = process.argv.includes("--dark") ? "dark" : "light";

// Unidades: 1 = 1 dm. La envoltura va a escala; la cesta y el quemador, a 1,5×.
const W = 560;
const H = 650;
const LIFT_MAX = 56;
const LIFT_K = 350; // m
const liftOf = (alt) => LIFT_MAX * (1 - Math.exp(-alt / LIFT_K));

const PLATE = { x: -92, y: -92, w: 184, d: 184, r: 10 };
const PLATE_H = 10;
const FOOT_H = 5;

const BASKET = { x: -9, y: -12, w: 18, d: 24, r: 1.6 };
const SKID_H = 1.6;
const FLOOR_Z = SKID_H;
const RIM_Z = FLOOR_Z + 16.5;
const RIM_H = 1.8;
const WALL = 1.1;
const FRAME_Z = 34;
const FRAME_H = 1.4;
const FRAME = { x: -10.5, y: -13.5, w: 21, d: 27 };
const BLOCK_Z = FRAME_Z + FRAME_H;
const COIL_Z0 = BLOCK_Z + 3.2;
const COIL_Z1 = COIL_Z0 + 5.2;
const NOZZLE_Z = COIL_Z1 + 0.8;
const MOUTH_Z = 76;
const R_EQ = 87;
const R_MOUTH = 22;
const S_EQ = 110;
const R_CROWN = 22;
const DOME = 80;
const S_CROWN = S_EQ + DOME * Math.sqrt(1 - (R_CROWN / R_EQ) ** 2);
const VENT_DROP = 14;
const B = [36, -36];                       // donde se posa la cesta en la plataforma
const DH = [-Math.SQRT1_2, Math.SQRT1_2]; // hacia dónde se tiende la envoltura antes de inflarla
const LIE_D = 30;                         // distancia de la cesta a la boca con la envoltura tendida

const radius = (s) => {
  if (s <= S_EQ) {
    const x = Math.max(0, s) / S_EQ;
    return R_MOUTH + (R_EQ - R_MOUTH) * (1 - (1 - x) ** 2);
  }
  const q = Math.min(1, (s - S_EQ) / DOME);
  return R_EQ * Math.sqrt(Math.max(0, 1 - q * q));
};
const slope = (s) => {
  if (s <= S_EQ) return (R_EQ - R_MOUTH) * 2 * (1 - Math.max(0, s) / S_EQ) / S_EQ;
  const q = Math.min(0.9999, (s - S_EQ) / DOME);
  return (-R_EQ * q) / (DOME * Math.sqrt(1 - q * q));
};

const MAST = [80, -82];
const MAST_PLAN = { x: MAST[0] - 3, y: MAST[1] - 3, w: 6, d: 6, r: 0.8 };
const MAST_TOP = FLOOR_Z + LIFT_MAX + 12;

const P = k.fitProjection(
  [
    ...k.boxCorners(PLATE, -PLATE_H - FOOT_H, 0),
    ...[0, 1, 2, 3, 4, 5, 6, 7].map((i) => {
      const a = (i / 8) * Math.PI * 2;
      return [B[0] + Math.cos(a) * R_EQ, B[1] + Math.sin(a) * R_EQ, MOUTH_Z + S_EQ + LIFT_MAX];
    }),
    [B[0], B[1], MOUTH_Z + S_CROWN + LIFT_MAX + 4],
  ],
  W,
  H,
  { pad: 22, azimuth: 50 },
);
const KS = G.scaleOf(P);
const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (pts, style) => k.dotsSvg(pts, style);
const depth = (p) => k.depthOf(p, P);
const byDepth = (list, key = (x) => x) => [...list].sort((a, b) => depth(key(a)) - depth(key(b)));
const view = G.viewOf(P);

// ---------- Base: la plataforma de despegue con su mástil de altura ----------
function plate() {
  const out = [`<path class="iso-halo" d="${k.haloOf(PLATE, -PLATE_H - FOOT_H, PLATE_H, P)}"/>`];
  for (const [x, y] of byDepth(k.corners(PLATE, 22), ([x, y]) => [x, y, 0])) {
    out.push(S(k.cylinder(x, y, 8, -PLATE_H - FOOT_H, 1.6, P, 28), { tone: "lo" }));
    out.push(S(k.cylinder(x, y, 6, -PLATE_H - FOOT_H + 1.6, FOOT_H - 1.6, P, 28), { tone: "mid" }));
  }
  out.push(S(k.slabOf(PLATE, -PLATE_H, PLATE_H, P, 8, 1.6), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(PLATE, 6), 0, P, 8), { tone: "lo" }));
  const screws = k.corners(PLATE, 11);
  out.push(L(screws.map(([x, y]) => k.ring(x, y, 2.4, 0, P, 16)).join(""), { tone: "lo" }));
  out.push(D(screws.map(([x, y]) => at([x, y, 0])), { size: 0.5 }));
  // Círculo de despegue: donde se posa la cesta.
  out.push(L(k.ring(B[0], B[1], 26, 0, P, 96), { tone: "faint" }));
  out.push(L(k.ring(B[0], B[1], 30, 0, P, 96), { tone: "faint" }));
  const marks = [0, 1, 2, 3].map((i) => {
    const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
    return k.lineOnTop([B[0] + Math.cos(a) * 26, B[1] + Math.sin(a) * 26], [B[0] + Math.cos(a) * 30, B[1] + Math.sin(a) * 30], 0, P);
  });
  out.push(L(marks.join(""), { tone: "lo" }));
  // Regla a lo largo del borde cercano.
  const strip = { x: PLATE.x + 18, y: PLATE.y + PLATE.d - 16, w: 110, d: 7, r: 1 };
  out.push(S(k.slabOf(strip, 0, 0.6, P, 3), { tone: "lo", crease: "none" }));
  const ticks = k.topTicks(strip.x + 4, strip.x + strip.w - 4, 5, 5, strip.y + 0.8, 0.6, [2, 3.8], P);
  out.push(L(ticks.minor, { tone: "lo" }), L(ticks.major, { tone: "mid" }));
  out.push(D([at([strip.x + 2, strip.y + 3.5, 0.6]), at([strip.x + strip.w - 2, strip.y + 3.5, 0.6])], { size: 0.45 }));
  // Placa de identificación.
  const label = { x: 40, y: 58, w: 30, d: 16, r: 1.2 };
  out.push(S(k.slabOf(label, 0, 0.8, P, 3, 0.3), { tone: "mid" }));
  out.push(L([4, 8, 12].map((dy, i) => k.lineOnTop([label.x + 5, label.y + dy], [label.x + label.w - (i === 2 ? 12 : 5), label.y + dy], 0.8, P)).join(""), { tone: "lo", free: true }));
  out.push(D(k.corners(label, 2).map(([x, y]) => at([x, y, 0.8])), { size: 0.4 }));
  return out.join("");
}

// Ventilador de inflado en frío: llena la envoltura tendida de aire antes de encender el quemador.
const FAN_C = [-4, 44];                   // en coordenadas de la cesta
const FAN_Z = 14;
const MOUTH_LIE = [DH[0] * LIE_D, DH[1] * LIE_D];
const FAN_A = G.unit3([MOUTH_LIE[0] - FAN_C[0], MOUTH_LIE[1] - FAN_C[1], 0]);
const FAN_U = [-FAN_A[1], FAN_A[0], 0];
const FAN_F = G.frameOf([FAN_C[0], FAN_C[1], FAN_Z], FAN_A, FAN_U, [0, 0, 1]);
const fanBlades = (phase) => G.spokesOf(FAN_F, 0, 2.4, 10.2, 5, P, { phase, sweep: 0.5 });
function fan() {
  const out = [];
  const toward = G.dot3(FAN_A, view) > 0;
  const face = toward ? 3.2 : -3.2;
  const on = (o) => G.frameOf([FAN_C[0] + FAN_A[0] * o, FAN_C[1] + FAN_A[1] * o, 0], [0, 0, 1], FAN_A, FAN_U);
  const rect = (w, d) => [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]];
  const shift = (poly, du, dv) => poly.map(([u, v]) => [u + du, v + dv]);
  const base = on(-7);
  out.push(`<path class="iso-halo" d="${k.haloOf({ x: FAN_C[0] - 18, y: FAN_C[1] - 14, w: 30, d: 28, r: 8 }, 0, 0.1, P)}" style="filter:blur(6px)"/>`);
  const skids = [-10, 10].map((dv) => ({ dv, depth: G.dot3(G.pointOf(base, 0, Math.abs(dv), dv > 0 ? Math.PI / 2 : -Math.PI / 2), view) }));
  for (const { dv } of skids.sort((a, b) => a.depth - b.depth)) out.push(S(G.prismOf(base, shift(rect(28, 2), 0, dv), 0, 1.6, P), { tone: "lo" }));
  const legs = [-8.5, 8.5].map((dv) => S(G.prismOf(on(0), shift(rect(2, 2), 0, dv), 1.6, 3.4, P), { tone: "mid" }));
  const shroud = [
    S(G.ringBand(-3.2, 3.2, 10.4, 11.4, FAN_F, P), { tone: "mid", inner: L(G.arcOf(FAN_F, 0, 11.4, P), { tone: "faint" }) }),
    `<path class="gb-fan-void" d="${G.circleOf(FAN_F, face, 10.4, P, 72)}"/>`,
    `<path data-part="fan-blades" class="iso-line" data-tone="lo" d="${fanBlades(0.2)}"/>`,
    S(G.disc(-1, 1, 2.4, FAN_F, P), { tone: "mid" }),
    L([4, 7, 10.4].map((r) => G.circleOf(FAN_F, face + Math.sign(face) * 0.2, r, P, 72)).join("") + G.spokesOf(FAN_F, face + Math.sign(face) * 0.2, 4, 10.4, 8, P, { phase: 0.06 }), { tone: "mid" }),
    D(G.dotsOf(FAN_F, face, 10.9, 12, P, { all: true }), { size: 0.4 }),
  ];
  // Motor de gasolina sobre el bastidor, detrás del aro.
  const boxF = on(-14);
  const box = [
    S(G.prismOf(boxF, rect(11, 12), 1.6, 11, P), { tone: "mid" }),
    L(G.circleOf(G.frameOf(G.pointOf(boxF, 11, 0, 0), [0, 0, 1], FAN_A, FAN_U), 0, 2.2, P, 24), { tone: "lo" }),
    S(G.disc(11, 12.4, 1.4, G.frameOf(G.add3(G.pointOf(boxF, 0, 0, 0), G.add3(G.mul3(FAN_A, -2.5), G.mul3(FAN_U, 3))), [0, 0, 1], FAN_A, FAN_U), P), { tone: "mid" }),
    D(rect(9, 10).map(([u, v]) => at(G.add3(G.add3(G.pointOf(boxF, 11, 0, 0), G.mul3(FAN_A, u)), G.mul3(FAN_U, v)))), { size: 0.4 }),
  ];
  const boxNear = G.dot3(FAN_A, view) < 0;
  out.push(...legs);
  if (boxNear) out.push(...shroud, ...box);
  else out.push(...box, ...shroud);
  return out.join("");
}

const TICKS = Array.from({ length: 11 }, (_, i) => i * 100);
function mast() {
  const out = [];
  const foot = { x: MAST[0] - 8, y: MAST[1] - 8, w: 16, d: 16, r: 2 };
  out.push(S(k.slabOf(foot, 0, 4, P, 4, 0.6), { tone: "mid" }));
  out.push(D(k.corners(foot, 2.6).map(([x, y]) => at([x, y, 4])), { size: 0.45 }));
  out.push(S(k.slabOf(MAST_PLAN, 4, MAST_TOP - 4, P, 3, 0.4), { tone: "mid" }));
  out.push(S(k.slabOf(k.insetPlan(MAST_PLAN, -0.8), MAST_TOP, 2, P, 3, 0.4), { tone: "mid" }));
  // Escala de altitud: una raya cada 100 m, más larga cada 500 m. La escala se comprime con la altura.
  // Regleta de altitud atornillada a la cara del mástil.
  const strip = { x: MAST_PLAN.x + MAST_PLAN.w, y: MAST_PLAN.y + 0.5, w: 0.6, d: MAST_PLAN.d - 1, r: 0.2 };
  const z0 = FLOOR_Z - 0.6, z1 = FLOOR_Z + LIFT_MAX + 2;
  const fx = strip.x + strip.w;
  const root = strip.y + strip.d - 0.8;
  out.push(S(k.slabOf(strip, z0, z1 - z0, P, 2), { tone: "lo", crease: "none" }));
  out.push(L(k.segment([fx, root, z0], [fx, root, z1], P), { tone: "lo" }));
  const minor = [], major = [];
  for (const h of TICKS) {
    const z = FLOOR_Z + liftOf(h);
    const big = h % 500 === 0;
    const len = big ? 3.6 : 2.0;
    (big ? major : minor).push(k.segment([fx, root, z], [fx, root - len, z], P));
  }
  out.push(L(minor.join(""), { tone: "lo" }), L(major.join(""), { tone: "hi" }));
  out.push(D([at([fx, strip.y + 0.9, z0 + 1.2]), at([fx, strip.y + 0.9, z1 - 1.2])], { size: 0.4 }));
  return out.join("");
}
function carriage() {
  const out = [];
  const plan = k.insetPlan(MAST_PLAN, -2.4);
  // Índice: una línea iluminada que rodea el collarín justo a la altura que marca.
  out.push(S(k.slabOf(plan, -2, 4, P, 3, 0.4), { tone: "hi", crease: "lo", inner: L(k.sideSeam(plan, 0, P, 3), { tone: "lit" }) }));
  out.push(D(k.corners(plan, 1.6).map(([x, y]) => at([x, y, 2])), { size: 0.4, tone: "lo" }));
  const knob = [plan.x + plan.w / 2, plan.y - 2];
  out.push(S(k.slabOf({ x: knob[0] - 1, y: plan.y - 1.6, w: 2, d: 1.8, r: 0.5 }, -1, 2, P, 2), { tone: "mid", crease: "none" }));
  out.push(S(k.cylinder(knob[0], knob[1], 2, -1.6, 3.2, P, 20), { tone: "mid" }));
  out.push(L(k.knurl(knob[0], knob[1], 2, -1.6, 1.6, 16, P), { tone: "lo" }));
  return out.join("");
}

// ---------- La cesta ----------
const CYL = [
  [-4.6, -7.4],
  [4.4, -7.4],
  [-4.6, 0.4],
];
const CYL_R = 3.3;
const CYL_H = 12.5;
const cylinderTop = FLOOR_Z + 0.6 + CYL_H;
const VALVE_TOP = cylinderTop + 3.2;

function wallPlans() {
  const { x, y, w, d } = BASKET;
  return {
    back: [
      { x, y, w, d: WALL, r: 0.4, side: "y0" },
      { x, y, w: WALL, d, r: 0.4, side: "x0" },
    ],
    front: [
      { x: x + w - WALL, y, w: WALL, d, r: 0.4, side: "x1" },
      { x, y: y + d - WALL, w, d: WALL, r: 0.4, side: "y1" },
    ],
  };
}
const wickerOn = (plan) => {
  // Mimbre: hiladas horizontales que rodean la pared de esquina a esquina, y varas verticales.
  const rows = [];
  for (let z = FLOOR_Z + 1.4; z < RIM_Z - 0.4; z += 1.25) rows.push(k.sideSeam(plan, z, P, 2));
  return rows.join("");
};
function stakes(plan, side) {
  const lines = [];
  const along = side === "x1" ? [plan.y + 1.5, plan.y + plan.d - 1.5, "y"] : [plan.x + 1.5, plan.x + plan.w - 1.5, "x"];
  for (let t = along[0]; t <= along[1] + 1e-6; t += 2.25) {
    const a = along[2] === "y" ? [plan.x + plan.w, t, FLOOR_Z] : [t, plan.y + plan.d, FLOOR_Z];
    const b = along[2] === "y" ? [plan.x + plan.w, t, RIM_Z] : [t, plan.y + plan.d, RIM_Z];
    lines.push(k.segment(a, b, P));
  }
  return lines.join("");
}

function basketBack() {
  const out = [];
  out.push(`<path class="iso-halo" data-part="basket-halo" d="${k.haloOf(k.insetPlan(BASKET, -2), 0, 0.1, P)}" style="filter:blur(5px)"/>`);
  for (const xx of [BASKET.x + 3, BASKET.x + BASKET.w - 5]) {
    out.push(S(k.slabOf({ x: xx, y: BASKET.y - 1, w: 2, d: BASKET.d + 2, r: 0.9 }, 0, SKID_H, P, 3), { tone: "lo" }));
  }
  out.push(S(k.slabOf(BASKET, FLOOR_Z, 0.6, P, 3), { tone: "lo" }));
  const { back } = wallPlans();
  for (const plan of back) out.push(S(k.slabOf(plan, FLOOR_Z, RIM_Z - FLOOR_Z, P, 2), { tone: "mid" }));
  // Suelo interior: tablero de contrachapado con su junta.
  out.push(L(k.lineOnTop([BASKET.x + WALL, 4], [BASKET.x + BASKET.w - WALL, 4], FLOOR_Z + 0.6, P), { tone: "faint" }));
  return out.join("");
}

function propane([x, y]) {
  const out = [];
  const F = G.frameOf([x, y, FLOOR_Z + 0.6], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
  const body = [[0, CYL_R - 0.4], [0.4, CYL_R], [CYL_H - 2.2, CYL_R, 1], [CYL_H - 1.2, CYL_R * 0.86, 1], [CYL_H - 0.3, CYL_R * 0.5, 1], [CYL_H, 1.1]];
  const strapS = [3.2, 8.4];
  out.push(S(G.solidOf(body, F, P), { tone: "hi", crease: "lo", inner: L(strapS.map((s) => G.arcOf(F, s, CYL_R, P)).join(""), { tone: "lo" }) }));
  // Válvula de servicio con volante y manómetro de nivel.
  const valve = G.frameOf([x, y, cylinderTop], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
  out.push(S(G.disc(0, 1.4, 0.9, valve, P), { tone: "mid" }));
  out.push(S(G.disc(1.4, 2.0, 1.7, valve, P), { tone: "mid", inner: L(G.circleOf(valve, 2.0, 1.1, P, 24), { tone: "lo" }) }));
  out.push(D([at([x, y, cylinderTop + 2.0])], { size: 0.5, tone: "hi" }));
  out.push(S(G.disc(2.0, 3.2, 0.5, valve, P), { tone: "mid" }));
  const gauge = G.frameAlong([x + 1.4, y + 1.4, cylinderTop - 0.4], G.unit3([1, 1, 0.6]));
  out.push(S(G.disc(0, 0.6, 0.9, gauge, P), { tone: "mid" }));
  return out.join("");
}

function hosePieces() {
  const all = [];
  for (const [x, y] of CYL) {
    const to = [Math.sign(x) * 1.6, -2.6, BLOCK_Z + 0.4];
    const route = G.fillet([[x, y, VALVE_TOP], [x, y, FRAME_Z - 4], [x * 0.4, y * 0.35, FRAME_Z - 1], to], 2.4, 7, { P, tube: 0.55 });
    for (const piece of tubePieces(route, 0.55, P, { maxLength: 6 })) all.push(piece);
  }
  return all;
}

function basketFront() {
  const out = [];
  const { front, back } = wallPlans();
  for (const plan of front) {
    out.push(S(k.slabOf(plan, FLOOR_Z, RIM_Z - FLOOR_Z, P, 2), { tone: "mid", inner: L(wickerOn(plan), { tone: "faint" }) }));
    out.push(L(stakes(plan, plan.side), { tone: "faint" }));
  }
  // Borde acolchado de cuero alrededor de la boca de la cesta.
  const rim = [...back, ...front].map((p) => k.insetPlan(p, -0.5));
  for (const plan of byDepth(rim, (p) => [p.x + p.w / 2, p.y + p.d / 2, RIM_Z])) {
    out.push(S(k.slabOf(plan, RIM_Z, RIM_H, P, 3, 0.3), { tone: "mid", crease: "lo" }));
  }
  // Asas de cuerda en la cara cercana.
  for (const yy of [BASKET.y + 6, BASKET.y + BASKET.d - 6]) {
    const x0 = BASKET.x + BASKET.w + 0.1;
    out.push(L(k.segment([x0, yy - 1.6, RIM_Z - 3], [x0 + 0.6, yy, RIM_Z - 4.4], P) + k.segment([x0 + 0.6, yy, RIM_Z - 4.4], [x0, yy + 1.6, RIM_Z - 3], P), { tone: "mid" }));
    out.push(D([at([x0, yy - 1.6, RIM_Z - 3]), at([x0, yy + 1.6, RIM_Z - 3])], { size: 0.45 }));
  }
  return out.join("");
}

// ---------- Postes, bastidor y quemador ----------
const POLES = k.corners(BASKET, 1.4);
function pole([x, y]) {
  const out = [];
  out.push(S(k.cylinder(x, y, 0.7, RIM_Z + RIM_H, FRAME_Z - RIM_Z - RIM_H, P, 16), { tone: "mid" }));
  // Funda acolchada en la parte baja del poste.
  out.push(S(k.cylinder(x, y, 1.25, RIM_Z + RIM_H, 7, P, 20, 0.2), { tone: "mid", inner: L(k.sideArc(x, y, 1.25, RIM_Z + RIM_H + 3.5, P, 12), { tone: "faint" }) }));
  return out.join("");
}
function frameBars(which) {
  const { x, y, w, d } = FRAME;
  const t = 1.3;
  const bars = {
    y0: { x, y, w, d: t, r: 0.5 },
    x0: { x, y, w: t, d, r: 0.5 },
    x1: { x: x + w - t, y, w: t, d, r: 0.5 },
    y1: { x, y: y + d - t, w, d: t, r: 0.5 },
    mid: { x: -0.65, y: y + t, w: 1.3, d: d - 2 * t, r: 0.4 },
  };
  return which.map((name) => S(k.slabOf(bars[name], FRAME_Z, FRAME_H, P, 2, 0.3), { tone: "mid" })).join("");
}
function karabiner([x, y]) {
  return S(G.sphereOf([x, y, FRAME_Z + FRAME_H + 0.9], 0.9, P), { tone: "mid" });
}

const COIL = (() => {
  const pts = [];
  const turns = 3.5;
  for (let i = 0; i <= 140; i++) {
    const t = i / 140;
    const a = t * turns * Math.PI * 2 + 0.6;
    pts.push([Math.cos(a) * 4.4, Math.sin(a) * 4.4, COIL_Z0 + t * (COIL_Z1 - COIL_Z0)]);
  }
  return tubePieces(pts, 0.75, P, { maxLength: 3.2 });
})();

function burnerBlock() {
  const out = [];
  const F = G.frameOf([0, 0, BLOCK_Z], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
  out.push(S(G.disc(0, 1.2, 4.2, F, P), { tone: "mid" }));
  out.push(S(G.disc(1.2, 3.2, 3.2, F, P), { tone: "mid", inner: L(G.arcOf(F, 2.2, 3.2, P), { tone: "faint" }) }));
  out.push(D(G.dotsOf(F, 1.2, 3.7, 8, P, { all: true }), { size: 0.4 }));
  // Válvula de ráfaga: el cuerpo y la palanca que abre el paso de propano líquido.
  const vb = { x: 3.0, y: -1.4, w: 2.6, d: 2.8, r: 0.4 };
  out.push(S(k.slabOf(vb, BLOCK_Z + 0.4, 2.4, P, 2, 0.2), { tone: "mid" }));
  return out.join("");
}
function lever(open) {
  const a = -0.15 - open * 0.55;
  const base = [5.6, 0, BLOCK_Z + 1.6];
  const tip = [5.6 + Math.cos(a) * 7, 0, BLOCK_Z + 1.6 + Math.sin(a) * 7];
  return k.segment(base, tip, P);
}
function burnerCan() {
  const out = [];
  const F = G.frameOf([0, 0, BLOCK_Z + 3.2], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
  out.push(S(G.solidOf([[0, 2.6], [NOZZLE_Z - BLOCK_Z - 3.6, 2.6], [NOZZLE_Z - BLOCK_Z - 3.2, 2.2]], F, P), { tone: "hi", crease: "lo", inner: L(G.arcOf(F, 2.4, 2.6, P), { tone: "faint" }) }));
  // Corona de chorros: los orificios por los que sale el propano vaporizado.
  out.push(D(G.dotsOf(F, NOZZLE_Z - BLOCK_Z - 3.2, 1.5, 10, P, { all: true }), { size: 0.4, tone: "hi" }));
  return out.join("");
}
function pilot() {
  const out = [];
  const F = G.frameOf([-3.4, 2.4, BLOCK_Z + 3.2], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
  out.push(S(G.disc(0, 2.6, 0.6, F, P), { tone: "mid" }));
  out.push(S(G.disc(2.6, 3.4, 0.9, F, P), { tone: "mid" }));
  return out.join("");
}
const PILOT_AT = [-3.4, 2.4, BLOCK_Z + 6.8];

// ---------- Envoltura y cables de carga (se reconstruyen en la página mientras se infla) ----------
const UPRIGHT = [0, 0, MOUTH_Z];
const C = {
  R_EQ, R_MOUTH, S_EQ, DOME, R_CROWN, S_CROWN, GORES: 24, SEAMS: [18, 40, 62, 84, 110, 134, 156, 174], DH, LIE_D, WIRES: [],
};
const E0 = makeEnvelope(k, G, P, C);
{
  const F = E0.frameFor(Math.PI / 2, UPRIGHT);
  for (const [x, y] of k.corners(FRAME, 0.65)) {
    const base = Math.atan2(y, x);
    for (const da of [-0.2, 0.2]) {
      const dir = [Math.cos(base + da), Math.sin(base + da), 0];
      C.WIRES.push({ from: [x, y, FRAME_Z + FRAME_H + 0.9], phi: Math.atan2(G.dot3(dir, F.v), G.dot3(dir, F.u)) });
    }
  }
}
const E = makeEnvelope(k, G, P, C);
const START = { fill: 0.42, stand: 0 };
const first = E.pose(E.poseOf({ ...START, upright: UPRIGHT }));

// ---------- Llama de respaldo (sin WebGL) ----------
function flameFallback() {
  const F = G.frameOf([0, 0, NOZZLE_Z], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
  const prof = [];
  for (let i = 0; i <= 12; i++) {
    const x = i / 12;
    prof.push([x * 30, (1.6 + 4.2 * Math.sin(Math.PI * Math.pow(x, 0.7)) * (1 - x * 0.4)) * (x < 1 ? 1 : 0.0001), 1]);
  }
  const o = G.outlineOf(prof, F, P, { fill: "hull" });
  return `<path class="gb-fallback" data-part="fallback" d="${o.fill}"/>`;
}

// ---------- Montaje ----------
const coilBack = COIL.filter((p) => depth(p.mid) < depth([0, 0, p.mid[2]]));
const coilFront = COIL.filter((p) => depth(p.mid) >= depth([0, 0, p.mid[2]]));
const hoses = hosePieces();
const polesBack = POLES.filter(([x, y]) => depth([x, y, 0]) < depth([0, 0, 0]));
const polesFront = byDepth(POLES.filter(([x, y]) => depth([x, y, 0]) >= depth([0, 0, 0])), ([x, y]) => [x, y, 0]);

const balloonBack = [
  basketBack(),
  ...byDepth(polesBack, ([x, y]) => [x, y, 0]).map(pole),
  ...byDepth(CYL, ([x, y]) => [x, y, 0]).map(propane),
  ...byDepth(hoses, (p) => p.mid).map((p) => tubeSvg(p, { tone: "mid" })),
  basketFront(),
  ...polesFront.map(pole),
  frameBars(["y0", "x0", "mid"]),
  burnerBlock(),
  ...byDepth(coilBack, (p) => p.mid).map((p) => tubeSvg(p, { tone: "mid" })),
  burnerCan(),
  pilot(),
  ...byDepth(coilFront, (p) => p.mid).map((p) => tubeSvg(p, { tone: "mid" })),
  `<path data-part="lever" class="iso-line" data-tone="hi" d="${lever(0)}" style="stroke-width:1.4"/>`,
  D([at([5.6, 0, BLOCK_Z + 1.6])], { size: 0.6, tone: "hi" }),
  frameBars(["x1", "y1"]),
  ...byDepth(k.corners(FRAME, 0.65), ([x, y]) => [x, y, 0]).map(karabiner),
  `<g data-part="wires-back">${first.back}</g>`,
  flameFallback(),
].join("");

const balloonFront = `<g data-part="env">${first.front}</g>`;

const backSvg = k.figureSvg({
  width: W,
  height: H,
  className: "gb-back",
  label:
    "Un globo aerostático sobre una plataforma de despegue. Bajo la envoltura de 2550 metros cúbicos cuelga una cesta de mimbre con tres botellas de propano; sus mangueras suben a un quemador en espiral que lanza la llama hacia la boca. Arriba, en la corona, un panel de paracaídas puede bajarse para dejar salir aire caliente. Un mástil graduado marca la altitud.",
  body: [plate(), mast(), `<g data-part="carriage" transform="${k.translateAlong(P, [0, 0, FLOOR_Z])}">${carriage()}</g>`, `<g transform="${k.translateAlong(P, [B[0], B[1], 0])}"><path class="iso-halo gb-shadow" data-part="shadow" d="${k.haloOf({ x: -60, y: -60, w: 120, d: 120, r: 60 }, 0, 0.1, P)}"/>${fan()}</g>`, `<g data-part="balloon-back" transform="${k.translateAlong(P, [B[0], B[1], 0])}">${balloonBack}</g>`],
});
const frontSvg = `<svg xmlns="http://www.w3.org/2000/svg" class="iso-svg gb-layer gb-front" viewBox="0 0 ${W} ${H}" aria-hidden="true"><g data-part="balloon-front" transform="${k.translateAlong(P, [B[0], B[1], 0])}">${balloonFront}</g></svg>`;

const CSS = `
.gb-stage{position:relative;outline:none;touch-action:none;-webkit-user-select:none;user-select:none;cursor:pointer}
.gb-layer{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.gb-gl{display:block}
.gb-void{fill:var(--gb-void)}
.gb-fan-void{fill:var(--anatomy-shade-0);stroke:var(--anatomy-mid);stroke-width:var(--anatomy-weight)}
.gb-ring{fill:var(--anatomy-top);stroke:var(--anatomy-mid);stroke-width:var(--anatomy-weight)}
.gb-panel-face{fill:var(--anatomy-top);stroke:var(--anatomy-mid);stroke-width:var(--anatomy-weight)}
.gb-shadow{filter:blur(18px)}
.iso{--gb-void:#5b5650;--gb-warm:#f2a35e;--gb-flame:#ff9a2e}
.iso[data-theme="dark"]{--gb-void:#070707;--gb-warm:#7a3c12;--gb-flame:#ff8a1e}
.gb-env{
  --anatomy-shade-0:color-mix(in oklab,#dcdcd9,var(--gb-warm) calc(var(--heat,0)*30%));
  --anatomy-shade-1:color-mix(in oklab,#e5e5e2,var(--gb-warm) calc(var(--heat,0)*26%));
  --anatomy-shade-2:color-mix(in oklab,#ededea,var(--gb-warm) calc(var(--heat,0)*22%));
  --anatomy-shade-3:color-mix(in oklab,#f4f4f1,var(--gb-warm) calc(var(--heat,0)*18%));
  --anatomy-top:color-mix(in oklab,#ffffff,var(--gb-warm) calc(var(--heat,0)*14%));
}
.iso[data-theme="dark"] .gb-env{
  --anatomy-shade-0:color-mix(in oklab,#0f0f0f,var(--gb-warm) calc(var(--heat,0)*30%));
  --anatomy-shade-1:color-mix(in oklab,#121212,var(--gb-warm) calc(var(--heat,0)*30%));
  --anatomy-shade-2:color-mix(in oklab,#151515,var(--gb-warm) calc(var(--heat,0)*30%));
  --anatomy-shade-3:color-mix(in oklab,#181818,var(--gb-warm) calc(var(--heat,0)*30%));
  --anatomy-top:color-mix(in oklab,#1c1c1c,var(--gb-warm) calc(var(--heat,0)*30%));
}
.gb-fallback{fill:var(--gb-flame);opacity:0;mix-blend-mode:multiply}
.iso[data-theme="dark"] .gb-fallback{mix-blend-mode:screen}
.gb-stage[data-gl] .gb-fallback{display:none}
.gb-controls{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;padding:4px 0 14px}
.gb-btn{font:500 12px/1 var(--anatomy-mono);color:var(--anatomy-strong);background:var(--anatomy-card);border:1px solid var(--anatomy-faint);border-radius:999px;padding:9px 16px;cursor:pointer;touch-action:none;-webkit-user-select:none;user-select:none}
.gb-btn[data-on]{border-color:var(--anatomy-hi)}
`;

const DATA = {
  W, H, camera: glCamera(P), P,
  nozzle: NOZZLE_Z, pilot: PILOT_AT, mouth: MOUTH_Z, crownS: S_CROWN, ventDrop: VENT_DROP, B, C, upright: UPRIGHT, start: START, fanF: FAN_F,
  liftMax: LIFT_MAX, liftK: LIFT_K, floorZ: FLOOR_Z, blockZ: BLOCK_Z,
};

const latheSource = readFileSync(join(HERE, "skill", "kit", "lathe.mjs"), "utf8").replace(/^import .*$/m, "").replace(/^export /gm, "");
const model = readFileSync(join(HERE, "model.mjs"), "utf8").replace(/^export /gm, "") +
  `const G = (() => {${latheSource}\nreturn { viewOf, scaleOf, frameOf, frameAlong, pointOf, lathe, arcOf, circleOf, spokesOf, dotsOf, facingOf, fadeOf, radialOf, ringBand, unit3, cross3, add3, mul3, sub3, dot3 };})();\n` +
  readFileSync(join(HERE, "envelope.mjs"), "utf8").replace(/^export /gm, "");
const live = readFileSync(join(HERE, "live.js"), "utf8")
  .replace("__DATA__", JSON.stringify(DATA))
  .replace("/*__LEVER__*/", `const BLOCK_Z = ${BLOCK_Z}, P = D.P;\nconst leverAt = ${lever.toString().replace(/k\.segment/g, "segment")};`);

const stage = `<div class="gb-stage" tabindex="0" role="group" aria-label="Globo aerostático: mantén pulsado para encender el quemador; flecha abajo o V abre la válvula de paracaídas">${backSvg}<canvas class="gb-layer gb-gl" aria-hidden="true"></canvas>${frontSvg}</div>
<div class="gb-controls"><button class="gb-btn" type="button" data-hold="fan">Ventilador</button><button class="gb-btn" type="button" data-hold="burn">Quemador</button><button class="gb-btn" type="button" data-hold="vent">Válvula de paracaídas</button></div>`;

const s0 = M.initial();
const a0 = M.stateAt(s0);
const body = `<style>${CSS}</style>` + k.plateHtml({
  fig: "Fig 1",
  title: "Globo aerostático",
  hint: "Mantén pulsado un botón",
  readout: `${(s0.t - 273.15).toFixed(0)} °C · ${Math.round(a0.net)} N · 0 m`,
  keys: [
    { mark: "lit", label: "Llama del quemador: 3 MW que calientan el aire de dentro" },
    { mark: "raised", label: "Envoltura de 2550 m³; se tiñe al calentarse el aire" },
    { mark: "dim", label: "Corona: el paracaídas baja y deja escapar aire caliente" },
    { mark: "raised", label: "Ventilador de inflado: llena de aire frío la envoltura en el suelo" },
  ],
  caption:
    "Un globo flota porque el aire de dentro, más caliente, pesa menos que el aire frío que desplaza (Arquímedes). Con 556 kg a bordo, este globo de 2550 m³ necesita unos 77 °C dentro para quedarse quieto: más calor y sube, menos y baja. El quemador entrega 3 MW; la tela pierde unos 5,2 kW por cada grado de diferencia, y al tirar del paracaídas se abre un hueco de unos 3,5 m² en la corona por el que escapa de golpe el aire más caliente, unos 15 kg/s, y el globo se enfría varios grados por segundo. Antes de volar se infla: el ventilador mete unos 9,4 m³/s de aire frío en la envoltura tumbada y luego el quemador, apuntando a la boca, la calienta hasta que a unos 26 °C la tela se levanta sola. El tiempo corre 8 veces más rápido. Atmósfera estándar; cesta y quemador dibujados a 1,5× (en el inflado real la cesta va tumbada; aquí se deja de pie); la escala del mástil se comprime con la altura.",
  body: stage,
});

if (process.argv.includes("--artifact")) {
  const ART_CSS = `
:root{--gb-page:#f2f2ef}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--gb-page:#0b0b0b;color-scheme:dark}}
:root[data-theme="dark"]{--gb-page:#0b0b0b;color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--gb-page);padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
#gb-root{background:var(--anatomy-page);color:var(--anatomy-text);font:14px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
.iso-page{width:min(620px,100%);margin:0 auto;padding-block:32px 48px}
`;
  const sync = `(function(){var r=document.documentElement,w=document.getElementById("gb-root"),mq=matchMedia("(prefers-color-scheme: dark)");function f(){w.setAttribute("data-theme",r.getAttribute("data-theme")||(mq.matches?"dark":"light"))}f();mq.addEventListener("change",f);new MutationObserver(f).observe(r,{attributes:true,attributeFilter:["data-theme"]})})();`;
  const script = (kitScript() + glScript() + model + live).replace(/<\/(script)/gi, "<\\/$1");
  const html = `<title>Globo aerostático</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n<style>${k.ISO_CSS}${ART_CSS}</style>\n<div class="iso" id="gb-root" data-theme="light"><main class="iso-page">${body}</main></div>\n<script>${sync}</script>\n<script type="module">${script}</script>\n`;
  writeFileSync(join(OUT, "globo-aerostatico-artifact.html"), html);
  console.log("wrote", join(OUT, "globo-aerostatico-artifact.html"));
}

const name = theme === "light" ? "globo-aerostatico.html" : "globo-aerostatico-dark.html";
writeFileSync(join(OUT, name), k.pageHtml({ title: "Globo aerostático", theme, body, script: kitScript() + glScript() + model + live, width: 620 }).replace('<html lang="en">', '<html lang="es">'));
console.log("wrote", join(OUT, name));
