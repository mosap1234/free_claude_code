"""Admin UI field manifest — aggregate of section field tuples."""

from __future__ import annotations

from api.admin.fields_diagnostics import FIELDS as _F_DIAG
from api.admin.fields_messaging import FIELDS as _F_MSG
from api.admin.fields_models import FIELDS as _F_MODELS
from api.admin.fields_providers import FIELDS as _F_PROV
from api.admin.fields_runtime_core import FIELDS as _F_RT_CORE
from api.admin.fields_runtime_flags import FIELDS as _F_RT_FLAGS
from api.admin.fields_smoke import FIELDS as _F_SMOKE
from api.admin.fields_thinking import FIELDS as _F_THINK
from api.admin.fields_voice import FIELDS as _F_VOICE
from api.admin.fields_web_tools import FIELDS as _F_WEB
from api.admin.manifest_types import (
    MASKED_SECRET,
    SECTIONS,
    ConfigFieldSpec,
    ConfigSectionSpec,
    FieldType,
    SourceType,
)

FIELDS: tuple[ConfigFieldSpec, ...] = (
    *_F_PROV,
    *_F_MODELS,
    *_F_THINK,
    *_F_RT_CORE,
    *_F_MSG,
    *_F_VOICE,
    *_F_RT_FLAGS,
    *_F_WEB,
    *_F_DIAG,
    *_F_SMOKE,
)

FIELD_BY_KEY = {field.key: field for field in FIELDS}

__all__ = [
    "FIELDS",
    "FIELD_BY_KEY",
    "MASKED_SECRET",
    "SECTIONS",
    "ConfigFieldSpec",
    "ConfigSectionSpec",
    "FieldType",
    "SourceType",
]
