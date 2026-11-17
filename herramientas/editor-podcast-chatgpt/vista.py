"""
vista.py - Vista previa en el navegador: el video y su transcripcion, con lo cortado tachado.

- Clic en una palabra: el video salta ahi.
- "Ver como queda": al reproducir se salta lo cortado (sin exportar).
- Selecciona texto y pulsa Cortar / Restaurar para editar a mano.
- Se actualiza sola cuando ChatGPT hace cambios.
"""

import hashlib
import json
import mimetypes
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Route


def rutas(prefijo, editor, editor_lock, tarea):
    """Devuelve las rutas de Starlette de la vista previa bajo /<prefijo>/vista."""

    def version():
        p = editor.p
        if p is None:
            return "vacio|" + tarea.describir()
        try:
            m = p.archivo.stat().st_mtime_ns
        except OSError:
            m = 0
        return hashlib.md5(f"{p.carpeta}|{m}|{tarea.describir()}".encode()).hexdigest()[:12]

    async def pagina(request: Request):
        return HTMLResponse(HTML.replace("__BASE__", f"/{prefijo}/vista"))

    async def datos(request: Request):
        v = version()
        if request.query_params.get("v") == v:
            return JSONResponse({"version": v, "igual": True})
        if not editor_lock.acquire(timeout=2):
            return JSONResponse({"version": "", "ocupado": True, "tarea": tarea.describir()})
        try:
            p = editor.p
            if p is None:
                return JSONResponse({"version": v, "vacio": True, "tarea": tarea.describir()})
            cortes = p.cortes()
            return JSONResponse({
                "version": v,
                "nombre": Path(p.video).name,
                "duracion": p.duracion,
                "duracion_final": p.duracion_final(cortes),
                "palabras": [[w["w"], w["start"], w["end"], 1 if i in p.borradas else 0]
                             for i, w in enumerate(p.palabras)],
                "cortes": cortes,
                "tarea": tarea.describir(),
            })
        finally:
            editor_lock.release()

    async def video(request: Request):
        p = editor.p
        if p is None or not Path(p.video).exists():
            return Response("Sin video", status_code=404)
        tipo = mimetypes.guess_type(p.video)[0] or "video/mp4"
        return FileResponse(p.video, media_type=tipo)

    async def editar(request: Request):
        try:
            d = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "msg": "Peticion no valida"}, status_code=400)
        if editor.p is None:
            return JSONResponse({"ok": False, "msg": "No hay video abierto"})
        if not editor_lock.acquire(timeout=2):
            return JSONResponse({"ok": False, "msg": "Espera, hay una tarea en curso"})
        try:
            accion = d.get("accion")
            if accion == "borrar":
                msg = editor.borrar_palabras(int(d["desde"]), int(d["hasta"]))
            elif accion == "restaurar":
                msg = editor.restaurar_palabras(int(d["desde"]), int(d["hasta"]))
            elif accion == "deshacer":
                msg = editor.deshacer()
            else:
                return JSONResponse({"ok": False, "msg": "Accion desconocida"}, status_code=400)
            return JSONResponse({"ok": True, "msg": msg.split(" Video:")[0]})
        except Exception as e:
            return JSONResponse({"ok": False, "msg": str(e)})
        finally:
            editor_lock.release()

    base = f"/{prefijo}/vista"
    return [
        Route(base, pagina),
        Route(base + "/datos", datos),
        Route(base + "/video", video),
        Route(base + "/editar", editar, methods=["POST"]),
    ]


HTML = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vista previa del podcast</title>
<style>
:root{--bg:#f6f5f2;--panel:#fff;--txt:#1d1d1f;--sub:#6b6b70;--borde:#e3e1dc;--acento:#d4501e;--cortado:#b8b6b0;--actual:#ffe28a}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--panel:#202020;--txt:#ececec;--sub:#9a9a9a;--borde:#333;--acento:#ff7a45;--cortado:#5c5c5c;--actual:#6b5512}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:16px/1.6 system-ui,Segoe UI,Arial,sans-serif}
header{padding:12px 20px;border-bottom:1px solid var(--borde);display:flex;gap:16px;align-items:baseline;flex-wrap:wrap}
h1{font-size:18px;margin:0}#info{color:var(--sub);font-size:14px}
main{display:grid;grid-template-columns:minmax(280px,42%) 1fr;gap:20px;padding:20px;height:calc(100vh - 56px)}
@media (max-width:800px){main{grid-template-columns:1fr;height:auto}}
#izq{display:flex;flex-direction:column;gap:12px}
video{width:100%;max-height:60vh;background:#000;border-radius:10px}
.barra{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
button{font:inherit;font-size:14px;padding:6px 12px;border-radius:8px;border:1px solid var(--borde);background:var(--panel);color:var(--txt);cursor:pointer}
button.prim{background:var(--acento);border-color:var(--acento);color:#fff}
button:disabled{opacity:.4;cursor:default}
label{font-size:14px;color:var(--sub);display:flex;gap:6px;align-items:center}
#msg{font-size:14px;color:var(--sub);min-height:1.4em}
#texto{background:var(--panel);border:1px solid var(--borde);border-radius:10px;padding:16px 20px;overflow:auto;user-select:text}
.f{margin:0 0 10px}.t{color:var(--sub);font-size:12px;margin-right:6px;user-select:none;cursor:pointer}
.w{cursor:pointer;border-radius:3px}.w:hover{background:var(--borde)}
.w.x{color:var(--cortado);text-decoration:line-through}
.w.ahora{background:var(--actual)}
#vacio{padding:40px;color:var(--sub)}
</style></head><body>
<header><h1 id="nombre">Vista previa</h1><span id="info"></span></header>
<main><section id="izq">
<video id="v" controls preload="metadata"></video>
<div class="barra">
 <label><input type="checkbox" id="saltar" checked> Ver como queda (salta lo cortado)</label>
</div>
<div class="barra">
 <button class="prim" id="bCortar" disabled>Cortar selección</button>
 <button id="bRest" disabled>Restaurar selección</button>
 <button id="bDesh">Deshacer</button>
</div>
<div id="msg">Selecciona texto para cortarlo o restaurarlo. Clic en una palabra para ir a ese momento.</div>
</section>
<section id="texto"><div id="vacio">Cargando...</div></section></main>
<script>
const BASE="__BASE__";let ver="",P=[],C=[],sel=null,nombre="";
const $=id=>document.getElementById(id),v=$("v");
function hms(s){s=Math.max(0,s);const m=Math.floor(s/60),x=(s%60).toFixed(0).padStart(2,"0");return m+":"+x}
async function cargar(){
 try{const r=await fetch(BASE+"/datos?v="+ver);const d=await r.json();
  if(d.igual||d.ocupado){if(d.tarea)$("info").textContent=d.tarea;return}
  ver=d.version;
  if(d.vacio){$("texto").innerHTML='<div id="vacio">Todavía no hay video abierto. Pídele a ChatGPT que abra uno.<br><br>'+(d.tarea||"")+"</div>";return}
  if(d.nombre!==nombre){nombre=d.nombre;v.src=BASE+"/video?n="+encodeURIComponent(nombre);$("nombre").textContent=nombre}
  P=d.palabras;C=d.cortes;
  $("info").textContent="Original "+hms(d.duracion)+" · editado "+hms(d.duracion_final)+" · "+C.length+" cortes"+(d.tarea&&d.tarea.startsWith("En curso")?" · "+d.tarea:"");
  pintar();
 }catch(e){$("info").textContent="Sin conexión con el editor (¿está abierta la ventana?)"}
}
function pintar(){
 const caja=$("texto"),y=caja.scrollTop;let h="",linea=[],n=0;
 const cerrar=()=>{if(linea.length){h+='<p class="f">'+linea.join(" ")+"</p>";linea=[]}};
 P.forEach((w,i)=>{if(!w[0])return;
  if(!linea.length)linea.push('<span class="t" data-i="'+i+'">'+hms(w[1])+"</span>");
  linea.push('<span class="w'+(w[3]?" x":"")+'" data-i="'+i+'">'+w[0].replace(/[<&]/g,c=>c=="<"?"&lt;":"&amp;")+"</span>");
  n++;if(/[.?!]$/.test(w[0])||linea.length>40)cerrar()});
 cerrar();caja.innerHTML=h||'<div id="vacio">Sin palabras.</div>';caja.scrollTop=y;
}
$("texto").addEventListener("click",e=>{const i=e.target.dataset.i;if(i===undefined||!window.getSelection().isCollapsed)return;
 v.currentTime=P[+i][1];v.play()});
document.addEventListener("selectionchange",()=>{
 const s=window.getSelection();sel=null;
 if(!s.isCollapsed&&$("texto").contains(s.anchorNode)){
  const ids=[...$("texto").querySelectorAll(".w")].filter(el=>s.containsNode(el,true)).map(el=>+el.dataset.i);
  if(ids.length)sel=[Math.min(...ids),Math.max(...ids)]}
 $("bCortar").disabled=$("bRest").disabled=!sel;
});
async function editar(accion,a,b){
 $("msg").textContent="...";
 const r=await fetch(BASE+"/editar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({accion,desde:a,hasta:b})});
 const d=await r.json();$("msg").textContent=d.msg;window.getSelection().removeAllRanges();ver="";cargar();
}
$("bCortar").onclick=()=>sel&&editar("borrar",sel[0],sel[1]);
$("bRest").onclick=()=>sel&&editar("restaurar",sel[0],sel[1]);
$("bDesh").onclick=()=>editar("deshacer");
let ultimo=-1;
v.addEventListener("timeupdate",()=>{
 const t=v.currentTime;
 if($("saltar").checked&&!v.paused){for(const c of C){if(t>=c[0]&&t<c[1]-0.02){v.currentTime=c[1];return}}}
 let k=-1;for(let i=0;i<P.length;i++){if(P[i][1]<=t){if(P[i][0])k=i}else break}
 if(k!==ultimo){document.querySelectorAll(".w.ahora").forEach(e=>e.classList.remove("ahora"));
  const el=document.querySelector('.w[data-i="'+k+'"]');if(el){el.classList.add("ahora");
   const caja=$("texto"),r=el.getBoundingClientRect(),rc=caja.getBoundingClientRect();
   if(!v.paused&&(r.top<rc.top||r.bottom>rc.bottom))el.scrollIntoView({block:"center"})}
  ultimo=k}
});
// el evento timeupdate va a ~4 por segundo: para saltos precisos, comprobar mas a menudo
setInterval(()=>{if(!v.paused&&$("saltar").checked){const t=v.currentTime;for(const c of C){if(t>=c[0]&&t<c[1]-0.02){v.currentTime=c[1];break}}}},50);
cargar();setInterval(cargar,2500);
</script></body></html>
"""
