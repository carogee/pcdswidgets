===========================
Builds and File Generation
===========================

There are a large number of built and generated files in this module.
These are built largely using the python code in the ``pcdswidgets.builder`` submodule.
Developers usually don't need to dig into the details:
the important thing is to call ``make`` and everything will be good.

This page is a primer on the details you don't usually need to know
and the general motivation behind these tools.


What are we Building?
---------------------
From source ``.ui`` files edited in ``designer``,
we are building python files that define widgets
that can be imported and used at runtime.

Each file in the ``pcdswidgets/ui`` filetree
is used as a source for the build.

The following files are built or edited when we ``make``:

- ``pcdswidgets/generated/**/$widget_name_form.py`` (if ui changed)

  - These are direct code representations of the ``.ui`` file contents
  - This uses ``pyuic5`` under the hood.

- ``pcdswidgets/generated/**/$widget_name_base.py`` (if ui changed)

  - This adds some macro-handling features based on the ``pydm`` macros found in the ``.ui`` file.
  - It also adds some nice type-hinting of widgets defined in the ``.ui`` file.

- ``pcdswidgets/**/$widget_name.py`` (if missing)

  - This is the actual widget object that will be run.
  - Developers are encouraged to edit these.

- ``pcdswidgets/**/__init__.py`` (if missing)

  - This ensures that edited submodules are treated as real Python modules.

- ``pyproject.toml`` (if available widgets changed)

  - This makes sure each widget is included in ``designer``.

- ``pcdswidgets/generated/path_defs.py`` (if ``pyproject.toml`` changed)

  - This makes sure each widget is included in ``pcdswidgets-show``.


Why are we Building?
--------------------
- A lot of these steps could be done at runtime at some performance cost.
  Building them now saves that performance cost.
- The widget type hints are very useful for adding logic to screens.
- Editing ``pyproject.toml`` by hand is fraught and error-prone.


Why are we Comitting These? What about .gitignore?
--------------------------------------------------
This library is intended to be installed into a python environment.
There is no built-in support for extra actions to be taken during the installation of a python package.
You can add a build step to the distribution but the syntax is janky and annoying.

Much simpler is to commit all the generated files and let them always be included in the distribution.
This also should be an easy way for us to realize when we've made a mistake in editing the build code.


API Docs
--------

.. automodule:: pcdswidgets.builder.build
    :members:

.. automodule:: pcdswidgets.builder.designer_options
    :members:

.. automodule:: pcdswidgets.builder.designer_widget
    :members:

.. automodule:: pcdswidgets.builder.entrypoint_finder
    :members:

.. automodule:: pcdswidgets.builder.get_icon_options
    :members:

.. automodule:: pcdswidgets.builder.icon_options
    :members:

.. automodule:: pcdswidgets.builder.inits
    :members:

.. automodule:: pcdswidgets.builder.read_ui
    :members:

.. automodule:: pcdswidgets.builder.screen_paths
    :members:
