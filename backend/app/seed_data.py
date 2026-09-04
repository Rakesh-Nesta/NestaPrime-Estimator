"""Shared seed data — imported by both the dev seed script and the test
suite, so there is exactly one place these figures are defined.

Only Mumbai, Chennai and Delhi NCR are fully specified in the blueprint's
B.2 "Automatic triggers (examples)" table — everything else is a neutral
1.0 placeholder (Q.3: an editable Master Setting default, not a hard-coded
fact; nothing here blocks development)."""

# (city, labour, transport, material, climate_zone, rainfall_zone, coastal, wind_zone, seismic_zone, is_confirmed)
REGIONAL_MULTIPLIER_SEED = [
    ("Mumbai", 1.25, 1.15, 1.10, "hot_humid", "high", True, "3", "III", True),
    ("Chennai", 1.0, 1.0, 1.0, "unspecified", "unspecified", True, "5_cyclonic", "III", True),
    ("Delhi NCR", 1.0, 1.0, 1.0, "hot_dry", "unspecified", False, "4", "IV", True),
    ("Bengaluru", 1.0, 1.0, 1.0, "unspecified", "unspecified", False, "unspecified", "unspecified", False),
    ("Hyderabad", 1.0, 1.0, 1.0, "unspecified", "unspecified", False, "unspecified", "unspecified", False),
    ("Pune", 1.0, 1.0, 1.0, "unspecified", "unspecified", False, "unspecified", "unspecified", False),
    ("Kolkata", 1.0, 1.0, 1.0, "unspecified", "unspecified", True, "unspecified", "unspecified", False),
    ("Ahmedabad", 1.0, 1.0, 1.0, "unspecified", "unspecified", False, "unspecified", "unspecified", False),
    ("Jaipur", 1.0, 1.0, 1.0, "unspecified", "unspecified", False, "unspecified", "unspecified", False),
    ("Lucknow", 1.0, 1.0, 1.0, "unspecified", "unspecified", False, "unspecified", "unspecified", False),
]
