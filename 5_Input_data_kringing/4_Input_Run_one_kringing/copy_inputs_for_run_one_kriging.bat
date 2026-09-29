@echo off
REM ============================================================
REM  STEP: Copy input files for Run One Kriging
REM  SOURCE FILES:
REM    - rain_2005_2012.csv   from 1_Datas (or 3_Homogeneity_Test_Output)
REM    - station_info.csv     from 1_Datas (or 3_Homogeneity_Test_Output)
REM    - demtopo900utm45n.txt from 1_Datas
REM  PURPOSE: Provides all 3 files needed by run_kriging_example_filtered.py
REM           (4_Run_One_Kringing step in 4_Kringing folder).
REM ============================================================

SET "DEST=%~dp0"
SET "DATA_SRC=%~dp0..\..\1_Datas"
SET "HOMOG_SRC=%~dp0..\..\3_Homogeneity_Test_Output"

echo.
echo ============================================================
echo  Copying inputs for Run One Kriging
echo ============================================================
echo.

REM -- 1. rain_2005_2012.csv --
echo [1/3] Copying rain_2005_2012.csv ...

IF EXIST "%DATA_SRC%\rain_2005_2012.csv" (
    copy /Y "%DATA_SRC%\rain_2005_2012.csv" "%DEST%"
    echo       Source: %DATA_SRC%\rain_2005_2012.csv
) ELSE IF EXIST "%HOMOG_SRC%\rain_2005_2012.csv" (
    copy /Y "%HOMOG_SRC%\rain_2005_2012.csv" "%DEST%"
    echo       Source: %HOMOG_SRC%\rain_2005_2012.csv
) ELSE (
    echo WARNING: rain_2005_2012.csv not found.
)

REM -- 2. station_info.csv --
echo [2/3] Copying station_info.csv ...

IF EXIST "%DATA_SRC%\station_info.csv" (
    copy /Y "%DATA_SRC%\station_info.csv" "%DEST%"
    echo       Source: %DATA_SRC%\station_info.csv
) ELSE IF EXIST "%HOMOG_SRC%\station_info.csv" (
    copy /Y "%HOMOG_SRC%\station_info.csv" "%DEST%"
    echo       Source: %HOMOG_SRC%\station_info.csv
) ELSE (
    echo WARNING: station_info.csv not found.
)

REM -- 3. DEM file --
echo [3/3] Copying demtopo900utm45n.txt ...

IF EXIST "%DATA_SRC%\demtopo900utm45n.txt" (
    copy /Y "%DATA_SRC%\demtopo900utm45n.txt" "%DEST%"
    echo       Source: %DATA_SRC%\demtopo900utm45n.txt
) ELSE (
    echo WARNING: demtopo900utm45n.txt not found in 1_Datas.
)

echo.
echo Done. Contents of this folder:
dir /B "%DEST%"
echo.
pause
