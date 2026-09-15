"""Errors with concise, user-facing Orinoco Lite messages."""


class OrinocoError(RuntimeError):
    """Base class for a fail-closed public-interface error."""


class ConfigurationError(OrinocoError):
    """The downstream configuration or lock is invalid."""


class IntegrityError(OrinocoError):
    """A release artifact or resources resource failed verification."""


class DriverError(OrinocoError):
    """A package driver could not be invoked successfully."""
