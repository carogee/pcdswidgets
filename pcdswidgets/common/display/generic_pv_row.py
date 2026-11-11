"""Module for GenericPvRow"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.builder.icon_options import IconOptions
from pcdswidgets.generated.common.display.generic_pv_row_base import GenericPvRowBase


class GenericPvRow(GenericPvRowBase):
    designer_options = DesignerOptions(
        group="ECS Common Display",
        is_container=False,
        icon=IconOptions.NONE,
    )
