@echo off
pushd "%~dp0"
py -3.14 -m pip install --upgrade pip
py -3.14 -m pip install -r requirements.txt
popd
pause
