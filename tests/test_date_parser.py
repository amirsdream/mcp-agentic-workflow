import pytest
from datetime import datetime
from src.core.date_parser import DateParser

class TestDateParser:
    """Test cases for DateParser."""
    
    def test_parse_this_month(self):
        """Test parsing 'this month'."""
        start, end = DateParser.parse_month("this month")
        assert start is not None
        assert end is not None
        assert start.day == 1
        assert start < end
    
    def test_parse_last_month(self):
        """Test parsing 'last month'."""
        start, end = DateParser.parse_month("last month")
        assert start is not None
        assert end is not None
        assert start.day == 1
        assert start < end
    
    def test_parse_named_month(self):
        """Test parsing named months."""
        start, end = DateParser.parse_month("January")
        assert start is not None
        assert end is not None
        assert start.month == 1
        assert start.day == 1
    
    def test_parse_month_year(self):
        """Test parsing 'Month Year' format."""
        start, end = DateParser.parse_month("January 2024")
        assert start is not None
        assert end is not None
        assert start.year == 2024
        assert start.month == 1
    
    def test_parse_iso_format(self):
        """Test parsing ISO format."""
        start, end = DateParser.parse_month("2024-01")
        assert start is not None
        assert end is not None
        assert start.year == 2024
        assert start.month == 1
    
    def test_parse_invalid_month(self):
        """Test parsing invalid month returns None."""
        start, end = DateParser.parse_month("invalid")
        assert start is None
        assert end is None
    
    def test_parse_empty_month(self):
        """Test parsing empty string returns None."""
        start, end = DateParser.parse_month("")
        assert start is None
        assert end is None

