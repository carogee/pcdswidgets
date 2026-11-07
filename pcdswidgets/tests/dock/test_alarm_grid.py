"""Unit tests for the AlarmGrid widget."""

import textwrap

import pytest
from pytestqt.qtbot import QtBot

from pcdswidgets.common.dock.alarm_grid import (
    AlarmGrid,
    AlarmGridCell,
    DeviceStatus,
    StatusLevel,
)

CONFIG = textwrap.dedent(
    """
    columns: [EBD, FEE]
    rows:
      - section: OPTICS SYSTEM
      - category: Mirrors
        cells:
          FEE:
            - {name: MR1L0, channel: "loc://mr1l0?type=int&init=0"}
            - {name: MR2L0, channel: "loc://mr2l0?type=int&init=0"}
          EBD: []
      - category: Slits
        cells:
          EBD:
            - name: SL1K0
              channels:
                - "ca://SL1K0:POWER:MMS:TOP"
                - "ca://SL1K0:POWER:MMS:BOTTOM"
    """
)


def test_level_word_labels():
    from pcdswidgets.common.dock.alarm_grid import _LEVEL_TEXT

    assert _LEVEL_TEXT[StatusLevel.NO_ALARM] == "OK"
    assert _LEVEL_TEXT[StatusLevel.MINOR] == "Warning"
    assert _LEVEL_TEXT[StatusLevel.MAJOR] == "Error"
    assert _LEVEL_TEXT[StatusLevel.INVALID] == "Invalid"
    assert _LEVEL_TEXT[StatusLevel.DISCONNECTED] == "Disconnected"


def test_cell_aggregate_marks_empty(grid):
    # A cell with no devices renders blank (set_empty True); one with devices
    # does not.
    mirrors_ebd, mirrors_fee = grid._row_cells["Mirrors"]
    assert mirrors_ebd.aggregate._empty is True
    assert mirrors_fee.aggregate._empty is False


# -- StatusLevel: pure logic (no Qt) --------------------------------------
def test_from_severity_connected():
    assert StatusLevel.from_severity(0, True) is StatusLevel.NO_ALARM
    assert StatusLevel.from_severity(1, True) is StatusLevel.MINOR
    assert StatusLevel.from_severity(2, True) is StatusLevel.MAJOR
    assert StatusLevel.from_severity(3, True) is StatusLevel.INVALID


def test_from_severity_disconnected_or_unknown():
    assert StatusLevel.from_severity(0, False) is StatusLevel.DISCONNECTED
    assert StatusLevel.from_severity(2, False) is StatusLevel.DISCONNECTED
    assert StatusLevel.from_severity(None, True) is StatusLevel.DISCONNECTED


def test_worst():
    assert StatusLevel.worst([]) is StatusLevel.NO_ALARM
    assert StatusLevel.worst([StatusLevel.NO_ALARM, StatusLevel.NO_ALARM]) is StatusLevel.NO_ALARM
    assert StatusLevel.worst([StatusLevel.NO_ALARM, StatusLevel.MINOR]) is StatusLevel.MINOR
    assert StatusLevel.worst([StatusLevel.MINOR, StatusLevel.MAJOR, StatusLevel.NO_ALARM]) is StatusLevel.MAJOR
    assert StatusLevel.worst([StatusLevel.MAJOR, StatusLevel.INVALID]) is StatusLevel.INVALID
    # Disconnected ranks highest (as in typhos).
    assert StatusLevel.worst([StatusLevel.INVALID, StatusLevel.DISCONNECTED]) is StatusLevel.DISCONNECTED


# -- Cell aggregation -----------------------------------------------------
@pytest.fixture(scope="function")
def cell(qtbot: QtBot) -> AlarmGridCell:
    cell = AlarmGridCell()
    qtbot.addWidget(cell)
    return cell


def _add(cell: AlarmGridCell, name: str) -> DeviceStatus:
    device = DeviceStatus(name=name, channels=f"loc://{name}?type=int&init=0")
    cell.add_device(device)
    return device


def test_empty_cell_is_blank(cell):
    # No devices: the box is marked empty (renders blank regardless of level).
    cell.update_aggregate()
    assert cell.aggregate._empty is True


def test_aggregate_updates_with_child_severity(cell):
    d1 = _add(cell, "d1")
    d2 = _add(cell, "d2")

    # Both connected + ok -> NO_ALARM
    d1.set_status(0, True)
    d2.set_status(0, True)
    assert cell.aggregate.get_level() is StatusLevel.NO_ALARM

    # One goes MINOR -> MINOR
    d2.set_status(1, True)
    assert cell.aggregate.get_level() is StatusLevel.MINOR

    # One goes MAJOR -> MAJOR
    d1.set_status(2, True)
    assert cell.aggregate.get_level() is StatusLevel.MAJOR

    # One goes INVALID -> INVALID (distinct from MAJOR now)
    d2.set_status(3, True)
    assert cell.aggregate.get_level() is StatusLevel.INVALID

    # Disconnect everything -> DISCONNECTED
    d1.set_status(0, False)
    d2.set_status(0, False)
    assert cell.aggregate.get_level() is StatusLevel.DISCONNECTED


def test_multi_channel_device_is_worst(qtbot):
    # One device watching four PVs: its level is the worst across them.
    device = DeviceStatus(
        name="SL1K0",
        channels=[f"ca://SL1K0:POWER:MMS:{b}" for b in ("TOP", "BOTTOM", "NORTH", "SOUTH")],
    )
    for addr in device.addresses:
        device.set_status(0, True, address=addr)
    assert device.level is StatusLevel.NO_ALARM
    device.set_status(2, True, address=device.addresses[1])  # BOTTOM faults
    assert device.level is StatusLevel.MAJOR


# -- Full grid ------------------------------------------------------------
@pytest.fixture(scope="function")
def grid(qtbot: QtBot, tmp_path) -> AlarmGrid:
    config_file = tmp_path / "grid.yaml"
    config_file.write_text(CONFIG)
    grid = AlarmGrid()
    qtbot.addWidget(grid)
    grid.configFile = str(config_file)
    return grid


def test_grid_structure(grid):
    assert grid.configFile.endswith("grid.yaml")
    assert grid._columns == ["EBD", "FEE"]
    # Two category rows were built.
    assert set(grid._row_cells) == {"Mirrors", "Slits"}
    # One cell per column in each category row.
    assert len(grid._row_cells["Mirrors"]) == 2
    assert len(grid._row_cells["Slits"]) == 2


def test_grid_cell_device_counts(grid):
    mirrors_ebd, mirrors_fee = grid._row_cells["Mirrors"]
    assert len(mirrors_ebd.devices) == 0  # EBD empty
    assert len(mirrors_fee.devices) == 2  # MR1L0, MR2L0
    assert mirrors_ebd.aggregate._empty is True  # empty cell renders blank


def test_grid_channels_registered(grid):
    # One channel per PV: MR1L0, MR2L0 (1 each) + SL1K0 (2 blade PVs) = 4.
    assert len(grid.channels()) == 4


def test_slits_single_combined_entry(grid):
    # SL1K0 is a single device/menu entry even though it watches four PVs.
    slits_ebd = grid._row_cells["Slits"][0]
    assert len(slits_ebd.devices) == 1
    device = slits_ebd.devices[0]
    assert device.name == "SL1K0"
    assert len(device.addresses) == 2  # the two blade PVs in the test config
    menu = grid._row_menus["Slits"]
    device_actions = [a for a in menu.actions() if isinstance(a.data(), DeviceStatus)]
    assert len(device_actions) == 1
    assert device_actions[0].data().name == "SL1K0"


def test_category_menus_built(grid):
    # Every category has a dropdown menu; categories with devices have content.
    assert set(grid._row_menus) == {"Mirrors", "Slits"}
    assert grid._row_menus["Mirrors"].has_content()
    assert grid._row_menus["Slits"].has_content()


def test_menu_lists_devices_with_location(grid):
    menu = grid._row_menus["Mirrors"]
    # Device actions carry a DeviceStatus in their data(); both Mirrors devices
    # are in the FEE column.
    entries = [
        (a.data().name, a.data().location)
        for a in menu.actions()
        if isinstance(a.data(), DeviceStatus)
    ]
    assert entries == [("MR1L0", "FEE"), ("MR2L0", "FEE")]


def test_typhos_key_sets_device_name(qtbot, tmp_path):
    # A device with a `typhos:` key records the happi name and still builds /
    # triggers safely (open_detail is a logged no-op when typhos is absent).
    config_file = tmp_path / "typhos.yaml"
    config_file.write_text(
        textwrap.dedent(
            """
            columns: [FEE]
            rows:
              - category: Mirrors
                cells:
                  FEE:
                    - name: MR1K1
                      channels:
                        - "ca://MR1K1:BEND:MMS:PITCH"
                        - "ca://MR1K1:BEND:MMS:US"
                      typhos: mr1k1_bend
            """
        )
    )
    grid = AlarmGrid()
    qtbot.addWidget(grid)
    grid.configFile = str(config_file)

    device = grid._row_cells["Mirrors"][0].devices[0]
    assert device.name == "MR1K1"
    assert device.typhos_name == "mr1k1_bend"
    assert device.detail is None
    assert len(device.addresses) == 2
    # Triggering the menu action must not raise even without happi/typhos.
    menu = grid._row_menus["Mirrors"]
    for a in menu.actions():
        if isinstance(a.data(), DeviceStatus):
            a.trigger()


def test_cell_menu_shows_only_that_cell(grid):
    # Each cell's menu lists only that cell's (category + location) devices;
    # the whole-category menu still lists every column's devices.
    ebd_cell, fee_cell = grid._row_cells["Mirrors"]
    assert not grid._cell_menus[ebd_cell].has_content()  # EBD is empty
    fee_menu = grid._cell_menus[fee_cell]
    names = [a.data().name for a in fee_menu.actions() if isinstance(a.data(), DeviceStatus)]
    assert names == ["MR1L0", "MR2L0"]
    # Category-wide menu still has the same (here only FEE has devices).
    cat_names = [
        a.data().name for a in grid._row_menus["Mirrors"].actions() if isinstance(a.data(), DeviceStatus)
    ]
    assert cat_names == ["MR1L0", "MR2L0"]


def test_menu_entry_triggers_open_detail(grid):
    menu = grid._row_menus["Mirrors"]
    device_actions = [a for a in menu.actions() if isinstance(a.data(), DeviceStatus)]
    assert len(device_actions) == 2
    # Triggering an action should reach its device's open_detail.  With no
    # ``detail`` configured in the test config, open_detail is a safe no-op, so
    # this exercises the full signal path without opening a window.
    for action in device_actions:
        action.trigger()  # must not raise


def test_menu_icons_refresh_on_show(grid):
    menu = grid._row_menus["Mirrors"]
    device_actions = [a for a in menu.actions() if isinstance(a.data(), DeviceStatus)]
    # Drive one device to OK and refresh the icons (what aboutToShow does).
    device_actions[0].data().set_status(0, True)
    menu._refresh_icons()
    assert not device_actions[0].icon().isNull()


def test_grid_rebuild_clears_old(grid, tmp_path):
    new_config = tmp_path / "grid2.yaml"
    new_config.write_text(
        textwrap.dedent(
            """
            columns: [A]
            rows:
              - category: Only
                cells:
                  A:
                    - {name: X, channel: "loc://x?type=int&init=0"}
            """
        )
    )
    grid.configFile = str(new_config)
    assert grid._columns == ["A"]
    assert set(grid._row_cells) == {"Only"}
    assert len(grid.channels()) == 1


# -- List view ------------------------------------------------------------
def _dev(grid: AlarmGrid, name: str) -> DeviceStatus:
    return next(d for d in grid._iter_devices() if d.name == name)


def _set(device: DeviceStatus, severity: int, connected: bool = True) -> None:
    for addr in device.addresses:
        device.set_status(severity, connected, address=addr)


def test_view_toggle_switches_stack(grid):
    assert grid._stack.currentIndex() == 0  # Grid by default
    grid._set_view(1)
    assert grid._stack.currentIndex() == 1
    grid._set_view(0)
    assert grid._stack.currentIndex() == 0


def test_list_default_sort_severity_desc(grid):
    _set(_dev(grid, "MR1L0"), 2)  # MAJOR
    _set(_dev(grid, "MR2L0"), 1)  # MINOR
    _set(_dev(grid, "SL1K0"), 0)  # NO_ALARM
    grid._refresh_list()
    assert [d.name for d in grid._row_devices] == ["MR1L0", "MR2L0", "SL1K0"]


def test_acknowledge_sinks_within_severity(grid):
    _set(_dev(grid, "MR1L0"), 2)  # MAJOR
    _set(_dev(grid, "MR2L0"), 2)  # MAJOR
    _set(_dev(grid, "SL1K0"), 0)
    _dev(grid, "MR1L0").acknowledge()
    grid._refresh_list()
    # Both MAJOR, but the acked one sinks below the unacked one.
    assert [d.name for d in grid._row_devices] == ["MR2L0", "MR1L0", "SL1K0"]
    assert _dev(grid, "MR1L0").ack_time is not None


def test_ack_all_count_and_action(grid):
    _set(_dev(grid, "MR1L0"), 2)
    _set(_dev(grid, "MR2L0"), 1)
    _set(_dev(grid, "SL1K0"), 0)  # OK -> not ackable
    grid._refresh_list()
    assert grid._ack_all_btn.text() == "Ack all (2)"
    assert grid._ack_all_btn.isEnabled()
    grid._acknowledge_all()
    assert _dev(grid, "MR1L0").acknowledged and _dev(grid, "MR2L0").acknowledged
    assert not _dev(grid, "SL1K0").acknowledged  # OK was never ackable
    assert grid._ack_all_btn.text() == "Ack all (0)"
    assert not grid._ack_all_btn.isEnabled()


def test_ack_clears_when_alarm_clears(grid):
    device = _dev(grid, "MR1L0")
    _set(device, 2)
    device.acknowledge()
    assert device.acknowledged
    _set(device, 0)  # alarm clears to OK
    assert not device.acknowledged
    assert device.ack_time is None


def test_ackable_only_when_alarmed(grid):
    _set(_dev(grid, "SL1K0"), 0)
    _set(_dev(grid, "MR1L0"), 2)
    assert not _dev(grid, "SL1K0").ackable
    assert _dev(grid, "MR1L0").ackable


def test_header_click_sorts_device_column(grid):
    grid._on_header_clicked(grid._COL_DEVICE)
    assert grid._sort_col == grid._COL_DEVICE and grid._sort_desc is False
    names = [d.name for d in grid._row_devices]
    assert names == sorted(names, key=str.lower)
    grid._on_header_clicked(grid._COL_DEVICE)  # toggle to descending
    assert grid._sort_desc is True
    names_desc = [d.name for d in grid._row_devices]
    assert names_desc == sorted(names, key=str.lower, reverse=True)


def test_device_name_click_opens_detail(grid, monkeypatch):
    grid._refresh_list()
    opened = []
    for device in grid._row_devices:
        monkeypatch.setattr(device, "open_detail", lambda d=device: opened.append(d.name))
    # Click the Device column of the first row.
    grid._on_cell_clicked(0, grid._COL_DEVICE)
    assert opened == [grid._row_devices[0].name]
    # Clicking another column does nothing.
    grid._on_cell_clicked(0, grid._COL_STATUS)
    assert opened == [grid._row_devices[0].name]


def test_filter_hides_nonmatching_rows(grid):
    grid._refresh_list()
    grid._apply_filter("MR1L0")
    visible = [
        d.name for row, d in enumerate(grid._row_devices) if not grid._table.isRowHidden(row)
    ]
    assert visible == ["MR1L0"]
    grid._apply_filter("")  # cleared -> all visible
    assert not any(grid._table.isRowHidden(r) for r in range(len(grid._row_devices)))
