"""Module for SmaractOpenLoopContextDouble"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

import logging

from pydm.widgets import PyDMPushButton

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.generated.motion.smaract.smaract_open_loop_context_double_base import SmaractOpenLoopContextDoubleBase

logger = logging.getLogger(__name__)


class SmaractOpenLoopContextDouble(SmaractOpenLoopContextDoubleBase):
    clear_step_count: PyDMPushButton

    designer_options = DesignerOptions(
        group="ECS Motion Smaract",
        is_container=False,
        icon="smaract_tip_tilt_context_qt_icon.png",
    )
