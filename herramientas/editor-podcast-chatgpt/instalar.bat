@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==================================================
echo  Instalando el Editor de podcast para ChatGPT
echo  (tarda unos minutos; no cierres esta ventana)
echo ==================================================
echo.

where winget >nul 2>nul
if errorlevel 1 (
  echo Falta "winget" ^(Instalador de aplicaciones^). Actualiza Windows o instala
  echo "App Installer" desde la Microsoft Store y vuelve a ejecutar este archivo.
  pause
  exit /b 1
)

echo [1/5] Python...
py -3 --version >nul 2>nul
if errorlevel 1 (
  winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements
)

echo [2/5] ffmpeg ^(corta el video^)...
where ffmpeg >nul 2>nul
if errorlevel 1 (
  winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
)

echo [3/5] cloudflared ^(conecta tu PC con ChatGPT^)...
where cloudflared >nul 2>nul
if errorlevel 1 (
  winget install -e --id Cloudflare.cloudflared --accept-source-agreements --accept-package-agreements
)

echo [4/5] Librerias de Python...
set "PY=py -3"
py -3 --version >nul 2>nul
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  ) else (
    echo No encuentro Python todavia. Cierra esta ventana y ejecuta instalar.bat otra vez.
    pause
    exit /b 1
  )
)
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo Fallo la instalacion de librerias. Revisa tu conexion y vuelve a probar.
  pause
  exit /b 1
)

echo [5/5] Modelo de voz para transcribir ^(unos 500 MB, solo la primera vez^)...
".venv\Scripts\python.exe" servidor.py --descargar-modelo
if errorlevel 1 (
  echo Fallo la descarga del modelo. Vuelve a ejecutar instalar.bat.
  pause
  exit /b 1
)
if not exist videos mkdir videos

echo.
echo [Opcional] URL fija para ChatGPT ^(asi no tienes que cambiarla cada vez^)
".venv\Scripts\python.exe" servidor.py --configurar-ngrok

echo.
echo ==================================================
echo  Listo. Ahora haz doble clic en iniciar.bat
echo ==================================================
pause
