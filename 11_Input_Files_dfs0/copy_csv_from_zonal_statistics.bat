@echo off
REM ============================================================
REM  STEP: Copy Zonal Statistics CSV outputs into DFS0 input folder
REM  SOURCE : ..\9_Zonal_Statistics_Output\csv_for_netcdf0\
REM  DEST   : .\csv_for_netcdf0\   (11_Input_Files_dfs0\csv_for_netcdf0\)
REM  PURPOSE: The DFS0 writer script (4_write_dsf0.py) reads the
REM           subbasin rainfall CSVs produced by zonal statistics.
REM           This bat copies them from the Zonal Statistics output
REM           folder into this input folder automatically.
REM ============================================================

SET "SOURCE=%~dp0..\9_Zonal_Statistics_Output\csv_for_netcdf0"
SET "DEST=%~dp0csv_for_netcdf0"

echo.
echo ============================================================
echo  Copying Zonal Statistics CSVs -> DFS0 input folder
echo ============================================================
echo.
echo   FROM: %SOURCE%
echo   TO  : %DEST%
echo.

IF NOT EXIST "%SOURCE%" (
    echo ERROR: Source folder not found: %SOURCE%
    echo        Run the Zonal Statistics step first (3_Run_Zonal_Statistics.cmd
    echo        inside 7_Zonal_Statistics) to generate the CSV files.
    pause
    exit /b 1
)

IF NOT EXIST "%DEST%" (
    mkdir "%DEST%"
    echo Created folder: %DEST%
)

xcopy /Y /I "%SOURCE%\*.csv" "%DEST%\"

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: All CSV files copied.
    echo.
    dir /B "%DEST%"
) ELSE (
    echo.
    echo ERROR: Copy failed or no .csv files found in source.
    echo        Check that the Zonal Statistics run completed successfully.
)

echo.
pause
