"""
Some basic tests for TabDockDiagramButton.

Most of the "functionality" is visual, but there are a few simple things
that we'd like to make sure don't break.
"""

import pytest
from pydm.widgets.channel import PyDMChannel
from pytestqt.qtbot import QtBot
from qtpy.QtCore import QObject

from pcdswidgets.common.dock.tab_dock_diagram_button import DiagramOption, TabDockDiagramButton

try:
    from qtpy.QtCore import pyqtSignal as Signal
except ImportError:
    from qtpy.QtCore import Signal  # type: ignore


@pytest.fixture(scope="function")
def diagram_button(qtbot: QtBot) -> TabDockDiagramButton:
    """Load a TabDockDiagramButton and make sure we'll clean it up properly."""
    button = TabDockDiagramButton()
    qtbot.add_widget(button)
    return button


@pytest.mark.parametrize("diagram_option", list(DiagramOption))
def test_image_exists(diagram_option: DiagramOption):
    """Make sure we didn't lose the pngs"""
    if diagram_option == DiagramOption.BLANK:
        with pytest.raises(ValueError):
            diagram_option.get_image_path()
    else:
        assert diagram_option.get_image_path().is_file()


@pytest.mark.parametrize("diagram_option", list(DiagramOption))
def test_diagram_options(qtbot: QtBot, diagram_button: TabDockDiagramButton, diagram_option: DiagramOption):
    """Make sure all enum options are included fully."""
    # This shouldn't error out
    diagram_button.setDiagram(diagram_option)
    # We should be able to get it back
    assert diagram_button.readDiagram() == diagram_option
    # The attribute should exist and be correct
    assert getattr(diagram_button, diagram_option.name) == DiagramOption[diagram_option.name]
    # Make sure there's no funny business in the rendering pipeline that explodes
    qtbot.wait(50)


def test_lightpath_channel(qtbot: QtBot, diagram_button: TabDockDiagramButton):
    """Make sure the lightpath option setting is stable."""

    # This is the canonical way to send to a local signal? Gross
    class Cls(QObject):
        sig = Signal(bool)

    obj = Cls()

    ch = PyDMChannel("loc://test_lightpath_channel?type=bool&init=False", value_signal=obj.sig)
    ch.connect()
    # I don't think local plugin channels work correctly, I need to re-send False
    obj.sig.emit(False)

    # Check that we initialize sensibly
    assert diagram_button._lightpath_status is None
    diagram_button.setLightpathChannel("loc://test_lightpath_channel")
    qtbot.wait(50)
    assert diagram_button._lightpath_status is not None
    assert not diagram_button._lightpath_status

    obj.sig.emit(True)

    def assert_lp_true():
        assert diagram_button._lightpath_status

    # Check that when the channels updates to true we get it
    qtbot.wait_until(assert_lp_true)
    assert_lp_true()

    # Make sure no funny business in the rendering pipeline
    qtbot.wait(50)
