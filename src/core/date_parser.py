from datetime import datetime
from typing import Tuple, Optional

class DateParser:
    """Parses month strings into date ranges."""
    
    MONTH_NAMES = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9, 'sept': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    @classmethod
    def parse_month(cls, month_str: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Parse month string to start and end dates."""
        if not month_str:
            return None, None
        
        now = datetime.now()
        month_lower = month_str.lower().strip()
        
        try:
            # Handle relative months
            if month_lower in ['this_month', 'this month', 'current month']:
                return cls._get_current_month(now)
            
            elif month_lower in ['last_month', 'last month', 'previous month']:
                return cls._get_last_month(now)
            
            # Handle named months
            elif month_lower in cls.MONTH_NAMES:
                return cls._get_named_month(month_lower, now.year)
            
            # Handle "Month Year" format
            elif " " in month_lower:
                return cls._parse_month_year(month_lower, now.year)
            
            # Handle "YYYY-MM" format
            elif "-" in month_str:
                return cls._parse_iso_format(month_str)
            
            return None, None
            
        except Exception:
            return None, None
    
    @classmethod
    def _get_current_month(cls, now: datetime) -> Tuple[datetime, datetime]:
        """Get current month date range."""
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end
    
    @classmethod
    def _get_last_month(cls, now: datetime) -> Tuple[datetime, datetime]:
        """Get last month date range."""
        if now.month == 1:
            start = now.replace(year=now.year - 1, month=12, day=1, 
                               hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now.replace(month=now.month - 1, day=1, 
                               hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, end
    
    @classmethod
    def _get_named_month(cls, month_name: str, year: int) -> Tuple[datetime, datetime]:
        """Get date range for named month."""
        month_num = cls.MONTH_NAMES[month_name]
        start = datetime(year, month_num, 1)
        if month_num == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month_num + 1, 1)
        return start, end
    
    @classmethod
    def _parse_month_year(cls, month_year: str, default_year: int) -> Tuple[datetime, datetime]:
        """Parse 'Month Year' format."""
        parts = month_year.split()
        month_name = parts[0]
        year = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else default_year
        
        if month_name in cls.MONTH_NAMES:
            return cls._get_named_month(month_name, year)
        
        return None, None
    
    @classmethod
    def _parse_iso_format(cls, month_str: str) -> Tuple[datetime, datetime]:
        """Parse 'YYYY-MM' format."""
        year, month = month_str.split("-")
        year, month = int(year), int(month)
        
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        
        return start, end