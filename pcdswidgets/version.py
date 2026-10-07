try:
    from ._version import version, version_tuple
except ImportError:
    version = "0.0.0"
    version_tuple = (0, 0, 0)
