import pytest
from datetime import datetime, timedelta
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
        
        # Check it's actually this month
        now = datetime.now()
        assert start.year == now.year
        assert start.month == now.month
    
    def test_parse_last_month(self):
        """Test parsing 'last month'."""
        start, end = DateParser.parse_month("last month")
        assert start is not None
        assert end is not None
        assert start.day == 1
        assert start < end
        
        # Check it's actually last month
        now = datetime.now()
        expected_month = now.month - 1 if now.month > 1 else 12
        expected_year = now.year if now.month > 1 else now.year - 1
        assert start.month == expected_month
        assert start.year == expected_year
    
    def test_parse_named_month_current_year(self):
        """Test parsing named months for current year."""
        start, end = DateParser.parse_month("January")
        assert start is not None
        assert end is not None
        assert start.month == 1
        assert start.day == 1
        assert start.year == datetime.now().year
    
    def test_parse_named_month_short_form(self):
        """Test parsing short month names."""
        test_cases = [
            ("Jan", 1), ("Feb", 2), ("Mar", 3), ("Apr", 4),
            ("May", 5), ("Jun", 6), ("Jul", 7), ("Aug", 8),
            ("Sep", 9), ("Oct", 10), ("Nov", 11), ("Dec", 12)
        ]
        
        for month_name, expected_month in test_cases:
            start, end = DateParser.parse_month(month_name)
            assert start is not None
            assert end is not None
            assert start.month == expected_month
    
    def test_parse_month_year(self):
        """Test parsing 'Month Year' format."""
        start, end = DateParser.parse_month("January 2024")
        assert start is not None
        assert end is not None
        assert start.year == 2024
        assert start.month == 1
        assert start.day == 1
        
        # Test with short form
        start, end = DateParser.parse_month("Feb 2023")
        assert start.year == 2023
        assert start.month == 2
    
    def test_parse_iso_format(self):
        """Test parsing ISO format."""
        start, end = DateParser.parse_month("2024-01")
        assert start is not None
        assert end is not None
        assert start.year == 2024
        assert start.month == 1
        assert start.day == 1
        
        # Test December (edge case)
        start, end = DateParser.parse_month("2024-12")
        assert start.year == 2024
        assert start.month == 12
        assert end.year == 2025
        assert end.month == 1
    
    def test_parse_case_insensitive(self):
        """Test that parsing is case insensitive."""
        test_cases = ["JANUARY", "january", "January", "JaNuArY"]
        
        for month_str in test_cases:
            start, end = DateParser.parse_month(month_str)
            assert start is not None
            assert start.month == 1
    
    def test_parse_alternative_phrases(self):
        """Test alternative phrases for relative months."""
        # Test "current month"
        start1, end1 = DateParser.parse_month("current month")
        start2, end2 = DateParser.parse_month("this month")
        assert start1 == start2
        assert end1 == end2
        
        # Test "previous month"
        start1, end1 = DateParser.parse_month("previous month")
        start2, end2 = DateParser.parse_month("last month")
        assert start1 == start2
        assert end1 == end2
    
    def test_parse_invalid_month(self):
        """Test parsing invalid month returns None."""
        invalid_cases = [
            "invalid", "not-a-month", "month13", "2024-13", 
            "Jamuary", "Febtober", "", "   "
        ]
        
        for invalid_month in invalid_cases:
            start, end = DateParser.parse_month(invalid_month)
            assert start is None
            assert end is None
    
    def test_parse_none_month(self):
        """Test parsing None returns None."""
        start, end = DateParser.parse_month(None)
        assert start is None
        assert end is None
    
    def test_month_boundaries(self):
        """Test that month boundaries are correct."""
        start, end = DateParser.parse_month("February 2024")
        
        # February 2024 should end on March 1, 2024
        assert start == datetime(2024, 2, 1)
        assert end == datetime(2024, 3, 1)
        
        # Check that the range covers the whole month
        feb_29 = datetime(2024, 2, 29, 23, 59, 59)  # 2024 is leap year
        assert start <= feb_29 < end