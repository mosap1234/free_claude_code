"""Web server tool / web_fetch knobs (derived views of :class:`~config.settings.Settings`)."""

from pydantic import BaseModel, ConfigDict, field_validator


def normalize_web_fetch_allowed_schemes(v: str) -> str:
    """Normalize and validate comma-separated schemes (shared with flat Settings validation)."""
    schemes = [part.strip().lower() for part in v.split(",") if part.strip()]
    if not schemes:
        raise ValueError("web_fetch_allowed_schemes must list at least one scheme")
    for scheme in schemes:
        if not scheme.isascii() or not scheme.isalpha():
            raise ValueError(
                f"Invalid URL scheme in web_fetch_allowed_schemes: {scheme!r}"
            )
    return ",".join(schemes)


class WebFetchSettings(BaseModel):
    """Bundled SSRF-facing web_fetch guards (mirrors flat Settings fields)."""

    model_config = ConfigDict(frozen=True)

    enable_web_server_tools: bool
    web_fetch_allowed_schemes: str
    web_fetch_allow_private_networks: bool

    @field_validator("web_fetch_allowed_schemes")
    @classmethod
    def validate_web_fetch_allowed_schemes(cls, v: str) -> str:
        return normalize_web_fetch_allowed_schemes(v)

    def allowed_scheme_set(self) -> frozenset[str]:
        """Normalized schemes allowed for ``web_fetch``."""
        return frozenset(
            part.strip().lower()
            for part in self.web_fetch_allowed_schemes.split(",")
            if part.strip()
        )
