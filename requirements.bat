@echo off

set MYDIR=%CD%

echo Downloading requirements for windows 7/10

echo Downloading python-3.8.10-amd64.exe...
powershell -c "$ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe' -OutFile 'python-3.8.10-amd64.exe'"
echo Installing Python 3.8.10 with parameters /passive PrependPath=1
start /wait python-3.8.10-amd64.exe /passive PrependPath=1

echo Done. Run "python firmware.py build" to install the rest of requirements
