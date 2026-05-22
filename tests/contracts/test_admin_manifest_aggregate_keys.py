from __future__ import annotations


def test_admin_manifest_field_keys_remain_unique_after_section_split() -> None:
    from api.admin_manifest import FIELD_BY_KEY, FIELDS

    assert FIELD_BY_KEY
    assert len(FIELD_BY_KEY) == len(FIELDS)
