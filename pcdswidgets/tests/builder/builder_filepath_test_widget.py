"""Module for BuilderFilepathTestWidget"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.builder.icon_options import IconOptions
from pcdswidgets.generated.tests.builder.builder_filepath_test_widget_base import BuilderFilepathTestWidgetBase


class BuilderFilepathTestWidget(BuilderFilepathTestWidgetBase):
    designer_options = DesignerOptions(
        group="ECS Tests Builder",
        is_container=False,
        icon=IconOptions.NONE,
    )
