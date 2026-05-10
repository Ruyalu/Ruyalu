@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD=py -3-32"
%PYTHON_CMD% -c "import struct, sys; sys.exit(0 if struct.calcsize('P') == 4 else 1)" >nul 2>nul
if errorlevel 1 (
  set "PYTHON_CMD=python"
  python -c "import struct, sys; sys.exit(0 if struct.calcsize('P') == 4 else 1)" >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] To create a Windows x86 application, install 32-bit Python for Windows.
    echo Then run this script again from Command Prompt.
    exit /b 1
  )
)

%PYTHON_CMD% -m pip install --upgrade pyinstaller opencv-python numpy
if errorlevel 1 exit /b 1

%PYTHON_CMD% -m PyInstaller --onefile --windowed --name RuyaluWatermarkTool watermark_desktop.py
if errorlevel 1 exit /b 1

if exist ffmpeg.exe (
  copy /Y ffmpeg.exe dist\ffmpeg.exe >nul
  echo Copied ffmpeg.exe to dist folder.
) else (
  echo [WARN] ffmpeg.exe was not found beside this script.
  echo Put ffmpeg.exe in the dist folder or install FFmpeg on the user's PATH.
)

if exist ffprobe.exe (
  copy /Y ffprobe.exe dist\ffprobe.exe >nul
  echo Copied ffprobe.exe to dist folder.
) else (
  echo [WARN] ffprobe.exe was not found beside this script.
  echo Put ffprobe.exe in the dist folder or install FFmpeg on the user's PATH.
)

echo.
echo Done. Application: dist\RuyaluWatermarkTool.exe
endlocal
