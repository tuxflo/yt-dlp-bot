"""Single source of truth for the application version.

Both services share this package, so logging it on startup makes a version skew
between the separately built images visible at a glance.
"""

__version__ = '1.8.0'
