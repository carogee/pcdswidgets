"""Module for AcquisitionControlFull"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

from qtpy.QtWidgets import QComboBox, QWidget

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.generated.imaging.common.acquisition_control_full_base import AcquisitionControlFullBase
from pcdswidgets.icons.glyphs import CAM_COG


class AcquisitionControlFull(AcquisitionControlFullBase):
    multiple_count_group: QWidget
    image_mode_combo: QComboBox

    designer_options = DesignerOptions(
        group="ECS Imaging Common",
        is_container=False,
        icon=CAM_COG,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image_mode_combo.currentTextChanged.connect(self._toggle_multiple_visibility)
        self._toggle_multiple_visibility(self.image_mode_combo.currentText())

    def _toggle_multiple_visibility(self, value):
        """only show multiple_count when in "Multiple" capture mode"""
        self.multiple_count_group.setVisible(value == "Multiple")
