@echo off
REM ============================================================
REM  STEP: Copy input files for Build Variogram Cache script
REM  SOURCE FILES:
REM    - rain_2005_2012.csv  from 1_Datas (or 3_Homogeneity_Test_Output)
REM    - station_info.csv    from 1_Datas (or 3_Homogeneity_Test_Output)
REM  NOTE: This folder feeds build_variogram_cache.py in 4_Kringing.
REM        The DEM file is kept local inside 4_Kringing and is NOT
REM        needed here.
REM ============================================================

SET "DEST=%~dp0"
SET "DATA_SRC=%~dp0..\..\1_Datas"
SET "HOMOG_SRC=%~dp0..\..\3_Homogeneity_Test_Output"

echo.
echo ============================================================
echo  Copying inputs for Build Variogram Cache
echo ============================================================
echo.

REM -- 1. rain_2005_2012.csv --
echo [1/2] Copying rain_2005_2012.csv ...

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
echo [2/2] Copying station_info.csv ...

IF EXIST "%DATA_SRC%\station_info.csv" (
    copy /Y "%DATA_SRC%\station_info.csv" "%DEST%"
    echo       Source: %DATA_SRC%\station_info.csv
) ELSE IF EXIST "%HOMOG_SRC%\station_info.csv" (
    copy /Y "%HOMOG_SRC%\station_info.csv" "%DEST%"
    echo       Source: %HOMOG_SRC%\station_info.csv
) ELSE (
    echo WARNING: station_info.csv not found.
)

echo.
echo Done. Contents of this folder:
dir /B "%DEST%"
echo.
pause
