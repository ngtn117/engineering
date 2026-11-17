# Editor de podcast con GPT

Editas el video de tu podcast **hablando con GPT**: el programa transcribe el video
y GPT lo corta borrando texto, quita muletillas y silencios, pone subtitulos y saca clips.
Esta hecho desde cero, inspirado en lo que hace Descript (edicion por transcripcion),
sin usar nada de su codigo.

## 1. Preparar (una sola vez)
1. **Python**: el mismo que usa `chat-gpt` (ya lo tienes).
2. **ffmpeg** (el motor que corta el video). Abre "Terminal" o "PowerShell" y escribe:
   `winget install Gyan.FFmpeg`
   Cierra la terminal al terminar. Si no funciona, descargalo de https://www.gyan.dev/ffmpeg/builds/,
   descomprimelo y pon en un archivo `.env` de esta carpeta la linea
   `FFMPEG=C:\ruta\a\ffmpeg\bin\ffmpeg.exe`
3. **Clave de OpenAI**: usa la del `.env` de `herramientas\chat-gpt`; no hace falta copiarla.

## 2. Usarlo
- **Arrastra el video encima de `abrir_editor.bat`** (o haz doble clic y luego pega la ruta).
- La primera vez lo transcribe (unos 0,006 USD por minuto de audio; 1 hora ≈ 0,36 USD).
- Luego pidele cosas a GPT, por ejemplo:
  - "limpia el podcast: quita muletillas y acorta los silencios"
  - "lee la transcripcion y dime que partes sobran"
  - "borra desde 'bueno, antes de empezar' hasta 'vamos al tema'"
  - "deshaz eso"
  - "exporta un borrador para revisarlo" / "exporta el final con subtitulos quemados"
  - "exporta solo el audio en mp3"
  - "dame titulo, descripcion y capitulos para YouTube"
  - "busca los 3 mejores momentos y hazme clips verticales con subtitulos"
- Los archivos salen en `proyectos\<nombre-del-video>\exportados\` (la carpeta se abre sola).
  Ademas del video tienes el `.srt` de subtitulos y un `.txt` con la transcripcion final.
- Si cierras el programa, al volver a abrirlo sigue el ultimo video con tus cortes guardados.
  El video original **nunca se modifica**.

## Que puede hacer GPT (herramientas)
| Herramienta | Que hace |
|---|---|
| `abrir_video` | Transcribe con tiempos por palabra (Whisper de OpenAI) |
| `ver_transcripcion`, `buscar` | Lee el texto con el numero de cada palabra |
| `borrar_palabras`, `restaurar_palabras` | Cortar / recuperar trozos borrando texto |
| `quitar_muletillas` | eh, ehm, mmm... (y "o sea", "este" si se lo pides) |
| `acortar_silencios` | Deja las pausas largas en ~0,35 s |
| `deshacer` | Deshace la ultima edicion |
| `exportar` | Video, audio mp3 o vertical; subtitulos aparte o quemados; volumen de podcast (-16 LUFS) |
| `crear_clip` | Clip corto (vertical 9:16) de una frase a otra |

## Si algo falla
- **"No encuentro ffmpeg"**: paso 2 de arriba; despues cierra y abre de nuevo el editor.
- **Cortes que se comen el principio de una palabra**: pide "deshaz" y que lo haga palabra a palabra,
  o "acorta silencios dejando 0.5".
- **Hay ruido de fondo y no detecta silencios**: "acorta silencios con umbral -30".
- **Errores 401 / 429 / 404**: igual que en `chat-gpt` (clave, saldo o modelo; mira su LEEME).
