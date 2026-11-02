# ==============================================================================
# FILE: gpo_macro/build_exe.bat
# ==============================================================================

@echo off
REM ============================================================================
REM SCRIPT DI COMPILAZIONE AUTOMATICA IN ESEGUIBILE (.EXE) CON PYINSTALLER
REM Crea un singolo file standalone in dist\GPO_Boss_Macro.exe
REM ============================================================================

echo [1/3] Installazione dipendenze e PyInstaller...
pip install -r requirements.txt
pip install pyinstaller

echo [2/3] Creazione cartella template se mancante...
if not exist "assets\templates" mkdir "assets\templates"

echo [3/3] Compilazione in singolo eseguibile Windows (.exe)...
pyinstaller --noconfirm --onefile --windowed ^
  --name "GPO_Boss_Macro" ^
  --add-data "assets;assets" ^
  --hidden-import "pynput.keyboard._win32" ^
  --hidden-import "pynput.mouse._win32" ^
  main.py

echo.
echo ============================================================================
echo COMPILAZIONE COMPLETATA!
echo Trovi il tuo eseguibile in: dist\GPO_Boss_Macro.exe
echo Ricorda di avviare GPO_Boss_Macro.exe come Amministratore!
echo ============================================================================
pause