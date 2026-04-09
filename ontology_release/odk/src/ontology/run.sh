#!/usr/bin/env sh
set -eu
if [ "$#" -eq 0 ]; then
  echo "Usage: ./run.sh make <target>"
  exit 1
fi
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PIPELINE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
docker run --rm -e ROBOT_JAVA_ARGS=-Xmx6G -v "$PIPELINE_ROOT:/work" -w /work/odk/src/ontology obolibrary/odkfull "$@"
