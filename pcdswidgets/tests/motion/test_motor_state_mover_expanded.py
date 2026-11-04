"""Expanded state mover: layout discovery from the IOC, PV addresses, tab visibility."""

from __future__ import annotations

import itertools
import logging

import numpy as np
import pytest
from pydm.widgets.label import PyDMLabel
from pytestqt.qtbot import QtBot

from pcdswidgets.motion.common import motor_state_mover_expanded as module
from pcdswidgets.motion.common.motor_state_mover_expanded import (
    MotorStateMoverExpanded,
    MotorStateMoverExpandedPMPS,
    _decode_tokens,
    _index_width,
)

DEVICE = "TST:MOTION"


class FakeChannel:
    """Stands in for PyDMChannel: records the address and feeds no data."""

    created: list[FakeChannel] = []

    def __init__(self, address=None, value_slot=None, **kwargs):
        self.address = address
        self.value_slot = value_slot
        self.disconnected = False
        FakeChannel.created.append(self)

    def connect(self):
        pass

    def disconnect(self):
        self.disconnected = True


@pytest.fixture(autouse=True)
def fake_channels(monkeypatch):
    FakeChannel.created = []
    monkeypatch.setattr(module, "PyDMChannel", FakeChannel)


@pytest.fixture
def mover(qtbot: QtBot) -> MotorStateMoverExpanded:
    widget = MotorStateMoverExpanded()
    qtbot.addWidget(widget)
    return widget


def tab_names(widget: MotorStateMoverExpanded) -> list[str]:
    return [widget.tabs.tabText(i) for i in range(widget.tabs.count())]


def channels_of(root) -> set[str]:
    return {label.channel for label in root.findChildren(PyDMLabel) if label.channel}


def publish(widget: MotorStateMoverExpanded, tokens=None, count=None, digits=None) -> None:
    """Deliver the metadata the IOC would publish."""
    if tokens is not None:
        widget._on_pv_tokens(tokens)
    if count is not None:
        widget._on_pv_state_count(count)
    if digits is not None:
        widget._on_pv_state_digits(digits)


def flush(widget: MotorStateMoverExpanded) -> None:
    """Metadata updates rebuild the tabs on a zero-delay timer; do it now."""
    widget._refresh_timer.stop()
    widget._rebuild_grid()


# helpers


@pytest.mark.parametrize(
    "max_index, width",
    [(0, 2), (1, 2), (9, 2), (10, 3), (99, 3), (100, 4)],
)
def test_index_width_matches_pytmc_padding(max_index, width):
    assert _index_width(max_index) == width


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, []),
        (["M1", "M2", "M3"], ["M1", "M2", "M3"]),
        ("M1, M2,M3", ["M1", "M2", "M3"]),
        (["M1,M2", "M3"], ["M1", "M2", "M3"]),
        ("M1,,M2", ["M1", "M2"]),
        (b"M1,M2\x00", ["M1", "M2"]),
        ([77, 49, 44, 77, 50, 0, 0], ["M1", "M2"]),
        (np.array([77, 49, 44, 77, 50, 0], dtype=np.uint8), ["M1", "M2"]),
        ([], []),
    ],
)
def test_decode_tokens(value, expected):
    assert _decode_tokens(value) == expected


# metadata published by the IOC


def test_metadata_is_read_from_the_pytmc_records(mover):
    mover.device = DEVICE

    addresses = {chan.address for chan in FakeChannel.created}
    assert {
        f"ca://{DEVICE}:STATE:MOTOR_TOKENS_RBV.VAL$",
        f"ca://{DEVICE}:STATE:STATE_COUNT_RBV",
        f"ca://{DEVICE}:STATE:STATE_INDEX_DIGITS_RBV",
    } <= addresses


def test_changing_device_drops_the_old_metadata(mover):
    mover.device = DEVICE
    publish(mover, tokens=["M1", "M2"], count=5, digits=3)
    metadata = {
        f"ca://{DEVICE}:STATE:MOTOR_TOKENS_RBV.VAL$",
        f"ca://{DEVICE}:STATE:STATE_COUNT_RBV",
        f"ca://{DEVICE}:STATE:STATE_INDEX_DIGITS_RBV",
    }
    first = [c for c in FakeChannel.created if c.address in metadata]
    assert len(first) == 3

    mover.device = "OTHER:MOTION"

    assert all(chan.disconnected for chan in first)
    assert mover._pv_tokens is None
    assert mover._pv_state_count is None
    assert mover._pv_state_digits is None
    assert any(c.address == "ca://OTHER:MOTION:STATE:MOTOR_TOKENS_RBV.VAL$" for c in FakeChannel.created)


def test_unusable_metadata_values_are_ignored(mover):
    mover.device = DEVICE
    publish(mover, tokens=["M1"], count=5, digits=3)

    mover._on_pv_state_count("not a number")
    mover._on_pv_state_digits(None)
    assert mover._pv_state_count == 5
    assert mover._pv_state_digits == 3

    mover._on_pv_state_count(0)
    mover._on_pv_state_digits(-1)
    assert mover._pv_state_count is None
    assert mover._pv_state_digits is None


# IOC values against the screen properties


def test_ioc_tokens_used_when_property_is_empty(mover):
    publish(mover, tokens=["M1", "M2", "M3"])
    assert mover._tokens == ["M1", "M2", "M3"]


def test_property_tokens_used_as_given_without_ioc_metadata(mover):
    mover.deviceTokens = "D1M1, D3M1"
    assert mover._tokens == ["D1M1", "D3M1"]


def test_property_tokens_keep_their_order_and_drop_unknown(mover):
    publish(mover, tokens=["M1", "M2", "M3"])
    mover.deviceTokens = "M3,X9,M1"

    assert mover._tokens == ["M3", "M1"]
    assert any("X9" in note for note in mover._notes)
    assert "X9" in mover._config_tab.toolTip()


def test_ioc_count_used_when_property_is_unset(mover):
    publish(mover, count=10)
    assert mover._effective_state_count() == 10


def test_property_count_below_the_ioc_count_is_kept(mover):
    publish(mover, count=10)
    mover.stateCount = 4
    assert mover._effective_state_count() == 4
    assert not mover._notes


def test_property_count_above_the_ioc_count_is_capped(mover):
    publish(mover, count=10)
    mover.stateCount = 20

    assert mover._effective_state_count() == 10
    assert any("20" in note and "10" in note for note in mover._notes)


def test_property_count_used_as_given_without_ioc_metadata(mover):
    mover.stateCount = 7
    assert mover._effective_state_count() == 7
    assert not mover._notes


def test_mismatch_is_noted_once(mover):
    publish(mover, count=10)
    mover.stateCount = 20
    mover._effective_state_count()
    mover._effective_state_count()
    assert len(mover._notes) == 1


@pytest.mark.parametrize("digits, count, expected", [(3, 5, 3), (None, 9, 2), (None, 10, 3)])
def test_state_index_width(mover, digits, count, expected):
    publish(mover, count=count, digits=digits)
    assert mover._state_index_width() == expected


def test_motor_index_follows_the_ioc_order(mover):
    publish(mover, tokens=["M1", "M2", "M3"])
    assert mover._motor_index("M3", position=0) == 3
    assert mover._motor_index("X9", position=4) == 5


# PV addresses the screen reads


def test_state_grid_addresses_use_the_published_index_width(mover):
    mover.device = DEVICE
    publish(mover, tokens=["M1", "M2", "M3"], count=10, digits=3)
    flush(mover)

    expected = {
        f"ca://{DEVICE}:STATE:{token}:{index:03d}:SETPOINT_RBV"
        for token, index in itertools.product(("M1", "M2", "M3"), range(1, 11))
    } | {f"ca://{DEVICE}:STATE:M1:{index:03d}:NAME_RBV" for index in range(1, 11)}
    assert channels_of(mover._config_tab) == expected


def test_state_grid_addresses_follow_a_narrower_published_width(mover):
    mover.device = DEVICE
    publish(mover, tokens=["M1"], count=3, digits=2)
    flush(mover)

    assert f"ca://{DEVICE}:STATE:M1:01:SETPOINT_RBV" in channels_of(mover._config_tab)


def test_diagnostics_addresses_use_the_motor_index(mover):
    mover.device = DEVICE
    publish(mover, tokens=["M1", "M2", "M3"])
    flush(mover)

    assert channels_of(mover._diag_tab) == {
        f"ca://{DEVICE}:{leaf}:{n:02d}_RBV" for leaf in ("MOVING", "STATUS") for n in (1, 2, 3)
    }
    assert {c.address for c in FakeChannel.created} >= {f"ca://{DEVICE}:M{n}:bError_RBV" for n in (1, 2, 3)}


# which tabs exist


def test_only_the_normal_tab_without_a_device(mover):
    assert tab_names(mover) == ["Normal"]


def test_tabs_follow_the_published_metadata(mover, qtbot):
    mover.device = DEVICE
    assert tab_names(mover) == ["Normal"]

    publish(mover, tokens=["M1", "M2", "M3"])
    qtbot.waitUntil(lambda: tab_names(mover) == ["Normal", "Diagnostics"])

    publish(mover, count=10)
    qtbot.waitUntil(lambda: tab_names(mover) == ["Normal", "Configuration", "Diagnostics"])

    publish(mover, tokens=[])
    qtbot.waitUntil(lambda: tab_names(mover) == ["Normal"])


def test_tabs_from_properties_alone_for_older_iocs(mover):
    mover.device = DEVICE
    mover.deviceTokens = "M1,M2"
    mover.stateCount = 3
    assert tab_names(mover) == ["Normal", "Configuration", "Diagnostics"]


def test_pmps_configuration_needs_only_the_device(qtbot):
    widget = MotorStateMoverExpandedPMPS()
    qtbot.addWidget(widget)
    widget.device = DEVICE
    assert tab_names(widget) == ["Normal", "Configuration"]


# warning when the metadata never arrives


def test_warning_names_the_missing_pv(mover, caplog):
    mover.device = DEVICE
    with caplog.at_level(logging.WARNING, logger=module.logger.name):
        mover._warn_no_metadata()

    assert "MOTOR_TOKENS_RBV.VAL$" in caplog.text
    assert "STATE_COUNT_RBV" in caplog.text


def test_no_warning_when_the_metadata_is_there(mover, caplog):
    mover.device = DEVICE
    publish(mover, tokens=["M1"], count=3)
    with caplog.at_level(logging.WARNING, logger=module.logger.name):
        mover._warn_no_metadata()

    assert not caplog.records


def test_warning_fires_when_nothing_arrives(mover, monkeypatch, qtbot, caplog):
    monkeypatch.setattr(module, "_METADATA_TIMEOUT_MS", 10)
    with caplog.at_level(logging.WARNING, logger=module.logger.name):
        mover.device = DEVICE
        qtbot.waitUntil(lambda: "no usable" in caplog.text, timeout=2000)
