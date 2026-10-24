"""Toney - a terminal UI that manages the dnsguard DNS filtering service.

The service and the UI are separate programs.  They only ever talk through
the Unix domain socket control protocol described in the project docs.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
