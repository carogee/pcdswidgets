#!/bin/bash
# Local test launcher for the DeviceGrid example screen.
#
# Runs pydm from this repo's `typhos` pixi environment, which has happi +
# typhos + pcdsdevices (so the mirror entries can open Typhos screens) and
# installs pcdswidgets editable from this checkout (so DeviceGrid resolves to
# the code here).  HAPPI_CFG is set by pixi_scripts/env_setup.sh on activation.
#
# One-time setup, if the env is not built yet:
#     pixi install -e typhos
#     bash pixi_scripts/install.sh
#
# Usage:  ./examples/run_device_grid.sh
set -e

REPO="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"
QSS="/cds/home/c/cagee/ecs-gui-ai-generation-guide/carbon_gray10.qss"

PIXI="$(command -v pixi || echo "${HOME}/.pixi/bin/pixi")"

cd "${REPO}"
exec "${PIXI}" run -e typhos pydm --stylesheet "${QSS}" "${REPO}/examples/device_grid.ui"
