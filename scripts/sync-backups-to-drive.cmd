@echo off
rem Copy Watchd's nightly backups (written into the project's backups folder
rem by the backup service, see backup.sh) to Google Drive, which uploads them.
rem Run by the "Watchd backup to Google Drive" scheduled task at 3:30am and
rem at sign-in. Docker can't write to Google Drive's G: drive itself.
rem
rem If NTFY_URL is set in .env, a failed copy sends a push notification.
set "SRC=%~dp0..\backups"
set "DEST=G:\My Drive\Watchd Backups"
set "NTFY_URL="
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b /c:"NTFY_URL=" "%~dp0..\.env"`) do set "NTFY_URL=%%b"

if not exist "G:\My Drive" (
    call :notify "Google Drive isn't running (no G:\My Drive), so the backups weren't copied to Drive."
    exit /b 1
)
robocopy "%SRC%" "%DEST%" /MIR /R:2 /W:5 /NP /NFL /NDL /LOG:"%SRC%\last-sync.log"
rem robocopy exit codes below 8 mean success.
set "RC=%ERRORLEVEL%"
if %RC% LSS 8 exit /b 0
call :notify "Copying the backups to Google Drive failed (robocopy code %RC%). See backups\last-sync.log."
exit /b %RC%

:notify
if not defined NTFY_URL exit /b 0
curl.exe -fsS -m 15 -H "Title: Watchd Drive copy failed" -H "Priority: high" -H "Tags: floppy_disk" -d "%~1" "%NTFY_URL%" >nul 2>&1
exit /b 0
