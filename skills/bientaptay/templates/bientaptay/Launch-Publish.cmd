@echo off
python "%~dp0release_publish.py" %*
set "PUBLISH_EXIT=%ERRORLEVEL%"
exit /b %PUBLISH_EXIT%
