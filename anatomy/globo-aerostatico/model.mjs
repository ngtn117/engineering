// Modelo físico de un globo de aire caliente de 2550 m³ (clase Cameron Z-90, 90 000 ft³).
// Todo lo que la figura mueve o escribe sale de aquí.

export const G0 = 9.80665;          // m/s²
export const R_AIR = 287.05;        // J/(kg·K), constante del aire seco
export const CP = 1005;             // J/(kg·K)
export const V = 2550;              // m³, volumen de la envoltura
export const MASS = {               // kg
  envoltura: 115,
  cesta: 65,
  quemador: 25,
  botellas: 111,                    // 3 × (18 kg de tara + 19 kg de propano)
  personas: 240,                    // piloto y dos pasajeros
};
export const M = Object.values(MASS).reduce((a, b) => a + b, 0); // 556 kg
export const BURNER_W = 3.0e6;      // W, un quemador simple a plena llama (~10 MBtu/h)
export const PROPANE_J = 46.35e6;   // J/kg, poder calorífico inferior del propano
export const UA = 5200;             // W/K, pérdida por la tela: ~320 kW a 62 K, lo que gasta un Z-90 en vuelo (≈25 kg/h de propano)
export const VENT_AREA = 3.5;       // m², hueco anular al bajar el paracaídas a fondo (~0,25 m en un borde de ~4,5 m)
export const CROWN_EXCESS = 1.25;   // el aire de la corona está más caliente que la media (estratificación)
export const VENT_CD = 0.6;
export const STACK_H = 17;          // m, altura de la columna caliente que empuja por la corona
export const AREA = Math.PI * 8.7 * 8.7; // m², sección frontal (8,7 m de radio en el ecuador)
export const CD = 0.5;
export const T_MAX = 120 + 273.15;  // K, límite de la tela (nailon con silicona)
export const ADDED = 0.5;           // masa añadida de una esfera, en fracciones del aire desplazado

// Atmósfera estándar internacional (troposfera).
export const ambientT = (z) => 288.15 - 0.0065 * z;
export const ambientP = (z) => 101325 * Math.pow(1 - 2.25577e-5 * z, 5.25588);
export const densityOf = (p, t) => p / (R_AIR * t);

// Temperatura interior a la que el globo flota en equilibrio a la altura z.
export function equilibriumT(z) {
  const p = ambientP(z), ta = ambientT(z);
  const need = M / V;                       // kg/m³ de diferencia de densidad
  const rhoIn = densityOf(p, ta) - need;
  return p / (R_AIR * rhoIn);
}

export function stateAt(s) {
  const p = ambientP(s.z), ta = ambientT(s.z);
  const rhoA = densityOf(p, ta), rhoI = densityOf(p, s.t);
  const buoyancy = V * G0 * rhoA;                 // Arquímedes: peso del aire desplazado
  const airWeight = V * G0 * rhoI;                // peso del aire caliente de dentro
  const weight = M * G0;
  const net = buoyancy - airWeight - weight;      // sustentación neta
  return { p, ta, rhoA, rhoI, buoyancy, airWeight, weight, net, mi: rhoI * V };
}

// Un paso de integración. burn y vent van de 0 a 1.
export function step(s, burn, vent, dt) {
  const a = stateAt(s);
  const dT = s.t - a.ta;
  const vStack = Math.sqrt(Math.max(0, 2 * G0 * STACK_H * (a.rhoA - a.rhoI) / a.rhoI));
  const mdotVent = a.rhoI * VENT_CD * VENT_AREA * vent * vStack;   // kg/s de aire caliente que sale por la corona
  const qBurn = BURNER_W * burn;
  const qLoss = UA * dT;
  const qVent = mdotVent * CP * dT * CROWN_EXCESS;
  s.t += (qBurn - qLoss - qVent) / (a.mi * CP) * dt;
  s.t = Math.max(a.ta, s.t);
  const mEff = M + a.mi + ADDED * a.rhoA * V;
  const drag = 0.5 * a.rhoA * CD * AREA * s.v * Math.abs(s.v);
  let force = a.net - drag;
  if (s.z <= 0 && force < 0 && s.v <= 0) { force = 0; s.v = 0; }  // apoyado en el suelo
  s.v += force / mEff * dt;
  s.z += s.v * dt;
  if (s.z < 0) { s.z = 0; s.v = Math.max(0, s.v); }
  s.fuel += qBurn / PROPANE_J * dt;
  s.qBurn = qBurn; s.qLoss = qLoss; s.qVent = qVent; s.mdotVent = mdotVent;
  return s;
}

export const initial = () => ({ z: 0, v: 0, t: equilibriumT(0) - 6, fuel: 0, qBurn: 0, qLoss: 0, qVent: 0, mdotVent: 0 });

// Inflado. Un ventilador de inflado típico mueve ~20 000 cfm (≈9,4 m³/s) de aire frío.
export const FAN_Q = 9.4;           // m³/s
export const SQUEEZE_Q = 12;        // m³/s, aire que sale al aplastar la tela al recoger
export const COLD_FILL = 0.85;      // fracción del radio que se alcanza solo con aire frío
// La envoltura se pone de pie cuando el aire caliente levanta su propio peso (115 kg de tela).
export function standT(z) {
  const p = ambientP(z), ta = ambientT(z);
  return p / (R_AIR * (densityOf(p, ta) - MASS.envoltura / V));
}
