"""Capabilities understood by the versioned API boundary."""

from enum import StrEnum


class Capability(StrEnum):
    PRODUCTION_READ = "production.read"
    PRODUCTION_CONTROL = "production.control"
    PRODUCTION_WRITE = "production.write"
    RESEARCH_READ = "research.read"
    RESEARCH_MUTATE = "research.mutate"


# API consumers must opt in explicitly; development must never imply write access.
DEVELOPMENT_DENIED_CAPABILITIES = frozenset({Capability.PRODUCTION_WRITE})
