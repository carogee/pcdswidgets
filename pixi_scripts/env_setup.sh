#!/bin/bash
HERE="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
THIS_ENV="${HERE}"/..

export PYQTDESIGNERPATH="${THIS_ENV}"/.pixi/envs/default/lib/python3.12/site-packages/pydm
export PYDM_DESIGNER_ONLINE=1
export QT_XCB_GL_INTEGRATION=none
export PYDM_STYLESHEET="${THIS_ENV}"/pcdswidgets/stylesheets/masterStyleSheet.qss:"${PYDM_STYLESHEET}"

# Point happi at the LCLS device database so the `typhos` env can look up
# devices (e.g. for AlarmGrid's Typhos detail screens).  Respect an existing
# HAPPI_CFG if the user already set one; harmless for the `default` env, which
# has no happi installed.
export HAPPI_CFG="${HAPPI_CFG:-/cds/group/pcds/pyps/apps/hutch-python/device_config/happi.cfg}"
