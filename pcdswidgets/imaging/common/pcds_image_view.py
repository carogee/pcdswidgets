"""
PCDSImageView: a PyDMImageView subclass that reduces camera network traffic.

"""

import logging

from pydm.widgets import PyDMImageView

logger = logging.getLogger(__name__)


class PCDSImageView(PyDMImageView):
    """PyDMImageView with a stream pausing interface

    Pausing: owning widget uses visibility hooks to pause/resume to mitigate
    heavy image-stream subscriptions.
    """

    def __init__(self, parent=None, image_channel=None, width_channel=None) -> None:
        # Start paused: the stream is only established once the owning widget
        # calls resume() (typically on its first showEvent). This prevents
        # background tabs/docks -- which never receive a showEvent -- from
        # quietly running a full-rate camonitor.
        self._paused: bool = True
        self._stream_connected: bool = False

        super().__init__(parent=parent, image_channel=image_channel, width_channel=width_channel)

    def _apply_stream_state(self) -> None:
        """Connect or disconnect the heavy image-stream channels."""
        connected = not self._paused
        if connected == self._stream_connected:
            logger.debug("stream already %s; skipping", "connected" if connected else "disconnected")
            return
        logger.debug("stream -> %s", "connect" if connected else "disconnect")
        for channel in (self._imagechannel, self._widthchannel):
            if channel is None:
                continue
            try:
                channel.connect() if connected else channel.disconnect()
            except Exception:
                logger.exception("Failed to %s stream channel", "connect" if connected else "disconnect")
        self._stream_connected = connected

    def pause(self) -> None:
        """Tear down the image stream (called when the view is hidden)."""
        logger.debug("pause()")
        self._paused = True
        self._apply_stream_state()

    def resume(self) -> None:
        """Restore the image stream."""
        logger.debug("resume()")
        self._paused = False
        self._apply_stream_state()

    # -- Overrides --------------------------------------------------------

    def setImageChannel(self, value) -> None:
        logger.debug("setImageChannel(%s)", value)
        super().setImageChannel(value)
        self._stream_connected = True  # super() just established a connection
        self._apply_stream_state()

    def setWidthChannel(self, value) -> None:
        logger.debug("setWidthChannel(%s)", value)
        super().setWidthChannel(value)
        self._stream_connected = True  # super() just established a connection
        self._apply_stream_state()
