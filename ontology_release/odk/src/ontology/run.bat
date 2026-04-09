@echo off
setlocal
if "%~1"=="" (
  echo Usage: run.bat make ^<target^>
  exit /b 1
)
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..\..") do set "PIPELINE_ROOT=%%~fI"
docker run --rm -e ROBOT_JAVA_ARGS=-Xmx6G -v "%PIPELINE_ROOT%:/work" -w /work/odk/src/ontology obolibrary/odkfull %*
