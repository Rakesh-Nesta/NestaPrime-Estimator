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

# Part C — MASTER SPORT LIST (Module 1), C.1 (indoor) + C.2 (outdoor), 30
# sports. min_clear_height_ft is the club/base figure where the blueprint
# gives a club/tournament pair (e.g. "24 ft club / 30 ft intl" -> 24.0) —
# that is the true minimum a building must clear; None for outdoor sports,
# which have no ceiling constraint.
#
# playing_l/w_ft and build_l/w_ft are numeric L x W (ft), club/base figure
# where a club/tournament pair is given — parsed from the same C.1/C.2
# text, left None where the dimension is genuinely variable (per-lane,
# custom footprint, oval track) rather than a fixed rectangle.
#
# (key, display_order, name, category, playing_dims, build_dims,
#  playing_l_ft, playing_w_ft, build_l_ft, build_w_ft,
#  min_clear_height_ft, governing_body)
SPORTS_SEED = [
    ("badminton", 1, "Badminton", "indoor", "44 x 20", "52 x 30 club / 60 x 36 tournament",
     44, 20, 52, 30, 24.0, "BWF"),
    ("table_tennis", 2, "Table Tennis", "indoor", "9 x 5 (table)", "40 x 20 per table club / 46 x 23 per table tournament (14 x 7 m)",
     9, 5, 40, 20, 12.0, "ITTF"),
    ("squash", 3, "Squash", "indoor", "32 x 21", "32 x 21 + walls",
     32, 21, 32, 21, 18.5, "WSF"),
    ("basketball_indoor", 4, "Basketball", "indoor", "92 x 49", "105 x 62",
     92, 49, 105, 62, 23.0, "FIBA"),
    ("volleyball_indoor", 5, "Volleyball", "indoor", "59 x 29.5", "79 x 49",
     59, 29.5, 79, 49, 23.0, "FIVB"),
    ("gymnasium", 6, "Gymnasium / multi-purpose hall", "indoor", "custom", "per layout",
     None, None, None, None, 16.0, "NestaPrime standard (no federation)"),
    ("shooting_range_10m", 7, "Shooting range 10 m", "indoor", "33 x (3.3 per lane)", "44 x (3.3 per lane + 3 each side) - firing point 5 ft + rear 6 ft",
     None, None, None, None, 12.0, "ISSF"),
    ("kabaddi", 8, "Kabaddi", "indoor", "43 x 33", "56 x 46",
     43, 33, 56, 46, 16.0, "IKF"),
    ("wrestling_boxing_martial_arts", 9, "Wrestling / boxing / martial arts", "indoor", "mat 40 x 40", "50 x 50",
     40, 40, 50, 50, 16.0, "UWW / IBA"),
    ("indoor_cricket_nets", 10, "Indoor cricket nets", "indoor", "80 x 12 per lane", "86 x (12 per lane + 3 between lanes)",
     None, None, None, None, 16.0, "NestaPrime standard (BCCI practice-net guidance)"),
    ("box_cricket", 11, "Box cricket", "outdoor", "50 x 25 (custom common)", "56 x 31 (3 ft buffer each side, inside the net)",
     50, 25, 56, 31, None, "NestaPrime standard (no federation)"),
    ("cricket_practice_nets", 12, "Cricket practice nets", "outdoor", "80 x 12 per lane", "86 x (12 per lane + 3 between lanes)",
     None, None, None, None, None, "NestaPrime standard (BCCI practice-net guidance)"),
    ("football_11", 13, "Football 11-a-side", "outdoor", "344 x 223 (105 x 68 m)", "360 x 240",
     344, 223, 360, 240, None, "FIFA"),
    ("football_7", 14, "Football 7-a-side", "outdoor", "197 x 130", "210 x 145",
     197, 130, 210, 145, None, "FIFA"),
    ("football_5_futsal", 15, "Football 5-a-side / futsal", "outdoor", "130 x 65", "145 x 80",
     130, 65, 145, 80, None, "FIFA"),
    ("tennis", 16, "Tennis (hard / clay / grass)", "outdoor", "78 x 36", "120 x 60",
     78, 36, 120, 60, None, "ITF"),
    ("padel", 17, "Padel", "outdoor", "66 x 33 (20 x 10 m)", "66 x 33 court + 6 ft access strip on the door side (not an FIP requirement; NestaPrime standard)",
     66, 33, 66, 33, None, "FIP"),
    ("pickleball", 18, "Pickleball", "outdoor", "44 x 20", "60 x 30 (64 x 34 tournament)",
     44, 20, 60, 30, None, "USA Pickleball"),
    ("basketball_outdoor", 19, "Basketball outdoor", "outdoor", "92 x 49", "105 x 62",
     92, 49, 105, 62, None, "FIBA"),
    ("volleyball_outdoor", 20, "Volleyball outdoor", "outdoor", "59 x 29.5", "79 x 49",
     59, 29.5, 79, 49, None, "FIVB"),
    ("beach_volleyball", 21, "Beach volleyball", "outdoor", "52 x 26", "72 x 46 club / 92 x 66 competition, sand 16 in",
     52, 26, 72, 46, None, "FIVB"),
    ("hockey_turf", 22, "Hockey turf", "outdoor", "300 x 180", "330 x 200 FIH (15 ft ends, 10 ft sides) / 320 x 200 school",
     300, 180, 330, 200, None, "FIH"),
    ("athletic_track_400m", 23, "Athletic track 400 m, 8 lane", "outdoor", "400 m oval", "~580 x 300",
     None, None, 580, 300, None, "World Athletics"),
    ("athletic_track_200_250m", 24, "Athletic track 200/250 m (school)", "outdoor", "oval", "per layout",
     None, None, None, None, None, "World Athletics (scaled, non-certified)"),
    ("skating_rink", 25, "Skating rink", "outdoor", "100 x 60", "110 x 70 + barrier",
     100, 60, 110, 70, None, "World Skate"),
    ("archery_range", 26, "Archery range", "outdoor", "distance input 18 m indoor / 30-90 m outdoor x 10 per lane", "distance + 30 ft overshoot zone, lanes + 10 ft each side",
     None, None, None, None, None, "World Archery"),
    ("kids_play_area", 27, "Kids play area", "outdoor", "equipment footprint", "footprint + 6 ft fall zone each side",
     None, None, None, None, None, "ASTM F1487 / IS 15650"),
    ("swimming_pool_25m", 28, "Swimming pool 25 m", "outdoor", "82 x 41 (6 lane)", "102 x 61 (deck 10 ft each side)",
     82, 41, 102, 61, None, "World Aquatics"),
    ("swimming_pool_50m", 29, "Swimming pool 50 m", "outdoor", "164 x 82 (8-10 lane)", "194 x 112 (deck 15 ft each side)",
     164, 82, 194, 112, None, "World Aquatics"),
    ("multipurpose_court", 30, "Multipurpose court", "outdoor", "120 x 80", "per sports chosen",
     120, 80, None, None, None, "Per sport marked (FIBA / FIVB / BWF / USA Pickleball)"),
]
