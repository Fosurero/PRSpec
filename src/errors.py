"""Exception types raised by PRSpec.

Every failure that is worth distinguishing from a generic ``Exception`` gets a
type here so callers (and the CLI) can react to it instead of guessing from a
message string.
"""


class PRSpecError(Exception):
    """Base class for every PRSpec-specific failure."""


class ConfigError(PRSpecError):
    """The configuration file is missing, unreadable, or malformed."""


class FetchError(PRSpecError):
    """A remote artefact could not be retrieved."""


class SpecFetchError(FetchError):
    """No specification source could be fetched for an EIP."""


class CodeFetchError(FetchError):
    """No implementation file could be fetched for an EIP/client pair."""


class AnalysisError(PRSpecError):
    """An LLM backend returned a response that cannot be used."""
