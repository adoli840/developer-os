@echo off
python "%~dp0..\docker\native_docker.py" --working-directory "%CD%" -- %*
exit /b %ERRORLEVEL%
