@echo off
call "%~dp0..\..\bin\devos-native-docker.cmd" %*
exit /b %ERRORLEVEL%
