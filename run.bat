@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON=F:\Anaconda\install\python.exe"

if not exist "%PYTHON%" (
    echo [错误] 找不到 Python: %PYTHON%
    pause
    exit /b 1
)

if not exist "%SCRIPT_DIR%auto_update_galleries.py" (
    echo [错误] 找不到 auto_update_galleries.py
    pause
    exit /b 1
)

echo.
echo ========================================
echo  PDF 图片库自动更新系统
echo ========================================
echo.

"%PYTHON%" "%SCRIPT_DIR%auto_update_galleries.py"

if errorlevel 1 (
    echo.
    echo 更新出错，请检查上述错误信息。
    pause
    exit /b 1
)

echo.
echo ========================================
echo  更新完成
echo ========================================
echo.
pause
