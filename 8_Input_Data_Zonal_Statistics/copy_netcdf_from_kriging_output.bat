@echo off
REM ============================================================
REM  STEP: Copy Kriging NetCDF outputs into Zonal Statistics input
REM  SOURCE : ..\6_Kringing_Output\netcdf_out\
REM  DEST   : .\netcdf_out\   (8_Input_Data_Zonal_Statistics\netcdf_out\)
REM  PURPOSE: The Zonal Statistics script reads all *.nc files from
REM           a NetCDF folder. This bat copies the kriged rainfall
REM           NetCDFs produced by 4_Kringing into this input folder
REM           so zonal_statistic.py can find them.
REM ============================================================

SET "SOURCE=%~dp0..\6_Kringing_Output\netcdf_out"
SET "DEST=%~dp0netcdf_out"

echo.
echo ============================================================
echo  Copying Kriging NetCDF outputs -> Zonal Statistics input
echo ============================================================
echo.
echo   FROM: %SOURCE%
echo   TO  : %DEST%
echo.

IF NOT EXIST "%SOURCE%" (
    echo ERROR: Source folder not found: %SOURCE%
    echo        Run the Kriging batch step first (5_run_batch_kriging_gui_app.bat
    echo        inside 4_Kringing) to generate the NetCDF files.
    pause
    exit /b 1
)

IF NOT EXIST "%DEST%" (
    mkdir "%DEST%"
    echo Created folder: %DEST%
)

xcopy /Y /I "%SOURCE%\*.nc" "%DEST%\"

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: All NetCDF files copied.
    echo.
    dir /B "%DEST%"
) ELSE (
    echo.
    echo ERROR: Copy failed or no .nc files found in source.
    echo        Check that the Kriging batch run completed successfully.
)

echo.
pause
