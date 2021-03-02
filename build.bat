python --version 2>NUL
if errorlevel 1 goto errorNoPython
python -m pip install -r requirements.txt

python -m PyInstaller --onefile main.py
copy config.json dist\config.json
pause
exit

:errorNoPython
echo.
echo Error^: Python not installed
pause
exit