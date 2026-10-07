============================
Installation
============================

``pcdswidgets`` is packaged using standard tools and can be installed with standard tools.
We maintain both ``pypi`` and ``conda-forge`` builds.

Pick your favorite:

- ``pip install pcdswidgets``
- ``conda install pcdswidgets``
- ``uv add pcdswidgets``
- ``pixi add pcdswidgets``

You can also build and install ``pcdswidgets`` directly from source using ``GitHub``.
Source tarballs for each tag are distributed on the
`release page <https://github.com/pcdshub/pcdswidgets/releases>`_,
or you can use ``git`` to clone the source, and then use your favorite install tool.

Note that the designer support for ``pcdswidgets`` relies on the ``designer`` support in ``pydm``,
which relies on the designer support in ``pyqt`` (or ``pyside``),
which can differ from distribution to distribution.

Specifically, the "python" designer plugin must be included.
