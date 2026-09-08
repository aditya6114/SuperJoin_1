import re

# Currency patterns and normalization
CURRENCY_PATTERN = re.compile(r'(?:₹|INR|Rs\.?|\$|USD|€|EUR|£|GBP)', re.IGNORECASE)
CURRENCY_MAP = {
    "₹": "₹",
    "inr": "INR",
    "rs": "INR",
    "rs.": "INR",
    "$": "$",
    "usd": "USD",
    "€": "€",
    "eur": "EUR",
    "£": "£",
    "gbp": "GBP",
}

# Scale patterns and canonical terms
SCALE_PATTERN = re.compile(r'\b(?:million|billion|crore|crores|lakh|lakhs|thousand|thousands|trillion)\b', re.IGNORECASE)
SCALE_MAP = {
    "million": "million",
    "billion": "billion",
    "crore": "crore",
    "crores": "crore",
    "lakh": "lakh",
    "lakhs": "lakh",
    "thousand": "thousand",
    "thousands": "thousand",
    "trillion": "trillion",
}

# Physical units
UNIT_PATTERN = re.compile(
    r'\b(?:square\s*feet|sq\.?\s*ft\.?|sqft|tonnes|metric\s*tonnes|guards|centres|centers|facilities|employees|km|mt)\b',
    re.IGNORECASE
)

# Number patterns (handles thousands commas and decimals)
NUMBER_REGEX = r'[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?'

# Percentage pattern
PERCENTAGE_PATTERN = re.compile(rf'({NUMBER_REGEX})\s*(?:%|percent)', re.IGNORECASE)

# Full quantity regex
QUANTITY_PATTERN = re.compile(
    rf'(?:(over|more\s+than|approximately|about|nearly|at\s+least|up\s+to)\s+)?'
    rf'(?:({CURRENCY_PATTERN.pattern})\s*)?'
    rf'({NUMBER_REGEX})\s*'
    rf'(?:({SCALE_PATTERN.pattern})\b)?\s*'
    rf'(?:(%|percent|{UNIT_PATTERN.pattern}))?',
    re.IGNORECASE
)

# Year and fiscal year patterns
FISCAL_YEAR_PATTERN = re.compile(r'\b(FY\s*\d{2,4}(?:-\d{2,4})?|fiscal\s*(?:year)?\s*\d{2,4})\b', re.IGNORECASE)
CALENDAR_YEAR_PATTERN = re.compile(r'\b(19\d{2}|20\d{2})\b')
QUARTER_PATTERN = re.compile(r'\b(Q[1-4])\s*(?:of\s+)?(FY\s*\d{2,4}|\d{4})?\b', re.IGNORECASE)
SPECIFIC_DATE_PATTERN = re.compile(
    r'\b(?:as\s+of\s+|for\s+the\s+year\s+ended\s+)?'
    r'((?:January|February|March|April|May|June|July|August|September|October|November|December|'
    r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{2,4})\b',
    re.IGNORECASE
)
