"""
servidor.py - Conector para que ChatGPT edite videos de podcast en tu ordenador.

Arranca un servidor MCP en tu PC y lo publica en internet con un tunel
(cloudflared), para que ChatGPT (modo desarrollador) lo use como conector.
Todo se procesa en tu ordenador: la transcripcion es local y gratis
(faster-whisper), y los cortes los hace ffmpeg. No hace falta clave de API.

Uso normal: doble clic en iniciar.bat.
    python servidor.py                   -> servidor + tunel, muestra la URL para ChatGPT
    python servidor.py --sin-tunel       -> solo servidor local (pruebas)
    python servidor.py --descargar-modelo -> descarga el modelo de voz y sale
    python servidor.py --configurar-ngrok -> deja una URL fija con ngrok (gratis)
"""

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import estilos  # estilos de edicion y analisis de referencias
import motor  # el motor de edicion (cortes, silencios, subtitulos, exportar)
import vista  # vista previa en el navegador

CARPETA = Path(__file__).resolve().parent
CARPETA_VIDEOS = CARPETA / "videos"
PUERTO = int(os.environ.get("PUERTO", "8765"))
EXTENSIONES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".flac"}

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def cargar_config():
    """config.txt: lineas NOMBRE=valor (modelo de whisper, idioma, ngrok...)."""
    archivo = CARPETA / "config.txt"
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


cargar_config()
MODELO = os.environ.get("MODELO_WHISPER", "small")
IDIOMA = os.environ.get("IDIOMA", "es")


# --------------------------------------------------------------------------
# Transcripcion local con faster-whisper
# --------------------------------------------------------------------------

_modelo = None
_progreso = {"total": 0.0, "hecho": 0.0}


def cargar_modelo():
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel
        print(f"Cargando modelo de voz '{MODELO}' (la primera vez se descarga)...")
        _modelo = WhisperModel(MODELO, device="cpu", compute_type="int8",
                               download_root=str(CARPETA / "modelos"))
    return _modelo


def transcribir_local(audio, clave=None, idioma="es", offset=0.0):
    """Misma salida que motor.transcribir pero sin internet."""
    import numpy as np
    modelo = cargar_modelo()
    # decodificamos con ffmpeg (evita problemas de version de la libreria "av")
    crudo = subprocess.run([motor.ffmpeg_bin(), "-v", "error", "-i", str(audio), "-f", "s16le",
                            "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    muestras = np.frombuffer(crudo, np.int16).astype(np.float32) / 32768.0
    segmentos, _ = modelo.transcribe(
        muestras, language=idioma or None, word_timestamps=True, beam_size=5,
        vad_filter=False, condition_on_previous_text=False,
        # anima a escribir las muletillas en vez de omitirlas
        initial_prompt=motor.prompt_transcripcion(),
    )
    palabras = []
    for seg in segmentos:
        for w in seg.words or []:
            texto = w.word.strip()
            if texto:
                palabras.append({"w": texto, "start": round(w.start + offset, 3),
                                 "end": round(w.end + offset, 3)})
        _progreso["hecho"] = offset + seg.end
    return palabras


motor.transcribir = transcribir_local


# --------------------------------------------------------------------------
# Tareas largas en segundo plano (ChatGPT corta las llamadas que tardan mucho)
# --------------------------------------------------------------------------

class Tarea:
    def __init__(self):
        self.lock = threading.Lock()
        self.nombre = None
        self.inicio = 0.0
        self.resultado = None
        self.hilo = None

    def ocupada(self):
        return self.hilo is not None and self.hilo.is_alive()

    def lanzar(self, nombre, funcion):
        if self.ocupada():
            return f"Espera: todavia estoy con '{self.nombre}'. {self.describir()}"
        self.nombre, self.inicio, self.resultado = nombre, time.time(), None

        def correr():
            try:
                with editor_lock:
                    self.resultado = "Terminado: " + funcion()
            except Exception as e:
                traceback.print_exc()
                self.resultado = f"Fallo en '{nombre}': {e}"
            print(" ", self.resultado)

        self.hilo = threading.Thread(target=correr, daemon=True)
        self.hilo.start()
        return (f"Empezado '{nombre}' en segundo plano. Llama a estado dentro de un rato "
                "para ver como va (no repitas esta llamada).")

    def describir(self):
        if self.ocupada():
            seg = int(time.time() - self.inicio)
            extra = ""
            if self.nombre.startswith("transcribir") and _progreso["total"]:
                pct = min(99, int(100 * _progreso["hecho"] / _progreso["total"]))
                extra = f" Transcrito {pct}%."
            return f"En curso: '{self.nombre}' desde hace {seg // 60} min {seg % 60} s.{extra}"
        if self.resultado:
            return self.resultado
        return "No hay tareas en curso."


tarea = Tarea()
editor_lock = threading.Lock()
editor = motor.Editor(clave=None)


def ruta_video(nombre):
    """Acepta un nombre de la carpeta videos o una ruta dentro de la carpeta del usuario."""
    nombre = nombre.strip().strip('"')
    candidatos = [CARPETA_VIDEOS / nombre, Path(nombre)]
    for c in candidatos:
        try:
            c = c.expanduser().resolve()
        except OSError:
            continue
        if c.is_file():
            casa = Path.home().resolve()
            if c.is_relative_to(CARPETA_VIDEOS.resolve()) or c.is_relative_to(casa):
                return c
            raise RuntimeError("Solo puedo abrir archivos de tu carpeta de usuario.")
    # busqueda aproximada por nombre en la carpeta videos
    norm = motor.normalizar(Path(nombre).stem)
    for f in sorted(CARPETA_VIDEOS.glob("*")):
        if f.suffix.lower() in EXTENSIONES and norm and norm in motor.normalizar(f.stem):
            return f.resolve()
    raise RuntimeError(f"No encuentro '{nombre}'. Usa listar_videos para ver los disponibles.")


# --------------------------------------------------------------------------
# Servidor MCP
# --------------------------------------------------------------------------

INSTRUCCIONES = """Eres el editor de video de un podcast y trabajas con estas herramientas, que cortan
el video en el ordenador del usuario. Habla en espanol, claro y breve.
- Empieza con listar_videos. Para abrir uno usa abrir_video; si no estaba transcrito tarda
  (varios minutos por cada 10 de video): avisa y consulta estado de vez en cuando.
- Para cortar, localiza el texto con buscar o ver_transcripcion y usa borrar_palabras con los
  indices exactos. Nunca inventes indices. Antes de borrar trozos grandes (mas de ~40 palabras),
  di que vas a quitar.
- "Limpiar" suele ser limpieza_basica (muletillas + silencios). Revisa tambien repeticiones,
  arranques en falso y tomas falsas.
- Si te piden la edicion completa o "hazlo todo tu", no preguntes en cada paso:
  1) limpieza_basica; 2) lee TODA la transcripcion con ver_transcripcion paginando hasta el final;
  3) decide los cortes de contenido (repeticiones, tomas falsas, divagaciones, silencios
  de tecnica, "se me corto", charla antes de empezar) y aplicalos juntos con borrar_tramos;
  4) corrige el texto mal transcrito (reemplazar_en_todo / corregir_varios);
  5) revision_final y arregla lo que falle; 6) exportar el final (con subtitulos quemados si hay
  estilo activo, si no srt) y espera con estado hasta que termine;
  7) da un resumen: duracion antes/despues, que quitaste, titulo, descripcion y capitulos con minutos
  del video editado (el segundo tiempo de ver_transcripcion, el que va despues de ->), y propone 3 clips.
  Respeta la duracion objetivo si la piden (por ejemplo "dejalo en 40 minutos").
- exportar y crear_clip trabajan en segundo plano: consulta estado hasta que diga Terminado.
  Sugiere un borrador para revisar y luego el final.
- Puedes proponer titulo, descripcion, capitulos con minutos y momentos para clips.

CONTEXTO Y CORRECCION DEL TEXTO
- Usa lo que sabes del proyecto y de la conversacion (tema del podcast, invitados, nombres, marcas,
  jerga). Al empezar, guarda esos nombres con guardar_glosario: mejora las transcripciones futuras.
- La transcripcion automatica se equivoca (nombres propios, palabras parecidas). Corrigela con
  reemplazar_en_todo (errores que se repiten) y corregir_varios (de una vez); eso arregla los
  subtitulos. No cambies lo que se dice: solo como esta escrito.

REVISION FINAL (obligatoria antes de exportar el video final)
- Llama a revision_final y lee todo: que cada union entre cortes se entienda y no corte frases a
  medias, que no quede ninguna muletilla o repeticion, y que el texto este bien escrito segun el
  contexto. Arregla lo que veas y vuelve a revisar si cambiaste mucho. Luego exporta.

ESTILOS DE REFERENCIA
- Si el usuario manda un podcast de referencia, pidele que lo copie en la carpeta 'referencias' y usa
  analizar_referencia. Mira los numeros y los fotogramas (tipo de subtitulos: fuente gruesa o fina,
  mayusculas, color, palabra resaltada, posicion, caja; encuadre y zooms) y crea un estilo con
  guardar_estilo + usar_estilo. Explica al usuario que imitaste y que no se puede imitar
  (transiciones animadas, efectos de sonido, graficos, b-roll, varias camaras, color).
- El estilo activo se aplica solo en limpieza_basica (ritmo) y al exportar con subtitulos quemados
  (subtitulos, zoom, musica, volumen). Musica: archivos de la carpeta 'musica' (ver_estilos)."""


def crear_servidor():
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations

    srv = MCPServer(name="Editor de podcast", instructions=INSTRUCCIONES)
    LEER = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
    EDITAR = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                             open_world_hint=False)

    def seguro(f):
        if not editor_lock.acquire(timeout=3):
            return "Espera, hay una tarea en curso. " + tarea.describir()
        try:
            return str(f())
        except RuntimeError as e:
            return f"Error: {e}"
        except Exception as e:
            traceback.print_exc()
            return f"Error inesperado: {type(e).__name__}: {e}"
        finally:
            editor_lock.release()

    @srv.tool(annotations=LEER)
    def listar_videos() -> str:
        """Lista los videos y audios de la carpeta 'videos' del editor y cual esta abierto."""
        CARPETA_VIDEOS.mkdir(exist_ok=True)
        archivos = [f for f in sorted(CARPETA_VIDEOS.iterdir()) if f.suffix.lower() in EXTENSIONES]
        transcritos = set()
        if motor.CARPETA_PROYECTOS.exists():
            for p in motor.CARPETA_PROYECTOS.glob("*/proyecto.json"):
                transcritos.add(p.parent.name)
        lineas = [f"- {f.name} ({f.stat().st_size / 1e6:.0f} MB)"
                  + (" [ya transcrito]" if motor.nombre_proyecto(f) in transcritos else "") for f in archivos]
        abierto = f"\nAbierto ahora: {Path(editor.p.video).name}" if editor.p else ""
        if not lineas:
            return f"La carpeta {CARPETA_VIDEOS} esta vacia. Pide al usuario que copie ahi sus videos." + abierto
        return "Videos en la carpeta:\n" + "\n".join(lineas) + abierto

    @srv.tool(annotations=EDITAR)
    def abrir_video(nombre: str) -> str:
        """Abre un video (nombre de la carpeta videos, o ruta completa) y lo transcribe si hace falta.
        La transcripcion va en segundo plano: luego consulta estado."""
        try:
            ruta = ruta_video(nombre)
        except RuntimeError as e:
            return f"Error: {e}"
        carpeta = motor.CARPETA_PROYECTOS / motor.nombre_proyecto(ruta)
        if (carpeta / "proyecto.json").exists():
            return seguro(lambda: editor.abrir_video(str(ruta), IDIOMA))
        dur, _ = motor.info_medio(ruta)
        _progreso.update(total=dur, hecho=0.0)
        return tarea.lanzar(f"transcribir {ruta.name}", lambda: editor.abrir_video(str(ruta), IDIOMA))

    @srv.tool(annotations=LEER)
    def estado() -> str:
        """Como va la tarea en segundo plano y resumen del proyecto abierto (duraciones, cortes)."""
        partes = [tarea.describir()]
        if editor.p and not tarea.ocupada():
            partes.append(seguro(editor.estado))
        partes.append(f"Vista previa para el usuario (abrela en su PC): {url_vista_local()}")
        return "\n".join(partes)

    @srv.tool(annotations=LEER)
    def ver_transcripcion(desde: int = 0, cuantas: int = 1500) -> str:
        """Lee la transcripcion con el indice de cada palabra y el tiempo de cada frase.
        Las borradas salen como ~~asi~~. Pagina con 'desde' (maximo 2500 por llamada;
        40 minutos de podcast son unas 6000 palabras)."""
        return seguro(lambda: editor.ver_transcripcion(desde, cuantas))

    @srv.tool(annotations=LEER)
    def buscar(texto: str) -> str:
        """Busca una frase y devuelve los indices de palabra donde aparece."""
        return seguro(lambda: editor.buscar(texto))

    @srv.tool(annotations=EDITAR)
    def borrar_palabras(desde: int, hasta: int) -> str:
        """Corta del video las palabras desde..hasta (incluidas), como borrar ese texto."""
        return seguro(lambda: editor.borrar_palabras(desde, hasta))

    @srv.tool(annotations=EDITAR)
    def borrar_tramos(tramos: list[list[int]]) -> str:
        """Varios cortes en una sola llamada: tramos = [[desde, hasta], ...] (indices de palabra,
        ambos incluidos). Usalo para aplicar todos los cortes de una revision de golpe."""
        return seguro(lambda: editor.borrar_tramos(tramos))

    @srv.tool(annotations=EDITAR)
    def limpieza_basica(incluir_dudosas: bool = False) -> str:
        """Quita muletillas y acorta silencios largos en un solo paso."""
        return seguro(lambda: editor.limpieza_basica(incluir_dudosas))

    @srv.tool(annotations=EDITAR)
    def corregir_varios(cambios: list[dict]) -> str:
        """Corrige como esta escrito el texto (y los subtitulos) sin tocar el audio.
        cambios = [{"desde": i, "hasta": j, "texto": "texto correcto"}, ...]. Las palabras
        desde..hasta se sustituyen por 'texto' (puede tener mas o menos palabras)."""
        return seguro(lambda: editor.corregir_varios(cambios))

    @srv.tool(annotations=EDITAR)
    def reemplazar_en_todo(buscar: str, poner: str) -> str:
        """Cambia una palabra o frase mal transcrita en toda la transcripcion (p. ej. 'estado de Adios'
        por 'estado de Hidalgo'). Solo cambia el texto, no el audio."""
        return seguro(lambda: editor.reemplazar_en_todo(buscar, poner))

    @srv.tool(annotations=EDITAR)
    def guardar_glosario(texto: str) -> str:
        """Guarda nombres propios, marcas y palabras tecnicas del podcast, separados por comas.
        Se usan para transcribir mejor los videos nuevos. Sustituye el glosario anterior."""
        return seguro(lambda: editor.guardar_glosario(texto))

    @srv.tool(annotations=LEER)
    def ver_glosario() -> str:
        """Muestra el glosario guardado."""
        return seguro(editor.ver_glosario)

    @srv.tool(annotations=LEER)
    def revision_final(desde: int = 0, cuantas: int = 2500) -> str:
        """Texto final tal como queda el video editado y cada corte con lo de antes y despues.
        Usalo siempre antes de exportar el video final. Pagina con 'desde' si el podcast es largo."""
        return seguro(lambda: editor.revision_final(desde, cuantas))

    @srv.tool(annotations=LEER)
    def analizar_referencia(nombre: str) -> list:
        """Analiza un podcast de referencia de la carpeta 'referencias' (o ruta completa): volumen,
        pausas, ritmo de cortes/zooms, musica de fondo, formato, y devuelve fotogramas para ver el
        estilo de subtitulos y encuadre."""
        from mcp.server.mcpserver.utilities.types import Image
        estilos.CARPETA_REFERENCIAS.mkdir(exist_ok=True)
        ruta = None
        for c in (estilos.CARPETA_REFERENCIAS / nombre, Path(nombre)):
            if c.is_file():
                ruta = c.resolve()
                break
        if ruta is None:
            norm = motor.normalizar(Path(nombre).stem)
            for f in sorted(estilos.CARPETA_REFERENCIAS.glob("*")):
                if f.suffix.lower() in EXTENSIONES and norm and norm in motor.normalizar(f.stem):
                    ruta = f.resolve()
                    break
        if ruta is None:
            hay = [f.name for f in estilos.CARPETA_REFERENCIAS.glob("*") if f.suffix.lower() in EXTENSIONES]
            return [f"No encuentro '{nombre}' en {estilos.CARPETA_REFERENCIAS}. Hay: {', '.join(hay) or 'nada'}"]
        if not (ruta.is_relative_to(estilos.CARPETA_REFERENCIAS.resolve()) or ruta.is_relative_to(Path.home().resolve())):
            return ["Error: solo puedo abrir archivos de tu carpeta de usuario."]
        try:
            texto, fotos = estilos.analizar(motor.ffmpeg_bin(), motor.ffmpeg_bin("ffprobe"), ruta,
                                            estilos.CARPETA_REFERENCIAS / "fotogramas")
        except Exception as e:
            return [f"Error analizando: {e}"]
        return [texto] + [Image(path=f) for f in fotos]

    @srv.tool(annotations=EDITAR)
    def guardar_estilo(nombre: str, estilo: dict) -> str:
        """Crea o actualiza un estilo de edicion. Solo pon lo que cambie; el resto queda por defecto.
        Claves: subtitulos {fuente, tamano (% de la altura), color "#RRGGBB", color_resaltado,
        resaltar_palabra (palabra que se dice en otro color), borde, color_borde, caja (fondo),
        posicion abajo|centro|arriba, margen (% altura), mayusculas, palabras_por_linea};
        ritmo {pausa_max, dejar} (segundos); zoom {modo no|cortes|tiempo, nivel (1.05-1.3), cada (s)};
        audio {lufs (-14 redes, -16 podcast), musica (archivo de la carpeta musica o ""),
        volumen_musica_db (-30 suave a -18 fuerte), bajar_musica_con_voz}.
        Fuentes seguras en Windows: Arial, Arial Black, Impact, Segoe UI, Verdana, Tahoma, Georgia."""
        def hacer():
            n, final = estilos.guardar(nombre, estilo)
            return f"Estilo '{n}' guardado: " + json.dumps(final, ensure_ascii=False)
        return seguro(hacer)

    @srv.tool(annotations=LEER)
    def ver_estilos() -> str:
        """Lista los estilos guardados, cual esta activo y la musica disponible."""
        return seguro(estilos.listar)

    @srv.tool(annotations=EDITAR)
    def usar_estilo(nombre: str) -> str:
        """Activa un estilo para las proximas exportaciones ('ninguno' para quitarlo)."""
        def hacer():
            n = estilos.activar(nombre)
            return f"Estilo activo: {n}." if n else "Sin estilo (subtitulos sencillos)."
        return seguro(hacer)

    @srv.tool(annotations=EDITAR)
    def restaurar_palabras(desde: int, hasta: int) -> str:
        """Vuelve a poner palabras borradas."""
        return seguro(lambda: editor.restaurar_palabras(desde, hasta))

    @srv.tool(annotations=EDITAR)
    def quitar_muletillas(extra: list[str] | None = None, incluir_dudosas: bool = False) -> str:
        """Borra muletillas (eh, ehm, mmm...). 'extra' anade otras palabras o frases.
        incluir_dudosas tambien quita 'este', 'esto', 'o sea' (pueden ser palabras normales)."""
        return seguro(lambda: editor.quitar_muletillas(extra, incluir_dudosas))

    @srv.tool(annotations=EDITAR)
    def acortar_silencios(mas_largos_que: float = 0.7, dejar: float = 0.35, umbral_db: float = -35) -> str:
        """Acorta las pausas mas largas que 'mas_largos_que' segundos, dejando 'dejar' segundos.
        Sube umbral_db a -30 si hay ruido de fondo. Sustituye una pasada anterior."""
        return seguro(lambda: editor.acortar_silencios(mas_largos_que, dejar, umbral_db))

    @srv.tool(annotations=EDITAR)
    def quitar_recortes_de_silencio() -> str:
        """Anula el recorte de silencios."""
        return seguro(editor.quitar_recortes_de_silencio)

    @srv.tool(annotations=EDITAR)
    def deshacer() -> str:
        """Deshace la ultima edicion."""
        return seguro(editor.deshacer)

    @srv.tool(annotations=EDITAR)
    def exportar(formato: str = "video", subtitulos: str = "srt", normalizar_audio: bool = True,
                 borrador: bool = False, nombre: str | None = None, estilo: str | None = None) -> str:
        """Genera el archivo final en la carpeta 'exportados' del proyecto (en segundo plano).
        formato: video | audio | vertical. subtitulos: ninguno | srt (archivo aparte) | quemados.
        normalizar_audio: volumen estandar de podcast. borrador: rapido y en baja calidad.
        estilo: nombre de un estilo guardado (si no, el activo). Antes del final, usa revision_final."""
        if editor.p is None:
            return "Error: primero abre un video."
        return tarea.lanzar(f"exportar {formato}", lambda: editor.exportar(
            formato, subtitulos, normalizar_audio, borrador, nombre, estilo))

    @srv.tool(annotations=EDITAR)
    def crear_clip(desde: int, hasta: int, vertical: bool = True, subtitulos: str = "quemados",
                   nombre: str | None = None, estilo: str | None = None) -> str:
        """Crea un clip corto para redes con las palabras desde..hasta (en segundo plano).
        desde y hasta son INDICES DE PALABRA (los numeros entre corchetes de ver_transcripcion),
        no segundos. Para un clip de 30-60 s suelen ser 80-160 palabras."""
        if editor.p is None:
            return "Error: primero abre un video."
        return tarea.lanzar(f"clip {desde}-{hasta}", lambda: editor.crear_clip(
            desde, hasta, vertical, subtitulos, nombre, estilo))

    return srv


def url_vista_local():
    return f"http://127.0.0.1:{PUERTO}/{token_secreto()}/vista"


def token_secreto():
    """Parte secreta de la URL: sin ella nadie mas puede usar tu editor."""
    archivo = CARPETA / ".token"
    if not archivo.exists():
        archivo.write_text(secrets.token_urlsafe(18), encoding="utf-8")
    return archivo.read_text(encoding="utf-8").strip()


def buscar_programa(nombre):
    encontrado = shutil.which(nombre)
    if encontrado:
        return encontrado
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet"
        for p in [base / "Links" / f"{nombre}.exe", *sorted(base.glob(f"Packages/*/**/{nombre}.exe")),
                  Path(os.environ.get("ProgramFiles(x86)", "")) / "cloudflared" / f"{nombre}.exe",
                  Path(os.environ.get("ProgramFiles", "")) / "cloudflared" / f"{nombre}.exe"]:
            if p.exists():
                return str(p)
    return None


def _url_ngrok(espera=25):
    """Pregunta a ngrok (su panel local en el puerto 4040) que URL publica tiene."""
    import urllib.request
    fin = time.time() + espera
    while time.time() < fin:
        try:
            with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=3) as r:
                for t in json.loads(r.read().decode("utf-8")).get("tunnels", []):
                    if t.get("public_url", "").startswith("https://"):
                        return t["public_url"]
        except Exception:
            pass
        time.sleep(1)
    return None


def abrir_tunel(ruta_mcp):
    """Lanza el tunel y devuelve la URL publica completa (o None).
    Con ngrok configurado la URL es siempre la misma; si no, cloudflared (cambia cada vez)."""
    dominio = os.environ.get("NGROK_DOMINIO", "").strip()
    if dominio or os.environ.get("TUNEL", "").strip().lower() == "ngrok":
        ngrok = buscar_programa("ngrok")
        if not ngrok:
            print("config.txt pide ngrok pero no lo encuentro. Ejecuta configurar_url_fija.bat.")
        else:
            args = [ngrok, "http", str(PUERTO), "--log=stdout"]
            if dominio:
                args.insert(3, f"--url={dominio}")
            proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            url = _url_ngrok()
            if url:
                return proc, url + ruta_mcp
            proc.terminate()
            print("ngrok no arranco (¿token mal puesto, o ngrok abierto en otra ventana?). Uso cloudflared.")

    cf = buscar_programa("cloudflared")
    if not cf:
        print("No encuentro cloudflared. Ejecuta instalar.bat otra vez.")
        return None, None
    for intento in range(3):
        proc, url = _cloudflared(cf, ruta_mcp)
        if url:
            return proc, url
        if proc:
            proc.terminate()
        print(f"  El tunel no respondio (intento {intento + 1} de 3). Reintentando...")
        time.sleep(3)
    print("El tunel no dio una direccion. Revisa tu conexion a internet y vuelve a abrir iniciar.bat.")
    return None, None


def _cloudflared(cf, ruta_mcp):
    log = open(CARPETA / "tunel.log", "w", encoding="utf-8")
    proc = subprocess.Popen([cf, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PUERTO}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace")
    fin = time.time() + 60
    while time.time() < fin:
        linea = proc.stdout.readline()
        if not linea:
            break
        log.write(linea)
        log.flush()
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", linea)
        if m:
            # sigue leyendo en segundo plano para que el tunel no se bloquee
            threading.Thread(target=lambda: [None for _ in proc.stdout], daemon=True).start()
            return proc, m.group(0) + ruta_mcp
    return proc, None


def configurar_ngrok():
    """Guia para dejar la URL fija: instala ngrok, guarda el token y lo apunta en config.txt."""
    print("\nURL FIJA CON NGROK (gratis)\n")
    print("1. Se abrira la pagina de ngrok. Crea una cuenta gratis (o entra con Google).")
    print("2. Copia tu 'Authtoken' (una clave larga) y pegala aqui.\n")
    try:
        import webbrowser
        webbrowser.open("https://dashboard.ngrok.com/get-started/your-authtoken")
    except Exception:
        pass
    token = input("Pega tu authtoken (o deja vacio y Enter para saltar): ").strip()
    if not token:
        print("Saltado. Puedes hacerlo luego con configurar_url_fija.bat.")
        return 0
    ngrok = buscar_programa("ngrok")
    if not ngrok and os.name == "nt":
        print("Instalando ngrok...")
        subprocess.run(["winget", "install", "-e", "--id", "Ngrok.Ngrok",
                        "--accept-source-agreements", "--accept-package-agreements"])
        ngrok = buscar_programa("ngrok")
    if not ngrok:
        print("No pude instalar ngrok. Descargalo de https://ngrok.com/download y vuelve a probar.")
        return 1
    r = subprocess.run([ngrok, "config", "add-authtoken", token], capture_output=True, text=True)
    if r.returncode != 0:
        print("ngrok no acepto el token:", (r.stderr or r.stdout).strip())
        return 1
    config = CARPETA / "config.txt"
    lineas = config.read_text(encoding="utf-8-sig").splitlines() if config.exists() else []
    lineas = [l for l in lineas if not l.strip().startswith("TUNEL=")] + ["TUNEL=ngrok"]
    config.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\nListo. Desde ahora la URL del conector sera siempre la misma.")
    print("La primera vez que abras iniciar.bat, crea el conector en ChatGPT con esa URL y ya no la cambies.")
    return 0


def copiar_portapapeles(texto):
    if os.name == "nt":
        try:
            subprocess.run("clip", input=texto.encode("utf-16-le"), check=False)
            return True
        except Exception:
            return False
    return False


def main():
    if "--descargar-modelo" in sys.argv:
        cargar_modelo()
        print("Modelo listo.")
        return 0
    if "--configurar-ngrok" in sys.argv:
        return configurar_ngrok()
    try:
        motor.ffmpeg_bin()
    except RuntimeError as e:
        print(e)
        return 1
    for c in (CARPETA_VIDEOS, estilos.CARPETA_REFERENCIAS, estilos.CARPETA_MUSICA, estilos.CARPETA_ESTILOS):
        c.mkdir(exist_ok=True)
    os.environ.setdefault("EDITOR_NO_ABRIR", "")

    import uvicorn
    from mcp.server.transport_security import TransportSecuritySettings

    ruta_mcp = f"/{token_secreto()}/mcp"
    app = crear_servidor().streamable_http_app(
        streamable_http_path=ruta_mcp, stateless_http=True, json_response=True,
        # el tunel llega con otro nombre de host; la proteccion la da el token de la URL
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    app.router.routes.extend(vista.rutas(token_secreto(), editor, editor_lock, tarea))
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PUERTO, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    time.sleep(1.5)
    if not hilo.is_alive():
        print(f"No pude arrancar en el puerto {PUERTO}. ¿Ya hay otra ventana del editor abierta?")
        return 1

    proc = None
    if "--sin-tunel" in sys.argv:
        url = f"http://127.0.0.1:{PUERTO}{ruta_mcp}"
    else:
        print("Abriendo el tunel a internet...")
        proc, url = abrir_tunel(ruta_mcp)
        if not url:
            servidor.should_exit = True
            return 1

    print("\n" + "=" * 70)
    print(" EDITOR DE PODCAST LISTO")
    print("=" * 70)
    print("\n URL del conector para ChatGPT:\n")
    print("   " + url + "\n")
    if copiar_portapapeles(url):
        print(" (Ya esta copiada: solo pegala en ChatGPT con Ctrl+V)")
    print(f"\n Vista previa (video + transcripcion): {url_vista_local()}")
    print(f"\n Pon tus videos en: {CARPETA_VIDEOS}")
    print(" No cierres esta ventana mientras uses el editor.\n" + "=" * 70 + "\n")
    if os.name == "nt" and "--sin-navegador" not in sys.argv:
        import webbrowser
        webbrowser.open(url_vista_local())
    try:
        while hilo.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        servidor.should_exit = True
        if proc:
            proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
