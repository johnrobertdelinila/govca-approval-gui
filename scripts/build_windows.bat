@echo off
REM Build script for Windows
REM Creates GovCAApproval.exe

echo ========================================
echo  Building GovCA Approval for Windows
echo ========================================

REM Navigate to project root (scripts\ -> project root)
cd /d "%~dp0\.."
set PROJECT_ROOT=%CD%

echo Project root: %PROJECT_ROOT%

REM Create virtual environment if not exists
if not exist "build_env" (
    echo Creating virtual environment...
    python -m venv build_env
)

REM Activate virtual environment
call build_env\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM Create drivers directory if not exists
if not exist "drivers" mkdir drivers

REM Download geckodriver if not present
if not exist "drivers\geckodriver.exe" (
    echo Downloading geckodriver...
    curl -L -o geckodriver.zip https://github.com/mozilla/geckodriver/releases/download/v0.34.0/geckodriver-v0.34.0-win64.zip
    powershell -command "Expand-Archive -Path geckodriver.zip -DestinationPath drivers -Force"
    del geckodriver.zip
    echo Geckodriver downloaded.
) else (
    echo Geckodriver already present.
)

REM Clean previous PyInstaller builds (but NOT our spec files)
echo Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Run PyInstaller with spec file from specs\ directory
echo Running PyInstaller...
pyinstaller specs\windows\govca_approval.spec --clean --noconfirm

REM Check if exe was created
if exist "dist\GovCAApproval.exe" (
    echo ========================================
    echo  Build Complete!
    echo ========================================
    echo.
    echo Output file:
    echo   dist\GovCAApproval.exe
    echo.
    echo To run:
    echo   Double-click GovCAApproval.exe
    echo.
) else (
    echo ERROR: Executable was not created!
    exit /b 1
)

call deactivate
echo Done!
pause
