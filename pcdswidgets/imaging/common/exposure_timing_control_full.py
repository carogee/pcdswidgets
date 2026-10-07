"""Module for ExposureTimingControlFull"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.generated.imaging.common.exposure_timing_control_full_base import ExposureTimingControlFullBase
from pcdswidgets.icons.glyphs import CAM_COG


class ExposureTimingControlFull(ExposureTimingControlFullBase):
    designer_options = DesignerOptions(
        group="ECS Imaging Common",
        is_container=False,
        icon=CAM_COG,
    )
