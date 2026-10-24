"""dnsguard - a small DNS filtering service with a query log and a control socket."""

from .service import VERSION

__version__ = VERSION
__all__ = ["VERSION", "__version__"]
