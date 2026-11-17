// La envoltura en cualquier postura: tumbada en el suelo, levantándose o de pie.
// La usan build.mjs (dibujo inicial) y la página (se reconstruye mientras se infla).

export function makeEnvelope(k, G, P, C) {
  const { R_EQ, R_MOUTH, S_EQ, DOME, R_CROWN, S_CROWN, GORES, SEAMS, DH, WIRES } = C;
  const radius = (s) => {
    if (s <= S_EQ) {
      const x = Math.max(0, s) / S_EQ;
      return R_MOUTH + (R_EQ - R_MOUTH) * (1 - (1 - x) ** 2);
    }
    const q = Math.min(1, (s - S_EQ) / DOME);
    return R_EQ * Math.sqrt(Math.max(0, 1 - q * q));
  };
  const slope = (s) => {
    if (s <= S_EQ) return ((R_EQ - R_MOUTH) * 2 * (1 - Math.max(0, s) / S_EQ)) / S_EQ;
    const q = Math.min(0.9999, (s - S_EQ) / DOME);
    return (-R_EQ * q) / (DOME * Math.sqrt(1 - q * q));
  };
  const view = G.viewOf(P);
  const side = [-DH[1], DH[0], 0];               // horizontal, perpendicular al eje: no cambia al levantarse
  const L = (d, style) => k.lineSvg(d, style);
  const D = (pts, style) => k.dotsSvg(pts, style);
  const at = (p) => k.iso(p, P);

  // Postura: inclinación del eje (0 = horizontal, π/2 = vertical) y escala de inflado del radio.
  function frameFor(theta, mouth) {
    const a = G.unit3([DH[0] * Math.cos(theta), DH[1] * Math.cos(theta), Math.sin(theta)]);
    const v = G.cross3(a, side);
    return G.frameOf(mouth, a, side, v);
  }
  // Altura mínima de la boca para que ningún punto de la tela quede bajo el suelo (z = 0).
  function seat(theta, scale, mouthXY, mouthZ) {
    let low = Infinity;
    for (let i = 0; i <= 40; i++) {
      const s = (S_CROWN * i) / 40;
      low = Math.min(low, mouthZ + s * Math.sin(theta) - scale * radius(s) * Math.cos(theta));
    }
    return low < 0.4 ? mouthZ + 0.4 - low : mouthZ;
  }

  function pose({ theta, scale, mouth }) {
    const F = frameFor(theta, mouth);
    const rad = (s) => scale * radius(s);
    const slp = (s) => scale * slope(s);
    const knots = [];
    for (let i = 0; i <= 48; i++) {
      const s = (S_CROWN * i) / 48;
      knots.push([s, rad(s), 1]);
    }
    const paths = G.lathe(knots, F, P, { smooth: { slope: slp, radius: rad }, rims: "all", steps: 72 });
    const seams = SEAMS.map((s) => G.arcOf(F, s, rad(s), P, { slope: slp(s) })).join("");
    const gores = [];
    for (let g = 0; g < GORES; g++) {
      const ang = (g / GORES) * Math.PI * 2 + 0.07;
      const steps = 36;
      for (let i = 0; i < steps; i++) {
        const s0 = (S_CROWN * i) / steps, s1 = (S_CROWN * (i + 1)) / steps, sm = (s0 + s1) / 2;
        const alpha = G.fadeOf(G.facingOf(F, ang, P, slp(sm)), [0.04, 0.4]);
        if (alpha < 0.02) continue;
        const pts = [s0, sm, s1].map((s) => at(G.pointOf(F, s, rad(s) + 0.05, ang)));
        gores.push({ d: `M${pts.map((p) => p.map((v) => v.toFixed(1)).join(" ")).join("L")}`, alpha });
      }
    }
    const env = `<g class="gb-env">${k.solidSvg(paths, { tone: "hi", inner: L(seams, { tone: "faint" }) + k.fadedSvg(gores, { tone: "lo" }) })}</g>`;

    // Corona con el paracaídas.
    const crownFaces = G.dot3(F.a, view) > 0.02;
    let crown = "";
    if (crownFaces) {
      const rc = rad(S_CROWN);
      const hole = G.circleOf(F, S_CROWN, rc, P, 96);
      const panel = G.circleOf(F, S_CROWN, rc + 2.4 * scale, P, 96);
      const spokes = G.spokesOf(F, S_CROWN, 3 * scale, rc + 2.4 * scale, 12, P, { phase: 0.13 });
      crown += `<clipPath id="gb-hole"><path d="${hole}"/></clipPath><g clip-path="url(#gb-hole)"><path class="gb-void" d="${hole}"/>`;
      crown += `<g data-part="vent"><path class="gb-panel-face" d="${panel}"/>${L(spokes, { tone: "lo" })}${L(G.circleOf(F, S_CROWN, 3 * scale, P, 24), { tone: "mid" })}</g></g>`;
      const outer = G.circleOf(F, S_CROWN + 0.6, rc + 0.3, P, 96);
      const innerRing = G.circleOf(F, S_CROWN + 0.6, rc - 1.6 * scale, P, 96);
      crown += `<path class="gb-ring" fill-rule="evenodd" d="${outer}${innerRing}"/>`;
      crown += D(G.dotsOf(F, S_CROWN + 0.6, rc - 0.65 * scale, GORES, P, { all: true, phase: 0.07 }), { size: 0.45 });
    }

    // Boca con su aro de cable. Si mira hacia nosotros se ve el interior oscuro.
    const rm = rad(0);
    const ring = k.solidSvg(G.ringBand(-1.2, 0.4, rm - 0.6, rm + 0.9, F, P), { tone: "mid" });
    const mouthFaces = -G.dot3(F.a, view) > 0.02;
    const voidMouth = mouthFaces ? `<path class="gb-void" d="${G.circleOf(F, -1.2, rm - 0.6, P, 72)}"/>` : "";

    // Cables de carga desde las esquinas del bastidor hasta la boca.
    const back = [], front = [];
    for (const w of WIRES) {
      const to = G.pointOf(F, 0, rm, w.phi);
      const facing = G.dot3(G.radialOf(F, w.phi), view);
      const svg = L(k.segment(w.from, to, P), { tone: "mid" }) + D([at(to)], { size: 0.5 });
      (facing < -0.15 ? back : front).push(svg);
    }
    const body = mouthFaces ? env + crown + voidMouth + ring : ring + env + crown;
    return { front: body + front.join(""), back: back.join(""), axis: F.a, mouth: mouth.slice() };
  }

  // Postura a partir del inflado (0..1 del volumen frío) y del levantamiento (0..1).
  function poseOf({ fill, stand, upright }) {
    const scale = Math.max(0.12, fill);
    const ease = stand * stand * (3 - 2 * stand);
    const lying = Math.atan2(scale * (R_EQ - R_MOUTH), S_EQ) * 0.9;
    const theta = lying + (Math.PI / 2 - lying) * ease;
    const m0 = [DH[0] * C.LIE_D, DH[1] * C.LIE_D, scale * R_MOUTH + 0.4];
    const mouthXY = [m0[0] + (upright[0] - m0[0]) * ease, m0[1] + (upright[1] - m0[1]) * ease];
    const mouthZ = m0[2] + (upright[2] - m0[2]) * ease;
    const mouth = [mouthXY[0], mouthXY[1], seat(theta, scale, mouthXY, mouthZ)];
    return { theta, scale, mouth };
  }

  return { pose, poseOf, radius, slope, frameFor };
}
