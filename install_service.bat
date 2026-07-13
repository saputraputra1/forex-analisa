@echo off
chcp 65001 >nul

echo ========================================
echo  Install XAUUSD Bot - Auto Startup
echo ========================================
echo.

taskkill /f /im python.exe 2>nul

echo [1/2] Adding to Windows Registry (HKCU Run)...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "XAUUSD_Trading_Bot" /t REG_SZ /d "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File \"C:\Users\izmet\Downloads\forexx\run_bot.ps1\"" /f >nul
echo   OK - Bot will start automatically on login

echo [2/2] Starting bot now...
start /min powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\Users\izmet\Downloads\forexx\run_bot.ps1"

timeout /t 3 >nul
tasklist /fi "imagename eq python.exe" 2>nul | find "python.exe" >nul
if %errorlevel%==0 (
    echo   OK - Bot is RUNNING
) else (
    echo   ERROR - Bot failed to start
)

echo.
echo ========================================
echo  INSTALLATION COMPLETE
echo ========================================
echo.
echo  The bot is now running 24/7.
echo  It will auto-start when you login.
echo. 
echo  Commands:
echo    check status:  tasklist /fi "imagename eq python.exe"
echo    stop bot:      taskkill /f /im python.exe
echo    uninstall:     reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "XAUUSD_Trading_Bot" /f
echo.
pause
