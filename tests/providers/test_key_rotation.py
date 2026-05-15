"""Tests for providers/key_rotation.py — multi-API-key round-robin rotation."""

from providers.key_rotation import KeyRotator, parse_api_keys


class TestParseApiKeys:
    """Tests for parse_api_keys comma-delimited key parser."""

    def test_single_key(self) -> None:
        assert parse_api_keys("abc123") == ["abc123"]

    def test_multiple_keys(self) -> None:
        assert parse_api_keys("key1,key2,key3") == ["key1", "key2", "key3"]

    def test_whitespace_stripped(self) -> None:
        assert parse_api_keys(" key1 , key2 , key3 ") == ["key1", "key2", "key3"]

    def test_empty_string(self) -> None:
        assert parse_api_keys("") == []

    def test_whitespace_only(self) -> None:
        assert parse_api_keys("   ") == []

    def test_trailing_comma(self) -> None:
        assert parse_api_keys("key1,key2,") == ["key1", "key2"]

    def test_leading_comma(self) -> None:
        assert parse_api_keys(",key1,key2") == ["key1", "key2"]

    def test_consecutive_commas(self) -> None:
        assert parse_api_keys("key1,,key2") == ["key1", "key2"]

    def test_real_nvidia_key_format(self) -> None:
        key = "nvapi-abc123def456"
        assert parse_api_keys(key) == [key]

    def test_multiple_real_keys(self) -> None:
        keys = "nvapi-abc123,nvapi-def456,nvapi-ghi789"
        assert parse_api_keys(keys) == ["nvapi-abc123", "nvapi-def456", "nvapi-ghi789"]


class TestKeyRotator:
    """Tests for KeyRotator round-robin key selection."""

    def test_single_key_always_returns_same(self) -> None:
        rotator = KeyRotator(["key1"])
        assert rotator.next_key() == "key1"
        assert rotator.next_key() == "key1"
        assert rotator.next_key() == "key1"

    def test_round_robin_two_keys(self) -> None:
        rotator = KeyRotator(["key1", "key2"])
        assert rotator.next_key() == "key1"
        assert rotator.next_key() == "key2"
        assert rotator.next_key() == "key1"
        assert rotator.next_key() == "key2"

    def test_round_robin_three_keys(self) -> None:
        rotator = KeyRotator(["a", "b", "c"])
        assert [rotator.next_key() for _ in range(6)] == ["a", "b", "c", "a", "b", "c"]

    def test_primary_key(self) -> None:
        rotator = KeyRotator(["key1", "key2", "key3"])
        assert rotator.primary_key == "key1"

    def test_all_keys(self) -> None:
        keys = ["key1", "key2", "key3"]
        rotator = KeyRotator(keys)
        assert rotator.all_keys == ("key1", "key2", "key3")

    def test_len(self) -> None:
        rotator = KeyRotator(["a", "b", "c"])
        assert len(rotator) == 3

    def test_empty_keys_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="at least one key"):
            KeyRotator([])

    def test_many_rotations(self) -> None:
        """Verify rotation wraps correctly over many calls."""
        rotator = KeyRotator(["a", "b", "c"])
        keys = [rotator.next_key() for _ in range(99)]
        # Every 3rd key should be the same
        assert keys[0] == keys[3] == keys[6] == "a"
        assert keys[1] == keys[4] == keys[7] == "b"
        assert keys[2] == keys[5] == keys[8] == "c"
