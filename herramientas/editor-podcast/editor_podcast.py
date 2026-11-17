"""
editor_podcast.py - Editor de videos de podcast que se maneja hablando con GPT.

Editas el video a partir de su transcripcion: GPT lee lo que se dice y,
cuando le pides algo ("quita los silencios", "borra la parte donde hablo del
tiempo", "hazme un clip vertical de la frase X"), llama a las funciones de este
programa, que cortan el video con ffmpeg.

Necesita:
  - Python 3.8 o mas nuevo (sin instalar paquetes).
  - ffmpeg instalado (ver LEEME.md).
  - Tu clave de OpenAI: se lee del .env de esta carpeta o, si no hay, del
    .env de ../chat-gpt. Nunca la escribas dentro de este archivo.

Uso:
    python editor_podcast.py                 -> chat con GPT
    python editor_podcast.py "video.mp4"     -> chat con GPT y abre ese video

Comandos dentro del chat:
    salir   -> cierra el programa
    nuevo   -> borra la conversacion (el proyecto del video se conserva)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
try:
    import estilos  # estilos de edicion (subtitulos animados, zoom, musica)
except ImportError:
    estilos = None
CARPETA_PROYECTOS = CARPETA / "proyectos"
URL_CHAT = "https://api.openai.com/v1/chat/completions"
URL_TRANSCRIBIR = "https://api.openai.com/v1/audio/transcriptions"

# Muletillas que se buscan por defecto (en minusculas, sin signos).
MULETILLAS = [
    "eh", "ehh", "ehhh", "em", "emm", "ehm", "mm", "mmm", "hmm", "ah", "ahh",
    "um", "umm", "uh", "uhm", "esto", "este", "o sea", "osea",
]
# De esas, las que pueden ser palabras normales: solo se quitan si se piden.
MULETILLAS_DUDOSAS = {"este", "esto", "o sea", "osea"}

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass


# --------------------------------------------------------------------------
# Configuracion
# --------------------------------------------------------------------------

def cargar_env():
    """Lee .env de esta carpeta y, si falta algo, el de ../chat-gpt."""
    for archivo in (CARPETA / ".env", CARPETA.parent / "chat-gpt" / ".env"):
        if not archivo.exists():
            continue
        for linea in archivo.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            nombre, valor = linea.split("=", 1)
            os.environ.setdefault(nombre.strip(), valor.strip().strip('"').strip("'"))


def ffmpeg_bin(nombre="ffmpeg"):
    """Ruta de ffmpeg/ffprobe: la de .env (FFMPEG=...) o la del PATH."""
    propio = os.environ.get("FFMPEG", "").strip()
    if propio:
        p = Path(propio)
        if p.is_dir():
            p = p / (nombre + (".exe" if os.name == "nt" else ""))
        elif nombre != "ffmpeg":
            p = p.with_name(p.name.replace("ffmpeg", nombre))
        if p.exists():
            return str(p)
    encontrado = shutil.which(nombre)
    if not encontrado and os.name == "nt":
        # instalado con winget pero el PATH aun no se ha refrescado
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet"
        for p in [base / "Links" / f"{nombre}.exe", *sorted(base.glob(f"Packages/*FFmpeg*/**/bin/{nombre}.exe"))]:
            if p.exists():
                encontrado = str(p)
                break
    if not encontrado:
        raise RuntimeError(
            f"No encuentro {nombre}. Abre PowerShell y ejecuta:  winget install Gyan.FFmpeg\n"
            "(o pon su ruta en un .env de esta carpeta "
            "con FFMPEG=C:\\ruta\\a\\ffmpeg.exe). Mira LEEME.md."
        )
    return encontrado


def ejecutar(args, cwd=None):
    r = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        cola = "\n".join(r.stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"ffmpeg fallo:\n{cola}")
    return r


# --------------------------------------------------------------------------
# Utilidades de texto y tiempo
# --------------------------------------------------------------------------

def normalizar(texto):
    """minusculas, sin tildes ni signos: 'Ehm,' -> 'ehm'."""
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w\s]", "", t).strip()


def hms(seg):
    seg = max(0.0, seg)
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}" if h else f"{int(m)}:{s:05.2f}"


def srt_tiempo(seg):
    ms = int(round(max(0.0, seg) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def unir_rangos(rangos):
    rangos = sorted((a, b) for a, b in rangos if b - a > 0.001)
    unidos = []
    for a, b in rangos:
        if unidos and a <= unidos[-1][1] + 0.001:
            unidos[-1][1] = max(unidos[-1][1], b)
        else:
            unidos.append([a, b])
    return unidos


# --------------------------------------------------------------------------
# Transcripcion con OpenAI (whisper-1, con tiempos por palabra)
# --------------------------------------------------------------------------

def _multipart(campos, archivo_campo, archivo_ruta):
    limite = "----editorpodcast" + uuid.uuid4().hex
    partes = []
    for nombre, valor in campos:
        partes.append(
            f'--{limite}\r\nContent-Disposition: form-data; name="{nombre}"\r\n\r\n{valor}\r\n'.encode("utf-8")
        )
    partes.append(
        (f'--{limite}\r\nContent-Disposition: form-data; name="{archivo_campo}"; '
         f'filename="{Path(archivo_ruta).name}"\r\nContent-Type: audio/mpeg\r\n\r\n').encode("utf-8")
    )
    partes.append(Path(archivo_ruta).read_bytes())
    partes.append(f"\r\n--{limite}--\r\n".encode("utf-8"))
    return b"".join(partes), "multipart/form-data; boundary=" + limite


def _peticion(url, cuerpo, tipo, clave, timeout=600):
    req = urllib.request.Request(
        url, data=cuerpo,
        headers={"Authorization": "Bearer " + clave, "Content-Type": tipo},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", errors="replace")
        try:
            detalle = json.loads(detalle)["error"]["message"]
        except Exception:
            pass
        ayuda = {
            401: "La clave no es valida. Revisa el archivo .env.",
            429: "Sin saldo o demasiadas peticiones. Revisa 'Billing' en platform.openai.com.",
            404: "Ese modelo no existe o no tienes acceso. Cambia OPENAI_MODEL en .env.",
        }.get(e.code, "")
        raise RuntimeError(f"Error {e.code}: {detalle}\n{ayuda}".strip())
    except urllib.error.URLError as e:
        raise RuntimeError(f"No hay conexion con OpenAI: {e.reason}")


ARCHIVO_GLOSARIO = CARPETA / "glosario.txt"
PROMPT_MULETILLAS = "Ehm, bueno... eh, o sea, mmm, la verdad es que, este, pues sí."


def prompt_transcripcion():
    """Muletillas + nombres del glosario: ayuda a Whisper a escribirlos bien."""
    glosario = ARCHIVO_GLOSARIO.read_text(encoding="utf-8").strip() if ARCHIVO_GLOSARIO.exists() else ""
    glosario = " ".join(glosario.split())[:600]
    return (glosario + ". " if glosario else "") + PROMPT_MULETILLAS


def transcribir(audio_mp3, clave, idioma="es", offset=0.0):
    """Devuelve [{'w': palabra, 'start': s, 'end': s}] con tiempos absolutos."""
    campos = [
        ("model", "whisper-1"),
        ("response_format", "verbose_json"),
        ("timestamp_granularities[]", "word"),
        ("timestamp_granularities[]", "segment"),
        # Este texto anima a Whisper a escribir las muletillas en vez de omitirlas.
        ("prompt", prompt_transcripcion()),
    ]
    if idioma:
        campos.append(("language", idioma))
    cuerpo, tipo = _multipart(campos, "file", audio_mp3)
    datos = _peticion(URL_TRANSCRIBIR, cuerpo, tipo, clave)
    palabras = [
        {"w": p["word"].strip(), "start": round(p["start"] + offset, 3), "end": round(p["end"] + offset, 3)}
        for p in datos.get("words", []) if p.get("word", "").strip()
    ]
    # Whisper devuelve las palabras sin puntuacion; se la ponemos desde los segmentos.
    _poner_puntuacion(palabras, datos.get("segments", []), offset)
    return palabras


def _poner_puntuacion(palabras, segmentos, offset):
    i = 0
    for seg in segmentos:
        fin_seg = seg.get("end", 0) + offset
        tokens = seg.get("text", "").split()
        j = 0
        while i < len(palabras) and j < len(tokens) and palabras[i]["start"] <= fin_seg + 0.05:
            if normalizar(tokens[j]) == normalizar(palabras[i]["w"]) and normalizar(tokens[j]):
                palabras[i]["w"] = tokens[j]
                i += 1
                j += 1
            elif not normalizar(tokens[j]):
                j += 1
            else:
                # No coinciden (numeros, etc.): avanzamos el que vaya detras.
                i += 1
                j += 1


# --------------------------------------------------------------------------
# Proyecto: un video + su transcripcion + las ediciones
# --------------------------------------------------------------------------

class Proyecto:
    """Guarda todo en proyectos/<nombre>/proyecto.json."""

    def __init__(self, carpeta):
        self.carpeta = Path(carpeta)
        self.archivo = self.carpeta / "proyecto.json"
        d = json.loads(self.archivo.read_text(encoding="utf-8"))
        self.video = d["video"]
        self.duracion = d["duracion"]
        self.tiene_video = d.get("tiene_video", True)
        self.palabras = d["palabras"]
        self.borradas = set(d.get("borradas", []))
        self.cortes_silencio = d.get("cortes_silencio", [])
        self.historial = d.get("historial", [])

    # ---- guardar / deshacer ----
    def _estado(self):
        return {"borradas": sorted(self.borradas), "cortes_silencio": self.cortes_silencio}

    def guardar(self):
        d = {
            "video": self.video, "duracion": self.duracion, "tiene_video": self.tiene_video,
            "palabras": self.palabras, **self._estado(), "historial": self.historial[-50:],
        }
        self.archivo.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    def recordar(self, que, textos=None):
        """textos = {indice: texto_anterior} si la edicion cambia palabras."""
        self.historial.append({"que": que, "antes": self._estado(), "textos": textos or {}})

    def deshacer(self):
        if not self.historial:
            return "No hay nada que deshacer."
        ultimo = self.historial.pop()
        for i, texto in ultimo.get("textos", {}).items():
            self.palabras[int(i)]["w"] = texto
        self.borradas = set(ultimo["antes"]["borradas"])
        self.cortes_silencio = ultimo["antes"]["cortes_silencio"]
        self.guardar()
        return f"Deshecho: {ultimo['que']}."

    # ---- cortes ----
    def _rango_de_palabras(self, i, j):
        """Tramo de tiempo que ocupa el bloque de palabras i..j, repartiendo las pausas."""
        p = self.palabras
        a = p[i]["start"] if i == 0 else (p[i - 1]["end"] + p[i]["start"]) / 2
        b = self.duracion if j == len(p) - 1 else (p[j]["end"] + p[j + 1]["start"]) / 2
        if i == 0:
            a = min(a, 0.0) if p[0]["start"] < 0.3 else p[0]["start"] - 0.05
        return a, b

    def cortes(self):
        """Lista unida de tramos [a, b] que se quitan del video."""
        rangos = []
        i = 0
        n = len(self.palabras)
        while i < n:
            if i in self.borradas:
                j = i
                while j + 1 < n and (j + 1) in self.borradas:
                    j += 1
                rangos.append(self._rango_de_palabras(i, j))
                i = j + 1
            else:
                i += 1
        rangos += [tuple(c) for c in self.cortes_silencio]
        return unir_rangos(rangos)

    def duracion_final(self, cortes=None):
        cortes = self.cortes() if cortes is None else cortes
        return self.duracion - sum(b - a for a, b in cortes)

    def mapear(self, t, cortes):
        """Tiempo del original -> tiempo en el video editado."""
        quitado = 0.0
        for a, b in cortes:
            if t >= b:
                quitado += b - a
            elif t > a:
                return a - quitado
            else:
                break
        return t - quitado


def nombre_proyecto(video):
    base = re.sub(r"[^\w\-]+", "-", normalizar(Path(video).stem)).strip("-") or "video"
    return base[:60]


def info_medio(ruta):
    r = ejecutar([ffmpeg_bin("ffprobe"), "-v", "error", "-show_entries",
                  "format=duration:stream=codec_type", "-of", "json", str(ruta)])
    d = json.loads(r.stdout)
    dur = float(d["format"]["duration"])
    tiene_video = any(s.get("codec_type") == "video" for s in d.get("streams", []))
    return dur, tiene_video


def crear_proyecto(video, clave, idioma="es", avisar=print):
    video = Path(video.strip().strip('"')).expanduser().resolve()
    if not video.exists():
        raise RuntimeError(f"No existe el archivo: {video}")
    carpeta = CARPETA_PROYECTOS / nombre_proyecto(video)
    if (carpeta / "proyecto.json").exists():
        p = Proyecto(carpeta)
        if Path(p.video) == video:
            return p, False
        carpeta = carpeta.with_name(carpeta.name + "-" + datetime.now().strftime("%H%M%S"))
    carpeta.mkdir(parents=True, exist_ok=True)

    duracion, tiene_video = info_medio(video)
    avisar(f"  Extrayendo audio ({hms(duracion)})...")
    ff = ffmpeg_bin()
    # wav para detectar silencios, mp3 pequeno para enviar a transcribir
    ejecutar([ff, "-y", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
              str(carpeta / "audio.wav")])
    trozo = 20 * 60  # 20 min por envio (limite de OpenAI: 25 MB)
    palabras = []
    inicio = 0.0
    n = 0
    while inicio < duracion:
        mp3 = carpeta / f"trozo{n}.mp3"
        ejecutar([ff, "-y", "-v", "error", "-ss", str(inicio), "-t", str(trozo), "-i",
                  str(carpeta / "audio.wav"), "-b:a", "48k", str(mp3)])
        avisar(f"  Transcribiendo {hms(inicio)} - {hms(min(duracion, inicio + trozo))}...")
        palabras += transcribir(mp3, clave, idioma, offset=inicio)
        mp3.unlink(missing_ok=True)
        inicio += trozo
        n += 1
    if not palabras:
        raise RuntimeError("La transcripcion salio vacia. ¿El video tiene voz?")

    d = {"video": str(video), "duracion": duracion, "tiene_video": tiene_video,
         "palabras": palabras, "borradas": [], "cortes_silencio": [], "historial": []}
    (carpeta / "proyecto.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return Proyecto(carpeta), True


# --------------------------------------------------------------------------
# Silencios
# --------------------------------------------------------------------------

def detectar_silencios(proyecto, umbral_db=-35, minimo=0.6):
    wav = proyecto.carpeta / "audio.wav"
    if not wav.exists():
        ejecutar([ffmpeg_bin(), "-y", "-v", "error", "-i", proyecto.video, "-vn", "-ac", "1",
                  "-ar", "16000", str(wav)])
    r = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-i", str(wav), "-af",
         f"silencedetect=noise={umbral_db}dB:d={minimo}", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    silencios, inicio = [], None
    for linea in r.stderr.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", linea)
        if m:
            inicio = max(0.0, float(m.group(1)))
        m = re.search(r"silence_end: ([\d.]+)", linea)
        if m and inicio is not None:
            silencios.append((inicio, float(m.group(1))))
            inicio = None
    if inicio is not None:
        silencios.append((inicio, proyecto.duracion))
    return silencios


# --------------------------------------------------------------------------
# Exportar con ffmpeg
# --------------------------------------------------------------------------

def _escribir_srt(proyecto, cortes, ruta, desde=0.0, hasta=None, max_car=42, max_seg=3.0):
    hasta = proyecto.duracion if hasta is None else hasta
    base = proyecto.mapear(desde, cortes)
    lineas, actual = [], []
    for i, p in enumerate(proyecto.palabras):
        if i in proyecto.borradas or not p["w"] or p["start"] < desde or p["end"] > hasta + 0.01:
            continue
        ini = proyecto.mapear(p["start"], cortes) - base
        fin = proyecto.mapear(p["end"], cortes) - base
        if actual:
            texto = " ".join(x[0] for x in actual + [(p["w"], 0, 0)])
            if len(texto) > max_car or fin - actual[0][1] > max_seg:
                lineas.append(actual)
                actual = []
        actual.append((p["w"], ini, fin))
        if p["w"].endswith((".", "?", "!")):
            lineas.append(actual)
            actual = []
    if actual:
        lineas.append(actual)
    with open(ruta, "w", encoding="utf-8") as f:
        for k, l in enumerate(lineas, 1):
            fin = l[-1][2]
            if k < len(lineas):
                fin = min(fin + 0.3, lineas[k][0][1])
            f.write(f"{k}\n{srt_tiempo(l[0][1])} --> {srt_tiempo(fin)}\n{' '.join(x[0] for x in l)}\n\n")
    return len(lineas)


def _expresion_pts(cortes):
    """PTS nuevo = PTS - (tiempo quitado antes de este instante)."""
    if not cortes:
        return "PTS-STARTPTS"
    partes = [f"gte(T,{b:.3f})*{b - a:.3f}" for a, b in cortes]
    return "PTS-(" + "+".join(partes) + ")/TB"


def _expresion_select(cortes):
    if not cortes:
        return "1"
    return "not(" + "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in cortes) + ")"


def es_vertical(ruta):
    """True si el video se ve mas alto que ancho (teniendo en cuenta la rotacion del movil)."""
    try:
        r = ejecutar([ffmpeg_bin("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                      "stream=width,height:stream_tags=rotate:stream_side_data=rotation", "-of", "json", str(ruta)])
        st = json.loads(r.stdout)["streams"][0]
        w, h = st["width"], st["height"]
        rot = st.get("tags", {}).get("rotate") or next(
            (d.get("rotation") for d in st.get("side_data_list", []) if "rotation" in d), 0)
        if abs(int(float(rot))) % 180 == 90:
            w, h = h, w
        return h > w
    except Exception:
        return False


_OPCION_FILTRO = {}


def _opcion_filtro(ff):
    """ffmpeg 7+ usa '-/filter_complex archivo'; los antiguos, '-filter_complex_script'."""
    if ff not in _OPCION_FILTRO:
        r = subprocess.run([ff, "-version"], capture_output=True, text=True, errors="replace")
        m = re.search(r"version n?(\d+)\.", r.stdout)
        viejo = bool(m) and int(m.group(1)) < 7
        _OPCION_FILTRO[ff] = "-filter_complex_script" if viejo else "-/filter_complex"
    return _OPCION_FILTRO[ff]


def _palabras_editadas(proyecto, cortes, desde=0.0, hasta=None):
    hasta = proyecto.duracion if hasta is None else hasta
    base = proyecto.mapear(desde, cortes)
    return [(p["w"], proyecto.mapear(p["start"], cortes) - base, proyecto.mapear(p["end"], cortes) - base)
            for i, p in enumerate(proyecto.palabras)
            if i not in proyecto.borradas and p["w"] and p["start"] >= desde and p["end"] <= hasta + 0.01]


def renderizar(proyecto, salida, cortes, subtitulos="ninguno", normalizar_audio=True,
               vertical=False, borrador=False, srt_desde=0.0, srt_hasta=None, estilo=None):
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_bin()
    solo_audio = (not proyecto.tiene_video) or salida.suffix.lower() in (".mp3", ".m4a", ".wav")
    usar_estilo = estilo is not None and estilos is not None

    srt = None
    if subtitulos in ("srt", "quemados"):
        srt = salida.with_suffix(".srt")
        _escribir_srt(proyecto, cortes, srt, srt_desde, srt_hasta)

    # tamano del video de salida (para subtitulos y zoom con estilo)
    dims = None
    if not solo_audio and usar_estilo:
        if vertical:
            dims = (1080, 1920)
        else:
            dims = estilos.dimensiones(ffmpeg_bin("ffprobe"), proyecto.video)
            if dims and borrador:
                dims = (int(round(dims[0] * 480 / dims[1] / 2) * 2), 480)
            if dims:
                dims = (dims[0] // 2 * 2, dims[1] // 2 * 2)
    dur_final = proyecto.duracion - sum(b - a for a, b in cortes)
    if srt_hasta is not None:
        dur_final = proyecto.mapear(srt_hasta, cortes) - proyecto.mapear(srt_desde, cortes)

    pts = _expresion_pts(cortes)
    sel = _expresion_select(cortes)
    lufs = float(estilo["audio"].get("lufs", -16)) if usar_estilo else -16
    musica = None
    if usar_estilo and estilo["audio"].get("musica"):
        musica = estilos.CARPETA_MUSICA / estilo["audio"]["musica"]
        if not musica.exists():
            raise RuntimeError(f"No encuentro la musica {musica}")
    audio = f"[0:a]aselect='{sel}',asetpts='{pts}',aresample=async=1000,aresample=48000"
    grafo = []
    if musica:
        grafo.append(audio + "[voz]")
        grafo.append(estilos.filtro_musica("voz", "mezcla", 1, estilo["audio"], dur_final))
        audio = "[mezcla]anull"
    if normalizar_audio:
        audio += f",loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample=48000"
    audio += "[a]"
    grafo.append(audio)
    if not solo_audio:
        video = f"[0:v]select='{sel}',setpts='{pts}'"
        if vertical:
            video += ",crop='min(iw,ih*9/16)':ih,scale=1080:1920,setsar=1"
        elif borrador:
            video += ",scale=-2:480"
        if dims:
            video += f",scale={dims[0]}:{dims[1]},setsar=1"
            zoom = estilos.filtro_zoom("v0", "vz", dims[0], dims[1], estilo["zoom"],
                                       cortes if srt_hasta is None else [], dur_final)
            if zoom:
                grafo.append(video + "[v0]")
                grafo.append(zoom)
                video = "[vz]null"
        if subtitulos == "quemados" and dims:
            ass = salida.with_suffix(".ass")
            estilos.escribir_ass(_palabras_editadas(proyecto, cortes, srt_desde, srt_hasta), ass,
                                 dims[0], dims[1], estilo["subtitulos"])
            video += f",subtitles={ass.name}"
        elif srt is not None and subtitulos == "quemados":
            estilo = "FontName=Arial,FontSize=%d,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000," \
                     "BorderStyle=1,Outline=2,Shadow=0,MarginV=%d,Alignment=2" % (
                         (12, 90) if (vertical or es_vertical(proyecto.video)) else (20, 30))
            # ruta relativa + cwd = carpeta de salida: evita lios con "C:\" en el filtro
            video += f",subtitles={srt.name}:force_style='{estilo}'"
        video += "[v]"
        grafo.append(video)

    script = salida.with_name(salida.stem + "_filtro.txt")
    script.write_text(";\n".join(grafo), encoding="utf-8")
    args = [ff, "-y", "-v", "error", "-i", proyecto.video]
    if musica:
        args += ["-stream_loop", "-1", "-i", str(musica)]
    args += [_opcion_filtro(ff), script.name]
    if solo_audio:
        args += ["-map", "[a]"]
        if salida.suffix.lower() == ".mp3":
            args += ["-c:a", "libmp3lame", "-b:a", "192k"]
        elif salida.suffix.lower() == ".m4a":
            args += ["-c:a", "aac", "-b:a", "192k"]
    else:
        args += ["-map", "[v]", "-map", "[a]", "-fps_mode", "vfr",
                 "-c:v", "libx264", "-preset", "ultrafast" if borrador else "veryfast",
                 "-crf", "28" if borrador else "20", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    args.append(salida.name)
    try:
        ejecutar(args, cwd=str(salida.parent))
    finally:
        script.unlink(missing_ok=True)
        salida.with_suffix(".ass").unlink(missing_ok=True)
    return salida, srt


# --------------------------------------------------------------------------
# Herramientas que GPT puede llamar
# --------------------------------------------------------------------------

class Editor:
    def __init__(self, clave):
        self.clave = clave
        self.p = None
        ultimo = CARPETA_PROYECTOS / "ultimo.txt"
        if ultimo.exists():
            carpeta = Path(ultimo.read_text(encoding="utf-8").strip())
            if (carpeta / "proyecto.json").exists():
                self.p = Proyecto(carpeta)

    def _necesita(self):
        if self.p is None:
            raise RuntimeError("Primero abre un video con abrir_video.")
        return self.p

    def _resumen(self):
        p = self.p
        cortes = p.cortes()
        return (f"Video: {Path(p.video).name}. Duracion original {hms(p.duracion)}, "
                f"editada {hms(p.duracion_final(cortes))} ({len(cortes)} cortes, "
                f"{len(p.borradas)} palabras borradas, {len(p.cortes_silencio)} silencios recortados). "
                f"Palabras en la transcripcion: {len(p.palabras)} (indices 0 a {len(p.palabras) - 1}).")

    # ---- abrir ----
    def abrir_video(self, ruta, idioma="es"):
        self.p, nuevo = crear_proyecto(ruta, self.clave, idioma)
        CARPETA_PROYECTOS.mkdir(exist_ok=True)
        (CARPETA_PROYECTOS / "ultimo.txt").write_text(str(self.p.carpeta), encoding="utf-8")
        estado = "Transcrito y listo." if nuevo else "Ya estaba transcrito; retomo las ediciones guardadas."
        return estado + " " + self._resumen()

    def estado(self):
        self._necesita()
        return self._resumen()

    # ---- leer ----
    def ver_transcripcion(self, desde=0, cuantas=1500):
        p = self._necesita()
        desde = max(0, int(desde))
        hasta = min(len(p.palabras), desde + min(int(cuantas), 2500))
        cortes = p.cortes()
        lineas, linea = [], []
        for i in range(desde, hasta):
            w = p.palabras[i]
            if not linea:
                if cortes:
                    linea.append(f"[{i} | {hms(w['start'])} -> {hms(p.mapear(w['start'], cortes))}]")
                else:
                    linea.append(f"[{i} | {hms(w['start'])}]")
            if not w["w"]:
                continue
            linea.append(f"~~{w['w']}~~" if i in p.borradas else w["w"])
            if w["w"].endswith((".", "?", "!")) or len(linea) > 25:
                lineas.append(" ".join(linea))
                linea = []
        if linea:
            lineas.append(" ".join(linea))
        pie = f"\n(Mostradas {desde}-{hasta - 1} de {len(p.palabras)}. ~~x~~ = borrada."
        pie += " Tiempos: original -> en el video editado.)" if cortes else ")"
        return "\n".join(lineas) + pie

    def buscar(self, texto):
        p = self._necesita()
        objetivo = normalizar(texto).split()
        if not objetivo:
            return "Texto vacio."
        norm = [normalizar(w["w"]) for w in p.palabras]
        res = []
        for i in range(len(norm) - len(objetivo) + 1):
            if norm[i:i + len(objetivo)] == objetivo:
                j = i + len(objetivo) - 1
                ctx = " ".join(w["w"] for w in p.palabras[max(0, i - 6):j + 7])
                res.append(f"palabras {i}-{j} ({hms(p.palabras[i]['start'])}): ...{ctx}...")
        if not res:
            return f"No aparece '{texto}'. Prueba con menos palabras o mira ver_transcripcion."
        return f"{len(res)} resultado(s):\n" + "\n".join(res[:40])

    # ---- editar ----
    def borrar_palabras(self, desde, hasta):
        p = self._necesita()
        desde, hasta = int(desde), int(hasta)
        if not (0 <= desde <= hasta < len(p.palabras)):
            return f"Indices fuera de rango (0 a {len(p.palabras) - 1})."
        texto = " ".join(w["w"] for w in p.palabras[desde:hasta + 1])
        p.recordar(f"borrar palabras {desde}-{hasta}")
        p.borradas.update(range(desde, hasta + 1))
        p.guardar()
        corto = texto if len(texto) < 200 else texto[:90] + " [...] " + texto[-90:]
        return f"Borrado ({hms(p.palabras[desde]['start'])}): \"{corto}\". " + self._resumen()

    def borrar_tramos(self, tramos):
        """Varios cortes de una vez: [[desde, hasta], ...]."""
        p = self._necesita()
        n = len(p.palabras)
        validos, malos = [], []
        for t in tramos or []:
            try:
                a, b = int(t[0]), int(t[1])
            except (TypeError, ValueError, IndexError):
                malos.append(str(t))
                continue
            if 0 <= a <= b < n:
                validos.append((a, b))
            else:
                malos.append(f"{a}-{b}")
        if not validos:
            return f"Ningun tramo valido (indices 0 a {n - 1})."
        p.recordar(f"borrar {len(validos)} tramos")
        lineas = []
        for a, b in sorted(validos):
            p.borradas.update(range(a, b + 1))
            texto = " ".join(w["w"] for w in p.palabras[a:b + 1])
            if len(texto) > 120:
                texto = texto[:55] + " [...] " + texto[-55:]
            lineas.append(f"- {a}-{b} ({hms(p.palabras[a]['start'])}): {texto}")
        p.guardar()
        aviso = f"\nIgnorados (fuera de rango): {', '.join(malos)}" if malos else ""
        return "Borrado:\n" + "\n".join(lineas) + aviso + "\n" + self._resumen()

    def limpieza_basica(self, incluir_dudosas=False):
        """Muletillas + silencios en un paso."""
        a = self.quitar_muletillas(None, incluir_dudosas)
        ritmo = {}
        if estilos is not None:
            try:
                ritmo = estilos.cargar().get("ritmo", {})
            except RuntimeError:
                pass
        b = self.acortar_silencios(ritmo.get("pausa_max", 0.7), ritmo.get("dejar", 0.35))
        return a.split(" Video:")[0] + " " + b

    def corregir_texto(self, desde, hasta, texto):
        """Cambia lo escrito en las palabras desde..hasta (no toca el audio ni los cortes)."""
        p = self._necesita()
        desde, hasta = int(desde), int(hasta)
        if not (0 <= desde <= hasta < len(p.palabras)):
            return f"Indices fuera de rango (0 a {len(p.palabras) - 1})."
        antes = " ".join(w["w"] for w in p.palabras[desde:hasta + 1] if w["w"])
        p.recordar(f"corregir {desde}-{hasta}", {i: p.palabras[i]["w"] for i in range(desde, hasta + 1)})
        p.palabras[desde]["w"] = " ".join(str(texto).split())
        for i in range(desde + 1, hasta + 1):
            p.palabras[i]["w"] = ""
        p.guardar()
        return f"Corregido: \"{antes}\" -> \"{p.palabras[desde]['w']}\"."

    def corregir_varios(self, cambios):
        """cambios = [{"desde": i, "hasta": j, "texto": "..."}]: muchas correcciones de una vez."""
        p = self._necesita()
        previos, hechos, malos = {}, [], []
        for c in cambios or []:
            try:
                a, b, t = int(c["desde"]), int(c.get("hasta", c["desde"])), str(c["texto"])
            except (KeyError, TypeError, ValueError):
                malos.append(str(c))
                continue
            if not (0 <= a <= b < len(p.palabras)):
                malos.append(f"{a}-{b}")
                continue
            for i in range(a, b + 1):
                previos.setdefault(i, p.palabras[i]["w"])
            antes = " ".join(w["w"] for w in p.palabras[a:b + 1] if w["w"])
            p.palabras[a]["w"] = " ".join(t.split())
            for i in range(a + 1, b + 1):
                p.palabras[i]["w"] = ""
            hechos.append(f"- {a}-{b}: \"{antes}\" -> \"{p.palabras[a]['w']}\"")
        if not hechos:
            return "Ninguna correccion valida."
        p.historial.append({"que": f"{len(hechos)} correcciones", "antes": p._estado(), "textos": previos})
        p.guardar()
        aviso = f"\nIgnoradas: {', '.join(malos)}" if malos else ""
        return "Corregido:\n" + "\n".join(hechos) + aviso

    def reemplazar_en_todo(self, buscar, poner):
        """Cambia una palabra o frase mal transcrita en toda la transcripcion (p. ej. un nombre)."""
        p = self._necesita()
        objetivo = normalizar(buscar).split()
        if not objetivo:
            return "Texto vacio."
        idx = [i for i, w in enumerate(p.palabras) if w["w"]]
        norm = [normalizar(p.palabras[i]["w"]) for i in idx]
        cambios, k = [], 0
        while k <= len(norm) - len(objetivo):
            if norm[k:k + len(objetivo)] == objetivo:
                a, b = idx[k], idx[k + len(objetivo) - 1]
                final = re.search(r"[.,;:?!]+$", p.palabras[b]["w"])
                cambios.append({"desde": a, "hasta": b, "texto": poner + (final.group(0) if final else "")})
                k += len(objetivo)
            else:
                k += 1
        if not cambios:
            return f"No aparece '{buscar}'."
        r = self.corregir_varios(cambios)
        return f"Reemplazado {len(cambios)} vez/veces. " + r

    def guardar_glosario(self, texto):
        """Nombres propios, marcas y palabras tecnicas del podcast (sirve para transcribir mejor)."""
        ARCHIVO_GLOSARIO.write_text(str(texto).strip(), encoding="utf-8")
        return ("Glosario guardado. Se usara al transcribir videos nuevos; para lo ya transcrito, "
                "corrige con reemplazar_en_todo.")

    def ver_glosario(self):
        if not ARCHIVO_GLOSARIO.exists():
            return "No hay glosario todavia."
        return "Glosario:\n" + ARCHIVO_GLOSARIO.read_text(encoding="utf-8")

    def revision_final(self, desde=0, cuantas=2500):
        """El texto tal como queda + cada corte con lo que hay antes y despues, para revisarlo todo."""
        p = self._necesita()
        cortes = p.cortes()
        n = len(p.palabras)
        desde = max(0, int(desde))
        hasta = min(n, desde + min(int(cuantas), 4000))
        texto, linea = [], []
        for i in range(desde, hasta):
            w = p.palabras[i]
            if i in p.borradas or not w["w"]:
                continue
            if not linea:
                linea.append(f"[{hms(p.mapear(w['start'], cortes))}]")
            linea.append(w["w"])
            if w["w"].endswith((".", "?", "!")) or len(linea) > 30:
                texto.append(" ".join(linea))
                linea = []
        if linea:
            texto.append(" ".join(linea))

        def vecinas(i, paso, k=7):
            out = []
            while 0 <= i < n and len(out) < k:
                if i not in p.borradas and p.palabras[i]["w"]:
                    out.append(p.palabras[i]["w"])
                i += paso
            return out[::-1] if paso < 0 else out

        saltos, i = [], desde
        while i < hasta:
            if i in p.borradas:
                j = i
                while j + 1 < n and (j + 1) in p.borradas:
                    j += 1
                quitado = " ".join(w["w"] for w in p.palabras[i:j + 1] if w["w"])
                if len(quitado) > 90:
                    quitado = quitado[:40] + " [...] " + quitado[-40:]
                saltos.append(f"- [{hms(p.mapear(p.palabras[i]['start'], cortes))}] "
                              f"...{' '.join(vecinas(i - 1, -1))} || quitado: \"{quitado}\" || "
                              f"{' '.join(vecinas(j + 1, 1))}...")
                i = j + 1
            else:
                i += 1
        pie = (f"\n(Palabras {desde}-{hasta - 1} de {n}. Tiempos del video editado.)"
               if hasta < n or desde else "")
        return ("RESUMEN: " + self._resumen() +
                "\n\nTEXTO FINAL:\n" + "\n".join(texto) +
                f"\n\nCORTES DE TEXTO ({len(saltos)}) - comprueba que cada union se entiende:\n" +
                ("\n".join(saltos) or "(ninguno)") + pie)

    def restaurar_palabras(self, desde, hasta):
        p = self._necesita()
        p.recordar(f"restaurar palabras {desde}-{hasta}")
        p.borradas.difference_update(range(int(desde), int(hasta) + 1))
        p.guardar()
        return "Restaurado. " + self._resumen()

    def quitar_muletillas(self, extra=None, incluir_dudosas=False):
        p = self._necesita()
        lista = [m for m in MULETILLAS if incluir_dudosas or m not in MULETILLAS_DUDOSAS]
        lista += [normalizar(e) for e in (extra or []) if normalizar(e)]
        norm = [normalizar(w["w"]) for w in p.palabras]
        nuevas, cuenta = set(), {}
        for m in sorted(set(lista), key=lambda x: -len(x.split())):
            partes = m.split()
            for i in range(len(norm) - len(partes) + 1):
                if norm[i:i + len(partes)] == partes:
                    idx = set(range(i, i + len(partes)))
                    if not idx & (nuevas | p.borradas):
                        nuevas |= idx
                        cuenta[m] = cuenta.get(m, 0) + 1
        if not nuevas:
            return "No encontre muletillas de la lista."
        p.recordar(f"quitar {len(nuevas)} muletillas")
        p.borradas |= nuevas
        p.guardar()
        detalle = ", ".join(f"'{k}' x{v}" for k, v in sorted(cuenta.items(), key=lambda x: -x[1]))
        return f"Quitadas: {detalle}. " + self._resumen()

    def acortar_silencios(self, mas_largos_que=0.7, dejar=0.35, umbral_db=-35):
        p = self._necesita()
        mas_largos_que = max(float(mas_largos_que), float(dejar) + 0.05)
        silencios = detectar_silencios(p, umbral_db, mas_largos_que)
        mitad = float(dejar) / 2
        cortes = []
        for a, b in silencios:
            ca, cb = a + mitad, b - mitad
            if a <= 0.01:
                ca = 0.0   # silencio al principio: fuera entero menos lo que dejas
                cb = b - mitad
            if b >= p.duracion - 0.01:
                cb = p.duracion
            # no tocar si el tramo se come el centro de una palabra
            if any(ca < (w["start"] + w["end"]) / 2 < cb for w in p.palabras):
                continue
            if cb - ca > 0.05:
                cortes.append([round(ca, 3), round(cb, 3)])
        p.recordar(f"acortar {len(cortes)} silencios")
        p.cortes_silencio = cortes  # sustituye los de una pasada anterior
        p.guardar()
        ahorro = sum(b - a for a, b in cortes)
        return f"Recortados {len(cortes)} silencios (ahorro {ahorro:.1f} s). " + self._resumen()

    def quitar_recortes_de_silencio(self):
        p = self._necesita()
        p.recordar("quitar recortes de silencio")
        p.cortes_silencio = []
        p.guardar()
        return "Silencios restaurados. " + self._resumen()

    def deshacer(self):
        self._necesita()
        return self.p.deshacer() + " " + self._resumen()

    # ---- exportar ----
    def _carpeta_salida(self):
        return self.p.carpeta / "exportados"

    def _estilo(self, nombre=None):
        if estilos is None:
            return None
        if nombre in ("ninguno", "sin estilo"):
            return None
        return estilos.cargar(nombre)

    def exportar(self, formato="video", subtitulos="srt", normalizar_audio=True, borrador=False, nombre=None,
                 estilo=None):
        p = self._necesita()
        est = self._estilo(estilo)
        ext = {"video": ".mp4", "audio": ".mp3", "vertical": ".mp4"}.get(formato, ".mp4")
        base = nombre or (Path(p.video).stem + ("_borrador" if borrador else "_editado")
                          + ("_vertical" if formato == "vertical" else ""))
        salida = self._carpeta_salida() / (re.sub(r"[^\w\-]+", "_", base) + ext)
        print(f"  Exportando {salida.name}... (puede tardar)")
        cortes = p.cortes()
        archivo, srt = renderizar(p, salida, cortes, subtitulos, normalizar_audio,
                                  vertical=(formato == "vertical"), borrador=borrador, estilo=est)
        txt = salida.with_suffix(".txt")
        txt.write_text(" ".join(w["w"] for i, w in enumerate(p.palabras) if i not in p.borradas and w["w"]),
                       encoding="utf-8")
        abrir_carpeta(archivo.parent)
        extra = f" Subtitulos: {srt}." if srt and subtitulos == "srt" else ""
        return (f"Listo: {archivo} (duracion {hms(p.duracion_final(cortes))}).{extra} "
                f"Transcripcion final: {txt}.")

    def crear_clip(self, desde, hasta, vertical=True, subtitulos="quemados", nombre=None, estilo=None):
        p = self._necesita()
        est = self._estilo(estilo)
        desde, hasta = int(desde), int(hasta)
        if not (0 <= desde <= hasta < len(p.palabras)):
            return f"Indices fuera de rango (0 a {len(p.palabras) - 1})."
        a = max(0.0, p.palabras[desde]["start"] - 0.15)
        b = min(p.duracion, p.palabras[hasta]["end"] + 0.4)
        cortes = unir_rangos(p.cortes() + [(0.0, a), (b, p.duracion)])
        base = nombre or f"clip_{desde}-{hasta}"
        salida = self._carpeta_salida() / (re.sub(r"[^\w\-]+", "_", base) + ".mp4")
        print(f"  Creando clip {salida.name}...")
        archivo, _ = renderizar(p, salida, cortes, subtitulos, True, vertical=bool(vertical),
                                srt_desde=a, srt_hasta=b, estilo=est)
        abrir_carpeta(archivo.parent)
        return f"Clip listo: {archivo} ({hms(p.duracion_final(cortes))})."


def abrir_carpeta(carpeta):
    if os.environ.get("EDITOR_NO_ABRIR"):
        return
    try:
        if os.name == "nt":
            os.startfile(str(carpeta))  # noqa
    except Exception:
        pass


def _f(nombre, descripcion, props=None, requeridos=None):
    return {"type": "function", "function": {
        "name": nombre, "description": descripcion,
        "parameters": {"type": "object", "properties": props or {}, "required": requeridos or []},
    }}


ENTERO = {"type": "integer"}
HERRAMIENTAS = [
    _f("abrir_video", "Abre un video o audio del ordenador, lo transcribe (si no lo estaba) y lo deja listo para editar.",
       {"ruta": {"type": "string", "description": "Ruta completa del archivo"},
        "idioma": {"type": "string", "description": "Codigo ISO, por defecto es"}}, ["ruta"]),
    _f("estado", "Resumen del proyecto abierto: duraciones y cuantos cortes hay."),
    _f("ver_transcripcion", "Lee la transcripcion con el indice de palabra y el tiempo al principio de cada frase. "
       "Las borradas salen como ~~asi~~. Pagina con 'desde'.",
       {"desde": ENTERO, "cuantas": {"type": "integer", "description": "Por defecto 1500, maximo 2500"}}),
    _f("buscar", "Busca una frase en la transcripcion y devuelve los indices de palabra donde aparece.",
       {"texto": {"type": "string"}}, ["texto"]),
    _f("borrar_palabras", "Corta del video las palabras desde..hasta (ambas incluidas). Es como borrar ese texto.",
       {"desde": ENTERO, "hasta": ENTERO}, ["desde", "hasta"]),
    _f("borrar_tramos", "Varios cortes de una vez. tramos = [[desde, hasta], ...] con indices de palabra.",
       {"tramos": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}}}, ["tramos"]),
    _f("limpieza_basica", "Quita muletillas y acorta silencios en un solo paso."),
    _f("restaurar_palabras", "Vuelve a poner palabras borradas.", {"desde": ENTERO, "hasta": ENTERO}, ["desde", "hasta"]),
    _f("quitar_muletillas", "Borra muletillas (eh, ehm, mmm...). 'extra' anade otras; incluir_dudosas tambien quita "
       "'este', 'esto', 'o sea' (cuidado, pueden ser palabras normales).",
       {"extra": {"type": "array", "items": {"type": "string"}}, "incluir_dudosas": {"type": "boolean"}}),
    _f("acortar_silencios", "Acorta las pausas largas. Sustituye una pasada anterior.",
       {"mas_largos_que": {"type": "number", "description": "Segundos; por defecto 0.7"},
        "dejar": {"type": "number", "description": "Segundos de pausa que se dejan; por defecto 0.35"},
        "umbral_db": {"type": "number", "description": "Nivel de silencio en dB; por defecto -35 (sube a -30 si hay ruido de fondo)"}}),
    _f("quitar_recortes_de_silencio", "Anula el recorte de silencios."),
    _f("deshacer", "Deshace la ultima edicion."),
    _f("exportar", "Genera el archivo final en la carpeta exportados del proyecto y la abre.",
       {"formato": {"type": "string", "enum": ["video", "audio", "vertical"]},
        "subtitulos": {"type": "string", "enum": ["ninguno", "srt", "quemados"],
                       "description": "srt = archivo aparte; quemados = dentro de la imagen"},
        "normalizar_audio": {"type": "boolean", "description": "Volumen estandar de podcast (-16 LUFS). Por defecto si."},
        "borrador": {"type": "boolean", "description": "Rapido y en baja calidad, para revisar"},
        "nombre": {"type": "string"}}),
    _f("crear_clip", "Crea un clip corto (para redes) con las palabras desde..hasta, respetando las ediciones.",
       {"desde": ENTERO, "hasta": ENTERO, "vertical": {"type": "boolean", "description": "9:16, por defecto si"},
        "subtitulos": {"type": "string", "enum": ["ninguno", "srt", "quemados"]}, "nombre": {"type": "string"}},
       ["desde", "hasta"]),
]

INSTRUCCIONES = """Eres el editor de video de un podcast. Hablas en espanol, claro y breve.
Editas el video a traves de su transcripcion usando las herramientas:
- Si no hay video abierto, pide la ruta (en Windows: clic derecho en el archivo > Copiar como ruta) y usa abrir_video.
- Para cortar algo, localizalo con buscar o ver_transcripcion y usa borrar_palabras con los indices exactos.
  Antes de borrar un trozo grande (mas de ~40 palabras), di que vas a quitar y desde que frase hasta cual.
- "Limpiar" un podcast suele ser: quitar_muletillas + acortar_silencios. Revisa tambien frases repetidas,
  arranques en falso ("lo que, lo que quiero decir") y tomas falsas, y proponlas antes de borrarlas.
- Tras cada cambio di en una linea que hiciste y la duracion nueva.
- Para revisar, sugiere exportar con borrador=true. El final, en calidad normal.
- Tambien puedes proponer titulo, descripcion, capitulos con minutos (usa los tiempos de la transcripcion)
  y los mejores momentos para clips; los clips se hacen con crear_clip.
- Nunca inventes indices: leelos siempre de las herramientas."""


def ejecutar_herramienta(editor, nombre, argumentos):
    try:
        args = json.loads(argumentos or "{}")
        funcion = getattr(editor, nombre, None)
        if funcion is None or nombre.startswith("_"):
            return f"Herramienta desconocida: {nombre}"
        return str(funcion(**args))
    except TypeError as e:
        return f"Argumentos no validos para {nombre}: {e}"
    except RuntimeError as e:
        return f"Error: {e}"
    except Exception as e:  # que el chat no se caiga
        return f"Error inesperado en {nombre}: {type(e).__name__}: {e}"


def preguntar(mensajes, clave, modelo):
    cuerpo = json.dumps({"model": modelo, "messages": mensajes, "tools": HERRAMIENTAS}).encode("utf-8")
    datos = _peticion(URL_CHAT, cuerpo, "application/json", clave, timeout=180)
    return datos["choices"][0]["message"]


def turno(mensajes, editor, clave, modelo, max_pasos=15):
    """Envia, ejecuta las herramientas que pida GPT y repite hasta que conteste."""
    for _ in range(max_pasos):
        msg = preguntar(mensajes, clave, modelo)
        llamadas = msg.get("tool_calls") or []
        mensajes.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
        if not llamadas:
            return msg.get("content") or ""
        for ll in llamadas:
            nombre = ll["function"]["name"]
            print(f"  [{nombre}]")
            resultado = ejecutar_herramienta(editor, nombre, ll["function"].get("arguments"))
            mensajes.append({"role": "tool", "tool_call_id": ll["id"], "content": resultado[:12000]})
    return "(He parado: demasiados pasos seguidos. Dime como seguimos.)"


def main():
    cargar_env()
    clave = os.environ.get("OPENAI_API_KEY", "").strip()
    modelo = os.environ.get("OPENAI_MODEL", "gpt-5-mini").strip()
    if not clave or clave.startswith("pega-aqui"):
        print("Falta tu clave de OpenAI. Ponla en el .env de herramientas\\chat-gpt (mira su LEEME.md).")
        return 1
    try:
        ffmpeg_bin()
    except RuntimeError as e:
        print(e)
        return 1

    editor = Editor(clave)
    mensajes = [{"role": "system", "content": INSTRUCCIONES}]
    print(f"Editor de podcast con GPT ({modelo}). 'salir' para terminar, 'nuevo' para borrar la conversacion.")
    if editor.p:
        print("Proyecto abierto:", editor.estado())
    print()

    pendiente = None
    if len(sys.argv) > 1:
        pendiente = f'Abre este video: "{" ".join(sys.argv[1:])}" y dime de que va en dos lineas.'
    elif editor.p:
        mensajes.append({"role": "system", "content": "Proyecto abierto ahora: " + editor.estado()})

    while True:
        if pendiente:
            texto, pendiente = pendiente, None
            print("Tu:", texto)
        else:
            try:
                texto = input("Tu: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
        if not texto:
            continue
        if texto.lower() in ("salir", "exit", "quit"):
            break
        if texto.lower() == "nuevo":
            mensajes = mensajes[:1]
            print("(Conversacion borrada; el proyecto sigue abierto.)\n")
            continue
        antes = len(mensajes)
        mensajes.append({"role": "user", "content": texto})
        try:
            respuesta = turno(mensajes, editor, clave, modelo)
        except RuntimeError as e:
            print(e, "\n")
            del mensajes[antes:]
            continue
        print("GPT:", respuesta, "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
