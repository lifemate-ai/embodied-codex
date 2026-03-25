"""Tests for MCP tool schemas."""

from memory_mcp.server import _category_schema


class TestCategorySchema:
    """Category schema should stay open-ended."""

    def test_category_schema_is_open_ended(self):
        """Category uses examples, not a closed enum."""
        schema = _category_schema("Category of memory", default="daily")

        assert schema["type"] == "string"
        assert schema["default"] == "daily"
        assert "enum" not in schema
        assert "relationship" in schema["examples"]
        assert "project" in schema["examples"]
