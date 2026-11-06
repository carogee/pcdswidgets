#!/bin/bash
# Local test launcher for the DeviceGrid example screen.
#
# Runs pydm from the pcds conda env (which has happi + typhos, so the mirror
# entries can open Typhos screens) while forcing this working checkout ahead of
# the installed pcdswidgets on PYTHONPATH (so DeviceGrid -- which the installed
# release does not have -- resolves to the code here).
#
# Usage:  ./examples/run_device_grid.sh
set -e

REPO="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"
QSS="/cds/home/c/cagee/ecs-gui-ai-generation-guide/carbon_gray10.qss"

# shellcheck disable=SC1091
source /cds/group/pcds/pyps/conda/pcds_conda

PYTHONPATH="${REPO}:${PYTHONPATH}" \
    pydm --stylesheet "${QSS}" "${REPO}/examples/device_grid.ui"
