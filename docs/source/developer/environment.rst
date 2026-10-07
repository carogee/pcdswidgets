=======================================
Development Environment
=======================================

.. tip::
    If you just want to create a widget, you might not need a development environment.
    See :doc:`create_composite_widget`

A ``pixi`` environment is included here.
This is the shared context in which we build, develop, and test ``pcdswidgets``.

.. note::
    You *must* have ``pixi`` on your path for this to work. That means that ``pixi`` is a developer requirement.

At lcls you can get this via ctrlenv-pathmunge::

    source ctrlenv_setup.sh
    ctrlenv-pathmunge
    pixi --version

You can create the environment with ``pixi run install``.
If this is the first ``pixi`` command you've run with this repo, it will build the environment for you,
and then run the post-env install script to set up the designer plugin, which is the ``install`` task in this repo.

You can also just ``make``, which will run all the important build steps,
or ``make pixi`` for just the ``pixi`` step.

This will create a ``pixi`` environment under the ``.pixi`` folder that will be ready to go
to help you run designer and test your custom widgets.
To work, this requires a pre-compiled designer python plugin,
which is tricky to set up properly.

If you are not at LCLS, you will need to edit the ``pixi_scripts/install.sh`` script to point to your plugin source,
or you'll need to copy it into your environment manually,
or you'll need to actually figure out why all the conda-forge pyqt builds stopped including this automatically,
or you'll need to pick a build that has this problem fixed.

You can run ``pixi install`` (or, ``make pixi``)
to update the environment with any new widgets you've added since the last run.

When you are ready to test, you can use ``pixi run designer`` to
make sure your widgets are exporting cleanly in an editable way in designer.

You can also use ``pixi run pydm`` to launch a version of ``pydm`` that includes
your new widgets.

Each of these ``pixi`` commands will build or update the environment as needed.

You can alternatively build your own environment:

- ``pip install -e .``

or

- ``uv sync``

or whatever your favorite method is.

.. warning::
    We can currently only run designer with custom widgets on our Rocky 9 OS machines at LCLS.
    This is due to complications in the build process where our existing compiled binary for the plugin
    is not cross-compiled, and therefore needs exact versions of ``Python`` and ``PyQt`` on the specific architecture.
