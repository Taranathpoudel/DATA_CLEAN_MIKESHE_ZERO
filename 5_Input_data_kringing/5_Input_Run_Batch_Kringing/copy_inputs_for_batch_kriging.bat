@echo off
REM ============================================================
REM  STEP: Copy input files for Run Batch Kriging
REM  SOURCE FILES:
REM    - rain_2005_2012.csv          from 1_Datas (or 3_Homogeneity_Test_Output)
REM    - station_info.csv            from 1_Datas (or 3_Homogeneity_Test_Output)
REM    - demtopo900utm45n.txt        from 1_Datas
REM    - variogram_cache.csv (cache) from 6_Kringing_Output\cache\
REM                                   (output of Build Variogram Cache step)
REM  PURPOSE: Provides all files needed by run_batch_all_years.py
REM           (5_run_batch_kriging step in 4_Kringing folder).
REM           NOTE: The .txt file reminds you to also paste the
REM           variogram cache CSV when it is ready.
REM ============================================================

SET "DEST=%~dp0"
SET "DATA_SRC=%~dp0..\..\1_Datas"
SET "HOMOG_SRC=%~dp0..\..\3_Homogeneity_Test_Output"
SET "CACHE_SRC=%~dp0..\..\6_Kringing_Output\cache"

echo.
echo ============================================================
echo  Copying inputs for Run Batch Kriging
echo ============================================================
echo.

REM -- 1. rain_2005_2012.csv --
echo [1/4] Copying rain_2005_2012.csv ...

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
echo [2/4] Copying station_info.csv ...

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
echo [3/4] Copying demtopo900utm45n.txt ...

IF EXIST "%DATA_SRC%\demtopo900utm45n.txt" (
    copy /Y "%DATA_SRC%\demtopo900utm45n.txt" "%DEST%"
    echo       Source: %DATA_SRC%\demtopo900utm45n.txt
) ELSE (
    echo WARNING: demtopo900utm45n.txt not found in 1_Datas.
)

REM -- 4. Variogram Cache CSV (output from Build Variogram Cache step) --
echo [4/4] Copying variogram_cache.csv from Kriging Output cache ...

IF EXIST "%CACHE_SRC%\variogram_cache.csv" (
    copy /Y "%CACHE_SRC%\variogram_cache.csv" "%DEST%"
    echo       Source: %CACHE_SRC%\variogram_cache.csv
    echo       NOTE: Also update paste_the_csv_of_catche_variogram_builder.txt if needed.
) ELSE (
    echo WARNING: variogram_cache.csv not found in 6_Kringing_Output\cache\.
    echo          Run Build Variogram Cache step first (3_build_Variogram_cache.bat in 4_Kringing).
)

echo.
echo Done. Contents of this folder:
dir /B "%DEST%"
echo.
pause
