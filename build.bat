@echo off
REM Builds fed_viewer.exe as a single standalone file.
REM Run this from the folder containing fed_viewer.py and adb_utils.py.

pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed ^
    --name fed_viewer ^
    fed_viewer.py

echo.
echo Build complete. Find fed_viewer.exe in the dist\ folder.
echo Remember: adb.exe (Android platform-tools) must be on PATH,
echo or copied next to fed_viewer.exe, for the app to work.
pause
