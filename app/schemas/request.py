"""Request schemas.

Defines the shape of incoming API requests and validates them before
they reach any agent or service.
"""

from pydantic import BaseModel, field_validator


class QueryRequest(BaseModel):
    """Input payload for POST /query."""

    query: str

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, v: str) -> str:
        """Reject empty or whitespace-only queries early."""
        if not v.strip():
            raise ValueError("query must not be empty or whitespace")
        return v.strip()
