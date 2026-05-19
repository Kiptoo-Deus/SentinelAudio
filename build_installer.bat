@echo off
setlocal enabledelayedexpansion
title Sentinel Audio - Build Installer

echo.
echo  ============================================================
echo    SENTINEL AUDIO  ^|  Build Installer
echo  ============================================================
echo.

set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set PYTHON=venv\Scripts\python.exe
set PYINSTALLER=venv\Scripts\pyinstaller.exe

:: ----------------------------------------------------------------
:: 0. Preflight checks
:: ----------------------------------------------------------------
echo [1/5] Checking tools...

if not exist "%PYTHON%" (
    echo ERROR: venv not found. Run setup.bat first.
    pause & exit /b 1
)

if not exist %ISCC% (
    echo ERROR: Inno Setup 6 not found at expected path.
    echo        Download from https://jrsoftware.org/isdl.php
    pause & exit /b 1
)

:: ----------------------------------------------------------------
:: 1. Generate icon
:: ----------------------------------------------------------------
echo [2/5] Generating icon...
%PYTHON% build_icon.py
if errorlevel 1 (
    echo ERROR: Icon generation failed.
    pause & exit /b 1
)

:: ----------------------------------------------------------------
:: 2. Generate installer splash bitmap (installer_small.bmp)
:: ----------------------------------------------------------------
echo       Generating installer graphics...
%PYTHON% -c "
import struct, os

def write_bmp(path, w, h, pixels_rgb):
    row_size = ((w * 3 + 3) // 4) * 4
    pixel_data = bytearray()
    for y in range(h-1, -1, -1):
        row = bytearray()
        for x in range(w):
            r, g, b = pixels_rgb[y*w+x]
            row += bytes([b, g, r])
        row += b'\x00' * (row_size - len(row))
        pixel_data += row
    file_size = 54 + len(pixel_data)
    bmp = b'BM'
    bmp += struct.pack('<I', file_size)
    bmp += b'\x00\x00\x00\x00'
    bmp += struct.pack('<I', 54)
    bmp += struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0, len(pixel_data), 0, 0, 0, 0)
    bmp += pixel_data
    with open(path, 'wb') as f:
        f.write(bmp)

import math
w, h = 55, 55
pixels = []
for y in range(h):
    for x in range(w):
        cx, cy = w/2, h/2
        dx, dy = x-cx, y-cy
        dist = math.sqrt(dx*dx+dy*dy)
        if dist < w*0.46:
            norm_x = dx/(w*0.38)
            if abs(norm_x) <= 1.0:
                wave_y = cy + math.sin(norm_x*math.pi*1.5)*(h*0.14)
                t = abs(math.sin(norm_x*math.pi*1.5))
                if abs(y-wave_y) <= 3:
                    pixels.append((int(90+t*134), int(175-t*135), int(207-t*177)))
                    continue
            pixels.append((18, 28, 38))
        else:
            pixels.append((10, 13, 15))
write_bmp('assets/installer_small.bmp', w, h, pixels)
print('OK')
"
if errorlevel 1 (
    echo WARNING: Could not generate installer graphic - continuing anyway.
)

:: ----------------------------------------------------------------
:: 3. PyInstaller — bundle to dist/SentinelAudio/
:: ----------------------------------------------------------------
echo [3/5] Bundling with PyInstaller (this takes a few minutes)...

if exist dist\SentinelAudio rmdir /s /q dist\SentinelAudio
if exist build\SentinelAudio rmdir /s /q build\SentinelAudio

%PYINSTALLER% sentinel_audio.spec --noconfirm --clean
if errorlevel 1 (
    echo ERROR: PyInstaller failed. Check output above.
    pause & exit /b 1
)

:: Verify the exe was created
if not exist dist\SentinelAudio\SentinelAudio.exe (
    echo ERROR: SentinelAudio.exe not found in dist\SentinelAudio\
    pause & exit /b 1
)
echo       Bundle created: dist\SentinelAudio\ ^(%~dp0dist\SentinelAudio%)

:: ----------------------------------------------------------------
:: 4. Inno Setup — compile installer
:: ----------------------------------------------------------------
echo [4/5] Compiling installer with Inno Setup...

if not exist installer\output mkdir installer\output

%ISCC% installer\sentinel_audio.iss
if errorlevel 1 (
    echo ERROR: Inno Setup compilation failed.
    pause & exit /b 1
)

:: ----------------------------------------------------------------
:: 5. Done
:: ----------------------------------------------------------------
echo [5/5] Done!
echo.

for %%f in (installer\output\SentinelAudio_Setup_*.exe) do (
    echo  Installer: %%f
    echo  Size:      %%~zf bytes
)

echo.
echo  ============================================================
echo    Installer ready in installer\output\
echo  ============================================================
echo.
explorer installer\output
pause
