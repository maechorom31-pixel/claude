@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python 이 필요합니다. https://www.python.org/downloads/ 에서 설치할 때
  echo "Add python.exe to PATH" 를 꼭 켜세요.
  pause
  exit /b 1
)
python -m pip install --quiet pymupdf
echo 브라우저가 열립니다. 이 창은 끄지 마세요 (끄면 검색기가 꺼집니다).
start "" http://127.0.0.1:8765
python -m gichul web
pause
