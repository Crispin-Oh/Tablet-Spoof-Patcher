@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 개발자용: exe 빌드 (사용자는 Python 불필요). 도구는 exe에 포함하지 않고 첫 실행 때 내려받는다.
pip install pyinstaller tkinterdnd2
pyinstaller --onefile --windowed --collect-all tkinterdnd2 --name TabletSpoofPatcher tablet_spoof_patcher.py
echo.
echo 완료: dist\TabletSpoofPatcher.exe
pause
