@echo off
REM ============================================================
REM  STEP: Copy Homogeneity Test outputs into this input folder
REM  SOURCE : ..\..\_3_Homogeneity_Test_Output\
REM  PURPOSE: Makes all SNHT result files available here so
REM           the Kriging pipeline can reference them.
REM ============================================================

SET "SOURCE=%~dp0..\..\3_Homogeneity_Test_Output"
SET "DEST=%~dp0"

echo.
echo Copying Homogeneity Test outputs...
echo   FROM: %SOURCE%
echo   TO  : %DEST%
echo.

IF NOT EXIST "%SOURCE%" (
    echo ERROR: Source folder not found: %SOURCE%
    echo        Run the Homogeneity Test first (2_Homogeneity_Test).
    pause
    exit /b 1
)

xcopy /Y /I "%SOURCE%\*" "%DEST%"

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: All files copied.
) ELSE (
    echo.
    echo ERROR: Copy failed. Check paths and permissions.
)

echo.
pause
