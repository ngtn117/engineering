# Editor de podcast para ChatGPT

Con este programa **ChatGPT edita los videos de tu podcast** en tu ordenador. Tú le hablas
y él corta el video: quita las muletillas y los silencios, borra trozos a partir del texto,
pone subtítulos, normaliza el volumen y saca clips verticales para redes.

- Funciona con **ChatGPT Plus** y no necesita clave de API.
- Es gratis: la transcripción y los cortes se hacen en tu PC.
- Tus videos no se suben a ningún sitio. ChatGPT solo lee el texto de la transcripción.
- Tu video original nunca se modifica.

Necesitas Windows 10/11 y unos 2 GB libres.

---

## 1. Instalar (una sola vez)
1. Copia esta carpeta entera donde quieras, por ejemplo en `Documentos\editor-podcast`.
2. Haz doble clic en **`instalar.bat`**. Instala Python, ffmpeg, cloudflared, las librerías
   y el modelo de voz. Tarda entre 5 y 15 minutos.
   - Si Windows pregunta "¿Permitir cambios?", dile que sí.
   - Si al final te pide ejecutarlo otra vez, ciérralo y vuelve a hacer doble clic.

## 2. Arrancar el editor (cada vez que lo uses)
1. Copia tus videos en la carpeta **`videos`**.
2. Haz doble clic en **`iniciar.bat`**. Aparece una ventana con
   **"URL del conector para ChatGPT"**: una dirección que termina en `/mcp`.
   Ya queda copiada en el portapapeles.
3. **No cierres esa ventana** mientras edites. Si la cierras, se apaga el editor.

Además se abre sola en el navegador la **vista previa**: el video a la izquierda y la
transcripción a la derecha, con lo cortado tachado.
- Haz clic en una palabra y el video salta a ese momento.
- Con **"Ver como queda"** activado, al reproducir se salta lo cortado. Así ves la edición sin exportar.
- También puedes editar a mano: selecciona texto y pulsa **Cortar selección** o **Restaurar selección**.
- La vista se actualiza sola mientras ChatGPT edita.

## 3. Conectarlo a ChatGPT
Hazlo en **chatgpt.com, desde el navegador del PC** (en el móvil no funciona). Los nombres
de los menús de ChatGPT cambian a veces; busca algo parecido a esto:

1. Haz clic en tu nombre (abajo a la izquierda) y entra en **Configuración**.
   Luego ve a **Aplicaciones y conectores** (o "Conectores" / "Plugins") y entra en **Avanzado**.
2. Activa el **Modo desarrollador**.
3. Vuelve a Conectores y pulsa **Crear** (o "+").
   - Nombre: `Editor de podcast`
   - URL: pega la URL de la ventana negra (Ctrl+V).
   - Autenticación: **Sin autenticación**.
   - Marca "Confío en esta aplicación" y pulsa **Crear**.
4. Abre un chat nuevo. Pulsa **+**, luego **Más** y **Modo desarrollador**, y activa
   **Editor de podcast**. Hay que activarlo en cada chat nuevo.

## 4. Pedirle cosas
- **Todo de una vez:** "Abre el episodio 1 y hazme la edición completa tú solo: limpia, quita lo que
  sobre, expórtalo con subtítulos y dame título, descripción, capítulos y 3 clips".
- "¿Qué videos tengo?" y después "abre el episodio 1". La primera vez lo transcribe, y tarda
  más o menos lo que dura el video. ChatGPT te va diciendo cómo va.
- "Limpia el podcast: quita muletillas y silencios largos."
- "Lee la transcripción y dime qué partes sobran."
- "Borra desde 'antes de empezar' hasta 'vamos al tema'."
- "Deshaz eso."
- "Exporta un borrador para revisarlo." Cuando te guste: "exporta el final con subtítulos quemados".
- "Exporta solo el audio en mp3."
- "Dame título, descripción y capítulos para YouTube."
- "Hazme 3 clips verticales con los mejores momentos."

Los archivos salen en `proyectos\<nombre-del-video>\exportados\`, y la carpeta se abre sola.
ChatGPT te pedirá permiso antes de cada cambio. Puedes pulsar "Permitir siempre" en esta conversación.

---

## Que el texto salga bien escrito
La transcripción automática se equivoca a veces con nombres y palabras raras. ChatGPT las corrige
usando lo que sabe de tu podcast, y así los subtítulos salen bien. Para que acierte más:
- Trabaja dentro de un **Proyecto de ChatGPT** donde le hayas contado de qué va tu podcast,
  quiénes son los invitados y los nombres que salen.
- Dile al principio: "guarda en el glosario estos nombres: ...". Con eso los videos nuevos se
  transcriben mejor desde el principio.
- Antes de exportar el final, ChatGPT hace siempre una **revisión final**. Lee todo el texto
  como queda, comprueba que ningún corte deja una frase a medias y arregla lo que vea mal escrito.

## Imitar el estilo de otro podcast
1. Copia el video de referencia en la carpeta **`referencias`**. Si quieres música de fondo,
   copia el mp3 en la carpeta **`musica`**.
2. Dile a ChatGPT: "analiza la referencia X y crea un estilo igual que se llame 'mi estilo'".
   Él mide el ritmo de las pausas, el volumen, cada cuánto cambia el plano y si hay música.
   También mira fotogramas para copiar los subtítulos.
3. A partir de ahí, cada exportación usa ese estilo. Puedes pedirle cambios como
   "subtítulos más grandes", "en amarillo", "sin zoom" o "la música más baja".

Lo que el estilo **sí** imita:
- **Subtítulos:** fuente, tamaño, color, mayúsculas, palabra resaltada mientras se dice,
  posición y fondo.
- **Ritmo:** cuánto se recortan las pausas.
- **Zooms:** zooms de "punch-in" que alternan en los cortes, para dar dinamismo con una sola cámara.
- **Sonido:** volumen final, y música de fondo que baja sola cuando alguien habla.

Lo que **no** puede imitar:
- Transiciones animadas, efectos de sonido, gráficos o textos animados.
- Imágenes de apoyo (b-roll) y cambiar entre varias cámaras.
- Los colores del video.

Además, la música tienes que ponerla tú en la carpeta `musica`, porque el editor no la descarga.

## Cosas que hay que saber
- **Sin URL fija, la URL cambia cada vez que abres `iniciar.bat`**, y tienes que editar el
  conector en ChatGPT para pegar la nueva. Para evitarlo, mira "URL fija" más abajo.
- **El PC tiene que estar encendido** y con `iniciar.bat` abierto mientras ChatGPT edita.
- **La velocidad depende de tu PC.** Con un PC normal, un podcast de 40 minutos tarda
  entre 10 y 30 minutos en transcribirse con el modelo `small`. Solo se hace una vez por video.
  Exportarlo tarda entre 5 y 15 minutos. Si te parece lento, pon `MODELO_WHISPER=base` en `config.txt`:
  es más rápido, pero se equivoca más con las palabras.
- **ChatGPT no ve la imagen**, solo el texto con sus tiempos. Corta por lo que se dice.
- **OpenAI cambia estas funciones a menudo.** Si el modo desarrollador desaparece o ChatGPT dice
  que no puede usar acciones del conector, es una limitación de tu plan o de la versión de ChatGPT,
  no del editor.
- **La URL es secreta.** Lleva una clave larga dentro y, sin ella, nadie más puede usar tu editor.
  No la compartas. Para cambiarla, borra el archivo `.token`.

## URL fija (recomendado)
Al final de `instalar.bat` te pregunta si quieres una URL fija. Si dijiste que no, puedes hacerlo
cuando quieras con doble clic en **`configurar_url_fija.bat`**:
1. Se abre la página de ngrok. Crea una cuenta gratis (puedes entrar con Google).
2. Copia tu **Authtoken**, pégalo en la ventana negra y pulsa Enter.

Desde ese momento la URL del conector siempre es la misma. Creas el conector en ChatGPT una vez
y no lo vuelves a tocar.

## Si algo falla
- **"No encuentro ffmpeg" o "cloudflared"**: vuelve a ejecutar `instalar.bat`.
- **"No pude arrancar en el puerto 8765"**: ya tienes otra ventana del editor abierta.
- **ChatGPT dice que no puede conectar**: revisa que la ventana negra siga abierta y que
  la URL del conector sea la última que te dio.
- **Cortes que se comen el principio de una palabra**: pide "deshaz" y "acorta silencios dejando 0.5".
- **Hay ruido de fondo y no detecta silencios**: pide "acorta silencios con umbral -30".
