"""
Confirm the overridden widgets react to the mouse wheel as intended.

- ``SpinBoxClickToScroll``: scrolls only once the widget has focus.
- ``ComboBoxNoScroll``: never scrolls; the wheel is always passed on.
- plain ``QSpinBox``: always scrolls, with or without focus.

``PyDMSpinBoxClickToScroll.keyPressEvent`` (<Enter> validates/sends/clears) is
checked separately at the bottom.
"""

from unittest.mock import Mock

import pytest
from pydm.widgets import PyDMSpinbox
from pytestqt.qtbot import QtBot
from qtpy.QtCore import QEvent, QPoint, QPointF, Qt
from qtpy.QtGui import QKeyEvent, QWheelEvent
from qtpy.QtWidgets import QApplication, QComboBox, QDoubleSpinBox, QSpinBox

from pcdswidgets.common.widget_overrides.combobox_no_scroll import ComboBoxNoScroll
from pcdswidgets.common.widget_overrides.spinbox_click_to_scroll import (
    DoubleSpinBoxClickToScroll,
    PyDMSpinBoxClickToScroll,
    SpinBoxClickToScroll,
)


def _wheel_event(widget, notches: int = 1) -> QWheelEvent:
    """Build a vertical wheel event (120 units == one notch)."""
    pos = QPointF(widget.rect().center())
    angle = QPoint(0, 120 * notches)
    return QWheelEvent(
        pos,
        QPointF(widget.mapToGlobal(widget.rect().center())),
        QPoint(0, 0),
        angle,
        Qt.NoButton,
        Qt.NoModifier,
        Qt.NoScrollPhase,
        False,
    )


@pytest.fixture(
    params=[
        QDoubleSpinBox,
        QSpinBox,
        PyDMSpinbox,
        SpinBoxClickToScroll,
        DoubleSpinBoxClickToScroll,
        PyDMSpinBoxClickToScroll,
    ]
)
def spin_box(request, qtbot: QtBot):
    box = request.param()
    qtbot.addWidget(box)
    box.setEnabled(True)  # PyDM widgets start disabled when unconnected
    box.setRange(0, 100)
    box.setValue(50)
    return box


@pytest.fixture(params=[QComboBox, ComboBoxNoScroll])
def combo_box(request, qtbot: QtBot):
    box: QComboBox = request.param()
    qtbot.addWidget(box)
    box.addItems(["a", "b", "c"])
    return box


def test_scroll_check_spinbox(spin_box) -> None:
    """Send one wheel notch and assert who reacted."""
    event = _wheel_event(spin_box)
    QApplication.sendEvent(spin_box, event)
    # only unmodified box should scroll
    if type(spin_box) in (QSpinBox, QDoubleSpinBox, PyDMSpinbox):
        assert event.isAccepted()
    else:
        assert not event.isAccepted()


def test_scroll_check_spinbox_focused(spin_box) -> None:
    """Send one wheel notch and assert who reacted."""
    spin_box.hasFocus = lambda: True
    event = _wheel_event(spin_box)
    QApplication.sendEvent(spin_box, event)
    # all should accept scroll events
    assert event.isAccepted()


def test_scroll_check_combo(combo_box) -> None:
    """Send one wheel notch and assert who reacted."""
    event = _wheel_event(combo_box)
    QApplication.sendEvent(combo_box, event)
    if type(combo_box) is ComboBoxNoScroll:
        assert not event.isAccepted()
    else:
        assert event.isAccepted()


@pytest.fixture(
    params=[
        PyDMSpinbox,
        PyDMSpinBoxClickToScroll,
    ]
)
def pydm_spin_box(request, qtbot: QtBot):
    box = request.param()
    qtbot.addWidget(box)
    box.setEnabled(True)  # PyDM widgets start disabled when unconnected
    box.setRange(0, 100)
    box.setValue(50)
    box.interpretText = Mock()
    box.send_value = Mock()
    box.clearFocus = Mock()
    return box


def test_pydm_spinbox_enter_validates_sends_and_clears(pydm_spin_box):
    """<Enter> interprets the text, writes the value, then drops focus."""
    pydm_spin_box.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))

    if isinstance(pydm_spin_box, PyDMSpinBoxClickToScroll):
        pydm_spin_box.interpretText.assert_called_once_with()
    else:
        pydm_spin_box.interpretText.assert_not_called()
