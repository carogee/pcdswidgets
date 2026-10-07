# pcdswidgets
This is a widget library that uses the `pydm` framework to add additional `PyQt` widgets to the `pydm` ecosystem.

When `pcdswidgets` is installed in a `python` environment, it will provide:

- Additional widgets in `designer` via `pydm`'s widget entrypoint.
- The same additional widgets at runtime for use in `pydm` and `PyQt` displays.
- A command-line interface, `pcdswidgets-show`, for showing standalone windows with screens and widgets sourced from the module.

At `LCLS`, this is pre-installed on all environments that provide `designer`.

It is distributed via both `pypi` and `conda-forge`, so it is installable with `pip`, `conda`, `uv`, and `pixi`.

See the [latest docs](https://pcdshub.github.io/pcdswidgets) for more information.
