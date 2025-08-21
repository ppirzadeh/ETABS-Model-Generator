@echo off
cd /d %~dp0
echo ETABS Model Generator. Let's get the tool ready for you!
echo.

:: Step 1: Create the virtual environment
echo Creating virtual environment...
py -m venv .venv

:: Step 2: Activate the virtual environment
echo Activating the virtual environment...
call .venv\Scripts\activate.bat

:: Step 3: Install packages from requirements.txt
echo Installing python packages from requirements.txt
pip install -r requirements.txt

echo Setup completed. You may proceed if there are no error messages above.
pause