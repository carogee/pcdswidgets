============================
CameraViewerStretch
============================
.. image:: /_static/catalog/camera_viewer_stretch.png

``CameraViewerStretch`` is useful for building a camera-specific control panel
where the main preview remains visible while auxiliary controls stay grouped in
a hidable side panel.

Important macros and properties
-------------------------------

``cam_prefix``
    The base prefix for the camera PVs, such as ``LAS:CAM:``. This is the main
    camera identifier used by the image view and is propagated to adopted child
    widgets so they point at the same detector.

``nickname``
    The text displayed at the top of the widget. This is the visible name shown
    in the title/header area of the viewer.

``stream_plugin``
    The AreaDetector stream plugin being displayed. The default is
    ``:IMAGE1:`` and it includes the conventional leading and trailing colons so
    the full stream PV can be changed cleanly while keeping the plugin name
    structure intact.

``img_protocol``
    The protocol used for the stream PV, typically ``ca://`` by default. This is
    appended in front of the image PV address and is useful when switching to
    ``pva://`` for a PVA-based stream.

``suffix_waveform_channel``
    The waveform field suffix used by the image source. The default is
    ``ArrayData`` for the standard CA-based workflow.

``suffix_width_channel``
    The width field suffix used by the image source. The default is
    ``ArraySize0_RBV`` for CA-based streams. This is mainly relevant for the
    width source when the image plugin is not using the standard CA naming
    convention; for PVA the width does not need to be matched the same way.

Sidebar behavior
----------------

The title shown at the top of each collapsible section is taken from the adopted
child widget's ``nickname`` property. In other words, the section header is the
sub-widget's ``nickname`` label, not a separate viewer label. If a widget is
being set up in Designer and does not already expose a ``nickname`` property, add
it as a dynamic property so the sidebar title can be customized.

The order of adopted widgets in the sidebar is determined by the original widget
positions in the design, using their ``y`` coordinate. In practice, placement
otherwise has no effect on the final sidebar ordering. This can look a bit ugly
in the Designer preview when a large number of widgets are present, but the final
runtime layout is still sorted by that coordinate.



.. automodule:: pcdswidgets.imaging.common.camera_viewer_stretch
.. autoclass:: CameraViewerStretch
    :members:
