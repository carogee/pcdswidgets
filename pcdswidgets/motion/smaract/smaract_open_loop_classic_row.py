"""Module for SmaractOpenLoopClassicRow"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.builder.icon_options import IconOptions
from pcdswidgets.generated.motion.smaract.smaract_open_loop_classic_row_base import SmaractOpenLoopClassicRowBase


class SmaractOpenLoopClassicRow(SmaractOpenLoopClassicRowBase):
    designer_options = DesignerOptions(
        group="ECS Motion Smaract",
        is_container=False,
        icon=IconOptions.NONE,
    )
