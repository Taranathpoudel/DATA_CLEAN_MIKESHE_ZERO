@echo off
REM ============================================================
REM  STEP: Copy input files for Variogram Cache Builder
REM  SOURCE FILES (from 1_Datas and 3_Homogeneity_Test_Output):
REM    - rain_2005_2012.csv   (processed rainfall data)
REM    - station_info.csv     (station metadata)
REM    - demtopo900utm45n.txt (DEM/topography file)
REM  PURPOSE: Provides the 3 required input files that
REM           build_variogram_cache.py (step 2 of Kriging) needs.
REM ============================================================

SET "DEST=%~dp0"
SET "DATA_SRC=%~dp0..\..\1_Datas"
SET "HOMOG_SRC=%~dp0..\..\3_Homogeneity_Test_Output"

echo.
echo ============================================================
echo  Copying inputs for Variogram Cache Builder
echo ============================================================
echo.

REM -- 1. Copy rain CSV (from 1_Datas or 3_Homogeneity_Test_Output) --
echo [1/3] Copying rain_2005_2012.csv ...

IF EXIST "%DATA_SRC%\rain_2005_2012.csv" (
    copy /Y "%DATA_SRC%\rain_2005_2012.csv" "%DEST%"
    echo       Source: %DATA_SRC%\rain_2005_2012.csv
) ELSE IF EXIST "%HOMOG_SRC%\rain_2005_2012.csv" (
    copy /Y "%HOMOG_SRC%\rain_2005_2012.csv" "%DEST%"
    echo       Source: %HOMOG_SRC%\rain_2005_2012.csv
) ELSE (
    echo WARNING: rain_2005_2012.csv not found in 1_Datas or 3_Homogeneity_Test_Output.
)

REM -- 2. Copy station_info.csv --
echo [2/3] Copying station_info.csv ...

IF EXIST "%DATA_SRC%\station_info.csv" (
    copy /Y "%DATA_SRC%\station_info.csv" "%DEST%"
    echo       Source: %DATA_SRC%\station_info.csv
) ELSE IF EXIST "%HOMOG_SRC%\station_info.csv" (
    copy /Y "%HOMOG_SRC%\station_info.csv" "%DEST%"
    echo       Source: %HOMOG_SRC%\station_info.csv
) ELSE (
    echo WARNING: station_info.csv not found in 1_Datas or 3_Homogeneity_Test_Output.
)

REM -- 3. Copy DEM file (stays as a static source file from 1_Datas) --
echo [3/3] Copying demtopo900utm45n.txt ...

IF EXIST "%DATA_SRC%\demtopo900utm45n.txt" (
    copy /Y "%DATA_SRC%\demtopo900utm45n.txt" "%DEST%"
    echo       Source: %DATA_SRC%\demtopo900utm45n.txt
) ELSE (
    echo WARNING: demtopo900utm45n.txt not found in 1_Datas.
    echo          It may need to be placed there manually.
)

echo.
echo Done. Contents of this folder:
dir /B "%DEST%"
echo.
pause
