"""Module for MotorBeckhoffSlits"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.builder.icon_options import IconOptions
from pcdswidgets.generated.motion.common.motor_beckhoff_slits_base import MotorBeckhoffSlitsBase


class MotorBeckhoffSlits(MotorBeckhoffSlitsBase):
    designer_options = DesignerOptions(
        group="ECS Motion Common",
        is_container=False,
        icon=IconOptions.NONE,
    )
