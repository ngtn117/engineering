# engineering

Indice de la carpeta. Cada proyecto vive en su propia carpeta con todo lo que necesita
(codigo, paginas .html y capturas), asi que puedes mover una carpeta entera sin romper nada.

## anatomy/ — figuras isometricas interactivas
| Carpeta | Que es | Abrir |
|---|---|---|
| `anatomy/globo-aerostatico/` | Globo aerostatico: envolvente, quemador y valvula | `globo-aerostatico.html` (o `-dark.html`) |
| `anatomy/motor-rotativo/` | Motor rotativo (Wankel) | `motor-rotativo.html` (o `-dark.html`) |

Dentro de cada una: `build.mjs` genera los .html a partir de `model.mjs` y los demas `.mjs/.js`;
`captura*.png` son capturas de la figura.

## juegos/
| Carpeta | Que es | Abrir |
|---|---|---|
| `juegos/pulso-prisma/` | Juego Pulso Prisma | `pulso-prisma.html` (las .png son capturas) |

## herramientas/ (solo en el ordenador)
| Carpeta | Que es | Abrir |
|---|---|---|
| `herramientas/chat-gpt/` | Chat con GPT desde la terminal | doble clic en `abrir_chat.bat` (ver su `LEEME.md`) |
| `herramientas/editor-podcast/` | Editor de videos de podcast manejado por GPT (corta por transcripcion, muletillas, silencios, subtitulos, clips) | arrastra el video sobre `abrir_editor.bat` (ver su `LEEME.md`) |
| `herramientas/editor-podcast-chatgpt/` | Mismo editor como conector para ChatGPT Plus (sin clave de API, transcripcion local, estilos de referencia). Para pasarselo a otra persona | `instalar.bat` y luego `iniciar.bat` (ver su `LEEME.md`) |

La clave de `.env` se queda solo en el ordenador; no se sube a los archivos del proyecto.

## skills/
- `skills/anatomy.zip` — la skill que genera las figuras de `anatomy/`.

## Convenciones
- Nombres en minusculas con guiones: `mi-proyecto/mi-proyecto.html`.
- Un proyecto nuevo = una carpeta nueva dentro de la categoria que toque
  (`anatomy/`, `juegos/`, `herramientas/`...). Si no encaja, crea una categoria nueva.
