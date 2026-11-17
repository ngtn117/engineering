"""
estilos.py - Estilos de edicion (subtitulos, zooms, musica, ritmo) y analisis de
podcasts de referencia. Lo usa motor.py al exportar.

Un estilo es un JSON en la carpeta estilos/, por ejemplo:
{
  "subtitulos": {"fuente": "Arial Black", "tamano": 6.5, "color": "#FFFFFF",
                 "color_resaltado": "#FFD400", "resaltar_palabra": true,
                 "borde": 4, "color_borde": "#000000", "caja": false,
                 "posicion": "abajo", "margen": 12, "mayusculas": true,
                 "palabras_por_linea": 4},
  "ritmo": {"pausa_max": 0.6, "dejar": 0.3},
  "zoom": {"modo": "cortes", "nivel": 1.12, "cada": 4},
  "audio": {"lufs": -14, "musica": "lofi.mp3", "volumen_musica_db": -24, "bajar_musica_con_voz": true}
}
tamano y margen van en % de la altura del video.
"""

import json
import re
import statistics
import subprocess
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
CARPETA_ESTILOS = CARPETA / "estilos"
CARPETA_MUSICA = CARPETA / "musica"
CARPETA_REFERENCIAS = CARPETA / "referencias"
ACTIVO = CARPETA_ESTILOS / "_activo.txt"

POR_DEFECTO = {
    "subtitulos": {"fuente": "Arial", "tamano": 4.5, "color": "#FFFFFF", "color_resaltado": "#FFD400",
                   "resaltar_palabra": False, "borde": 3, "color_borde": "#000000", "caja": False,
                   "posicion": "abajo", "margen": 6, "mayusculas": False, "palabras_por_linea": 7},
    "ritmo": {"pausa_max": 0.7, "dejar": 0.35},
    "zoom": {"modo": "no", "nivel": 1.1, "cada": 5},
    "audio": {"lufs": -16, "musica": "", "volumen_musica_db": -24, "bajar_musica_con_voz": True},
}


# --------------------------------------------------------------------------
# Guardar / cargar
# --------------------------------------------------------------------------

def _mezclar(base, nuevo):
    out = json.loads(json.dumps(base))
    for k, v in (nuevo or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def nombre_valido(nombre):
    n = re.sub(r"[^\w\-]+", "-", (nombre or "").strip().lower()).strip("-")
    if not n:
        raise RuntimeError("Dale un nombre al estilo.")
    return n[:40]


def guardar(nombre, estilo):
    CARPETA_ESTILOS.mkdir(exist_ok=True)
    n = nombre_valido(nombre)
    archivo = CARPETA_ESTILOS / f"{n}.json"
    previo = json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else POR_DEFECTO
    final = _mezclar(previo, estilo)
    musica = final["audio"].get("musica")
    if musica and not (CARPETA_MUSICA / musica).exists():
        raise RuntimeError(f"No encuentro la musica '{musica}' en {CARPETA_MUSICA}. Mira ver_estilos.")
    archivo.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    return n, final


def cargar(nombre=None):
    """El estilo pedido, o el activo, o el de por defecto."""
    if not nombre and ACTIVO.exists():
        nombre = ACTIVO.read_text(encoding="utf-8").strip()
    if nombre:
        archivo = CARPETA_ESTILOS / f"{nombre_valido(nombre)}.json"
        if not archivo.exists():
            raise RuntimeError(f"No existe el estilo '{nombre}'. Mira ver_estilos.")
        return _mezclar(POR_DEFECTO, json.loads(archivo.read_text(encoding="utf-8")))
    return json.loads(json.dumps(POR_DEFECTO))


def activar(nombre):
    if nombre in (None, "", "ninguno"):
        ACTIVO.unlink(missing_ok=True)
        return None
    cargar(nombre)
    CARPETA_ESTILOS.mkdir(exist_ok=True)
    ACTIVO.write_text(nombre_valido(nombre), encoding="utf-8")
    return nombre_valido(nombre)


def listar():
    CARPETA_ESTILOS.mkdir(exist_ok=True)
    CARPETA_MUSICA.mkdir(exist_ok=True)
    activo = ACTIVO.read_text(encoding="utf-8").strip() if ACTIVO.exists() else ""
    estilos = sorted(p.stem for p in CARPETA_ESTILOS.glob("*.json"))
    musica = sorted(p.name for p in CARPETA_MUSICA.iterdir()
                    if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg", ".flac"))
    partes = ["Estilos guardados: " + (", ".join(
        f"{e}{' (activo)' if e == activo else ''}" for e in estilos) or "ninguno")]
    for e in estilos:
        partes.append(f"\n{e}: " + json.dumps(cargar(e), ensure_ascii=False))
    partes.append("\nMusica disponible (carpeta musica): " + (", ".join(musica) or "ninguna"))
    partes.append("\nValores por defecto: " + json.dumps(POR_DEFECTO, ensure_ascii=False))
    return "\n".join(partes)


# --------------------------------------------------------------------------
# Medidas de un video
# --------------------------------------------------------------------------

def dimensiones(ffprobe, ruta):
    """(ancho, alto) tal como se ve (con la rotacion del movil aplicada)."""
    r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:stream_tags=rotate:stream_side_data=rotation",
                        "-of", "json", str(ruta)], capture_output=True, text=True, errors="replace")
    try:
        st = json.loads(r.stdout)["streams"][0]
    except Exception:
        return None
    w, h = st["width"], st["height"]
    rot = st.get("tags", {}).get("rotate") or next(
        (d.get("rotation") for d in st.get("side_data_list", []) if "rotation" in d), 0)
    if abs(int(float(rot or 0))) % 180 == 90:
        w, h = h, w
    return w, h


def color_ass(hexa, alfa=0):
    h = (hexa or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    return f"&H{alfa:02X}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


# --------------------------------------------------------------------------
# Subtitulos .ass (con palabra resaltada tipo karaoke)
# --------------------------------------------------------------------------

def _t(seg):
    seg = max(0.0, seg)
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _limpiar(texto):
    return texto.replace("{", "(").replace("}", ")").replace("\\", "/")


def escribir_ass(palabras, ruta, ancho, alto, sub):
    """palabras = [(texto, inicio, fin)] ya en el tiempo del video editado."""
    tam = max(10, round(alto * float(sub.get("tamano", 4.5)) / 100))
    margen = round(alto * float(sub.get("margen", 6)) / 100)
    alin = {"abajo": 2, "centro": 5, "arriba": 8}.get(sub.get("posicion", "abajo"), 2)
    caja = bool(sub.get("caja"))
    estilo = (f"Style: Base,{sub.get('fuente', 'Arial')},{tam},{color_ass(sub.get('color'))},"
              f"{color_ass(sub.get('color_resaltado'))},{color_ass(sub.get('color_borde'))},"
              f"{color_ass(sub.get('color_borde'), 0x60) if caja else '&H64000000'},"
              f"-1,0,0,0,100,100,0,0,{3 if caja else 1},{sub.get('borde', 3)},"
              f"{0 if caja else 1},{alin},{round(ancho * 0.06)},{round(ancho * 0.06)},{margen},1")
    cab = ("[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
           f"PlayResX: {ancho}\nPlayResY: {alto}\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
           "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
           "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n" + estilo + "\n\n[Events]\n"
           "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

    por_linea = max(1, int(sub.get("palabras_por_linea", 7)))
    max_car = 14 * por_linea
    lineas, actual = [], []
    for w in palabras:
        if actual:
            texto = " ".join(x[0] for x in actual + [w])
            if (len(actual) >= por_linea or len(texto) > max_car or w[1] - actual[-1][2] > 1.0
                    or w[2] - actual[0][1] > 4.0):
                lineas.append(actual)
                actual = []
        actual.append(w)
        if w[0].endswith((".", "?", "!")):
            lineas.append(actual)
            actual = []
    if actual:
        lineas.append(actual)

    mayus = bool(sub.get("mayusculas"))
    resaltar = bool(sub.get("resaltar_palabra"))
    color_r = color_ass(sub.get("color_resaltado"))
    eventos = []
    for k, l in enumerate(lineas):
        fin_linea = l[-1][2] + 0.25
        if k + 1 < len(lineas):
            fin_linea = min(fin_linea, lineas[k + 1][0][1])
        textos = [_limpiar(x[0].upper() if mayus else x[0]) for x in l]
        if not resaltar:
            eventos.append((l[0][1], fin_linea, " ".join(textos)))
            continue
        for j, w in enumerate(l):
            ini = w[1] if j else l[0][1]
            fin = l[j + 1][1] if j + 1 < len(l) else fin_linea
            partes = [("{\\c" + color_r + "}" + t + "{\\r}") if n == j else t for n, t in enumerate(textos)]
            eventos.append((ini, max(fin, ini + 0.05), " ".join(partes)))
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(cab)
        for ini, fin, texto in eventos:
            f.write(f"Dialogue: 0,{_t(ini)},{_t(fin)},Base,,0,0,0,,{texto}\n")
    return len(lineas)


# --------------------------------------------------------------------------
# Filtros de video y audio
# --------------------------------------------------------------------------

def tramos_zoom(cortes, duracion, cada):
    """Tramos del video editado con zoom: alterna en los cortes, como minimo cada 'cada' s."""
    conservar, t = [], 0.0
    for a, b in cortes:
        if a > t:
            conservar.append((t, a))
        t = max(t, b)
    if t < duracion:
        conservar.append((t, duracion))
    limites, pos = [0.0], 0.0
    for a, b in conservar:
        pos += b - a
        limites.append(pos)
    tramos, ultimo, zoom = [], 0.0, False
    for lim in limites[1:-1] + [limites[-1]]:
        if lim - ultimo >= cada or lim == limites[-1]:
            if zoom:
                tramos.append((ultimo, lim))
            zoom = not zoom
            ultimo = lim
    return tramos


def filtro_zoom(entrada, salida, ancho, alto, zoom, cortes, duracion):
    nivel = float(zoom.get("nivel", 1.1))
    modo = zoom.get("modo", "no")
    if modo == "no" or nivel <= 1.0:
        return None
    cada = max(1.0, float(zoom.get("cada", 5)))
    if modo == "cortes":
        tramos = tramos_zoom(cortes, duracion, cada)
        if not tramos:
            return None
        cond = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in tramos)
    else:
        cond = f"mod(floor(t/{cada:.2f}),2)"
    zw = int(round(ancho * nivel / 2) * 2)
    zh = int(round(alto * nivel / 2) * 2)
    return (f"[{entrada}]split[zb][zz];[zz]scale={zw}:{zh},crop={ancho}:{alto}[zc];"
            f"[zb][zc]overlay=0:0:enable='{cond}'[{salida}]")


def filtro_musica(voz, salida, indice_entrada, audio, duracion_final):
    vol = float(audio.get("volumen_musica_db", -24))
    fade = min(3.0, duracion_final / 4)
    m = (f"[{indice_entrada}:a]aresample=48000,volume={vol}dB,"
         f"atrim=0:{duracion_final:.3f},afade=t=in:d=1,afade=t=out:st={max(0, duracion_final - fade):.3f}:d={fade:.3f}")
    if audio.get("bajar_musica_con_voz", True):
        return (f"{m}[mus];[{voz}]asplit[v1][v2];[mus][v2]sidechaincompress=threshold=0.03:ratio=6:"
                f"attack=30:release=500[mduck];[v1][mduck]amix=inputs=2:duration=first:normalize=0[{salida}]")
    return f"{m}[mus];[{voz}][mus]amix=inputs=2:duration=first:normalize=0[{salida}]"


# --------------------------------------------------------------------------
# Analisis de una referencia
# --------------------------------------------------------------------------

def _num(patron, texto, defecto=None):
    m = re.search(patron, texto)
    return float(m.group(1)) if m else defecto


def analizar(ffmpeg, ffprobe, ruta, carpeta_frames, n_frames=4):
    """Mide ritmo, volumen, cortes de camara y saca fotogramas. Devuelve (texto, [rutas jpg])."""
    ruta = Path(ruta)
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,r_frame_rate",
                        "-of", "json", str(ruta)], capture_output=True, text=True, errors="replace")
    info = json.loads(r.stdout or "{}")
    dur = float(info.get("format", {}).get("duration", 0) or 0)
    if dur <= 0:
        raise RuntimeError("No puedo leer ese archivo.")
    tiene_video = any(s.get("codec_type") == "video" for s in info.get("streams", []))
    lineas = [f"Referencia: {ruta.name} ({dur / 60:.1f} min)"]

    # Volumen y pausas
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", str(ruta), "-vn", "-af",
                        "silencedetect=noise=-35dB:d=0.2,ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace")
    err = r.stderr
    lufs = _num(r"I:\s+(-?[\d.]+) LUFS\s*\n\s*Threshold:[^\n]*\n\s*\n\s*Loudness range", err)
    if lufs is None:
        valores = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
        lufs = float(valores[-1]) if valores else None
    pausas = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", err)]
    habla = dur - sum(pausas)
    if lufs is not None:
        lineas.append(f"- Volumen integrado: {lufs:.1f} LUFS (YouTube/Spotify suelen ir a -14; -16 es podcast clasico).")
    if pausas:
        p = sorted(pausas)
        lineas.append(f"- Pausas (>0.2 s): {len(p)} en total, {60 * len(p) / dur:.1f} por minuto; "
                      f"mediana {statistics.median(p):.2f} s, larga (p90) {p[int(0.9 * (len(p) - 1))]:.2f} s, "
                      f"maxima {p[-1]:.2f} s. Habla el {100 * habla / dur:.0f}% del tiempo.")
        lineas.append(f"  -> para imitarlo: ritmo.pausa_max ~ {max(0.3, p[int(0.9 * (len(p) - 1))]):.2f}, "
                      f"ritmo.dejar ~ {max(0.15, min(0.6, statistics.median(p))):.2f}")
    else:
        lineas.append("- Casi no hay pausas por debajo de -35 dB: o hablan sin parar, o hay musica/ruido de fondo constante.")
    # Fondo: silencios a -50 dB (si casi no hay, hay musica o ruido de fondo)
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", str(ruta), "-vn", "-af",
                        "silencedetect=noise=-50dB:d=0.3", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace")
    pausas_50 = len(re.findall(r"silence_end", r.stderr))
    if len(pausas) > 10 and pausas_50 < len(pausas) * 0.15:
        lineas.append("- En las pausas nunca baja del todo el sonido: probablemente hay MUSICA DE FONDO "
                      "(o ruido). Escuchalo para confirmarlo.")
    else:
        lineas.append("- En las pausas el sonido baja casi a silencio: probablemente SIN musica de fondo.")

    rutas = []
    if tiene_video:
        # cambios de plano (cortes de camara o zooms bruscos)
        r = subprocess.run([ffmpeg, "-hide_banner", "-i", str(ruta), "-an", "-vf",
                            "fps=10,scale=160:-2,select='gt(scene,0.25)',showinfo", "-f", "null", "-"],
                           capture_output=True, text=True, errors="replace")
        cambios = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]
        lineas.append(f"- Cambios de plano / zooms bruscos: {len(cambios)} ({60 * len(cambios) / dur:.1f} por minuto"
                      + (f", uno cada {dur / len(cambios):.1f} s de media" if cambios else "") + ").")
        if cambios:
            lineas.append(f"  -> para imitarlo con una sola camara: zoom.modo 'cortes', zoom.cada ~ "
                          f"{max(2, min(15, dur / len(cambios))):.0f}")
        dims = dimensiones(ffprobe, ruta)
        if dims:
            w, h = dims
            lineas.append(f"- Formato: {w}x{h} ({'vertical' if h > w else 'horizontal'}).")
        carpeta_frames = Path(carpeta_frames)
        carpeta_frames.mkdir(parents=True, exist_ok=True)
        for k in range(n_frames):
            t = dur * (k + 1) / (n_frames + 1)
            salida = carpeta_frames / f"{ruta.stem[:30]}_{k + 1}.jpg"
            subprocess.run([ffmpeg, "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(ruta), "-frames:v", "1",
                            "-vf", "scale='if(gt(iw,ih),640,-2)':'if(gt(iw,ih),-2,640)'", "-q:v", "5", str(salida)],
                           capture_output=True)
            if salida.exists():
                rutas.append(salida)
        lineas.append(f"- Fotogramas de muestra: {len(rutas)} (mira en ellos el tipo de subtitulos: fuente, "
                      "mayusculas, colores, palabra resaltada, posicion, caja de fondo; y el encuadre/zoom).")
    lineas.append("\nNo se puede medir solo: efectos de sonido, transiciones animadas, graficos, b-roll, "
                  "cambio entre varias camaras y etalonaje de color.")
    return "\n".join(lineas), rutas
