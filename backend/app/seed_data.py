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

# Part I — Additional Scope Checklist (Module 10). "unchecked = excluded
# and listed under Exclusions" — nothing here is on by default; a project
# includes an item by explicitly adding it.
# (key, display_order, group, name)
SCOPE_ITEMS_SEED = [
    ("changing_rooms", 1, "civil", "Changing rooms"),
    ("toilets", 2, "civil", "Toilets"),
    ("storage", 3, "civil", "Storage"),
    ("first_aid", 4, "civil", "First-aid"),
    ("security_cabin", 5, "civil", "Security cabin"),
    ("cafeteria_kiosk", 6, "civil", "Cafeteria / kiosk"),
    ("pavilion_gallery", 7, "civil", "Pavilion / gallery + seating count"),
    ("walkways", 8, "civil", "Walkways"),
    ("boundary_wall", 9, "civil", "Boundary wall"),
    ("electrical_connection_load_sanction", 10, "electrical", "Connection & load sanction"),
    ("dg", 11, "electrical", "DG"),
    ("solar", 12, "electrical", "Solar"),
    ("cctv", 13, "electrical", "CCTV"),
    ("pa_system", 14, "electrical", "PA"),
    ("wifi", 15, "electrical", "Wi-Fi"),
    ("scoreboards_electrical", 16, "electrical", "Scoreboards"),
    ("borewell", 17, "water", "Borewell"),
    ("municipal_connection", 18, "water", "Municipal connection"),
    ("rainwater_harvesting", 19, "water", "Rainwater harvesting"),
    ("irrigation", 20, "water", "Irrigation"),
    ("tank", 21, "water", "Tank"),
    ("parking", 22, "external", "Parking"),
    ("landscaping", 23, "external", "Landscaping"),
    ("signage", 24, "external", "Signage"),
    ("main_gate", 25, "external", "Main gate"),
    ("design_structural_drawings", 26, "services", "Design & structural drawings"),
    ("soil_test_service", 27, "services", "Soil test"),
    ("nocs", 28, "services", "NOCs"),
    ("peb_design_fee", 29, "services", "PEB design fee"),
    ("amc", 30, "maintenance", "AMC (turf brushing, infill top-up, acrylic re-coat 5-7 yr)"),
]

# E.3 — the netting grade catalogue, seeded once for the Director-editable
# NettingGrade table. rate_per_sqm is the range's midpoint, a starting
# [confirm] figure like every other seeded rate in this codebase, not a
# claim that it's NestaPrime's actual current price.
# (key, name, material, twine, mesh, uv_stabilized, typical_use, rate_per_sqm)
NETTING_GRADES_SEED = [
    ("n1_budget", "N1 Budget", "Nylon", "1.5 mm", "50 mm", False, "Practice nets", 30.0),
    ("n2_standard", "N2 Standard", "HDPE", "2.0 mm", "45 mm", True, "Box cricket, football", 47.5),
    ("n3_heavy", "N3 Heavy", "HDPE", "3.0 mm", "40 mm", True, "Premium, coastal, roof", 77.5),
    ("n4_welded_mesh", "N4 Welded mesh", "GI", "4 mm", "50x50 mm", None, "Padel above glass", 400.0),
]

# Part I / Module 9 — accessories.py's own former ACCESSORY_CATALOG dict,
# now this app's working default for the Director-editable
# AccessoryCatalogItem table (the audit's "hardcoded technical
# catalogues" finding). (sport_key, item_name, unit, quantity_per_court)
ACCESSORY_CATALOG_SEED = [
    ("badminton", "Badminton net + post set", "set", 1),
    ("table_tennis", "Table tennis net + post set", "set", 1),
    ("basketball_indoor", "Basketball goal (backboard + ring)", "nos", 2),
    ("basketball_outdoor", "Basketball goal (backboard + ring)", "nos", 2),
    ("volleyball_indoor", "Volleyball net + post set", "set", 1),
    ("volleyball_outdoor", "Volleyball net + post set", "set", 1),
    ("beach_volleyball", "Volleyball net + post set", "set", 1),
    ("indoor_cricket_nets", "Cricket stumps set (2 ends)", "set", 1),
    ("cricket_practice_nets", "Cricket stumps set (2 ends)", "set", 1),
    ("box_cricket", "Cricket stumps set (2 ends)", "set", 1),
    ("football_11", "Football goal with net", "nos", 2),
    ("football_7", "Football goal with net", "nos", 2),
    ("football_5_futsal", "Football goal with net", "nos", 2),
    ("tennis", "Tennis net + post set", "set", 1),
    ("padel", "Padel glass wall/door panel set", "set", 1),
    ("padel", "Padel net", "nos", 1),
    ("pickleball", "Pickleball net + post set", "set", 1),
    ("hockey_turf", "Hockey goal with net", "nos", 2),
    ("athletic_track_400m", "Starting block", "nos", 8),
    ("archery_range", "Archery target (butt/boss)", "nos", 1),
]

# J.2 — Labour category fallback %, used only when a rate item has no
# activity rate card of its own.
# (key, name, default_percent)
LABOUR_CATEGORIES_SEED = [
    ("civil_base_site_prep", "Civil / base / site prep", 30.0),
    ("ms_fabrication_erection", "MS fabrication & erection", 22.0),
    ("turf_laying", "Turf laying", 12.0),
    ("wooden_flooring", "Wooden flooring", 16.0),
    ("acrylic_pu", "Acrylic / PU", 20.0),
    ("electrical", "Electrical", 25.0),
    ("netting", "Netting", 15.0),
    ("pool_mep", "Pool MEP", 25.0),
    ("blended_fallback", "Blended fallback", 22.0),
]

# K.2 — margin floor per client type + whether that type is a "competitive
# segment" (drives the +3 vs +5 point gap to target margin). Both are
# blueprint defaults [confirm], Director-editable later.
# (client_type, floor_margin_percent, competitive_segment)
MARGIN_POLICY_SEED = [
    ("school", 18.0, True),
    ("college", 18.0, True),
    ("housing_society", 20.0, False),
    ("corporate", 15.0, True),
    ("club", 20.0, False),
    ("government", 12.0, True),
    ("individual", 22.0, False),
]

# Q.1/Q.2 — Master Settings for the [confirm] values that don't already
# have a dedicated strongly-typed table (MarginPolicy: K.2 margins,
# RegionalMultiplier: city multipliers, RateItem: material rates,
# LabourCategory: J.2 labour %). These were Python constants; seeding them
# here makes them Director-editable per Q's own principle: "no rate,
# percentage, floor or multiplier is hard-coded."
# (key, value, unit, effective_from ISO date)
SETTINGS_SEED = [
    ("gst_rate_percent", "18.0", "%", "2026-01-01"),  # K.4: "not hard-coded, in case it ever changes"
    ("estimate_validity_days", "15", "days", "2026-01-01"),
    ("quotation_validity_days", "30", "days", "2026-01-01"),
    ("estimate_price_range_percent", "5.0", "%", "2026-01-01"),
    ("rate_stale_after_days", "90", "days", "2026-01-01"),
    ("competitive_segment_gap_points", "3.0", "points", "2026-01-01"),
    ("non_competitive_segment_gap_points", "5.0", "points", "2026-01-01"),
    ("schedule_mobilisation_days_default", "5", "days", "2026-01-01"),
    ("schedule_lighting_electrical_days", "4", "days", "2026-01-01"),
    ("schedule_peb_days", "35", "days", "2026-01-01"),
    ("schedule_pool_days", "84", "days", "2026-01-01"),
    ("schedule_handover_days", "2", "days", "2026-01-01"),
    # K.1 step 6: contingency grouped by each line's work_package.
    ("contingency_civil_percent", "5.0", "%", "2026-01-01"),
    ("contingency_structure_percent", "5.0", "%", "2026-01-01"),
    ("contingency_flooring_percent", "3.0", "%", "2026-01-01"),
    ("contingency_electrical_percent", "3.0", "%", "2026-01-01"),
    ("contingency_pool_percent", "8.0", "%", "2026-01-01"),
    ("contingency_hvac_percent", "5.0", "%", "2026-01-01"),
    ("contingency_accessories_percent", "2.0", "%", "2026-01-01"),
    ("contingency_scope_percent", "5.0", "%", "2026-01-01"),
    ("contingency_services_percent", "0.0", "%", "2026-01-01"),
    # D.4: "Site establishment [confirm 4-8%]" -- K.1 step 3.
    ("site_establishment_percent", "6.0", "%", "2026-01-01"),
]

# Parts F.1/F.2 -- sports.py's own former _FLOORING_TABLE dict, now this
# app's working default for the Director-editable FlooringGuide table (the
# audit's "hardcoded technical catalogues" finding, gap #9). Two sports
# intentionally have no row here -- shooting_range_10m and archery_range --
# matching the original dict, which correctly gave them no recommendation
# rather than a guess. (sport_key, primary_spec, secondary_spec, budget_spec, rationale)
FLOORING_GUIDES_SEED = [
    ("badminton", "Wooden sprung 22 mm + BWF-approved PVC mat 4.5-7 mm", "PU 6 mm", "PVC mat 4.5 mm on PCC",
     "BWF tournaments are played on approved PVC mats laid over a wooden or synthetic base; bare wood is a club finish"),
    ("table_tennis", "Hardwood 22 mm or ITTF-approved PVC/PU 4.5-6 mm", "PU 6 mm", "Vinyl 4 mm",
     "ITTF approves wood and synthetic; non-reflective, non-slip"),
    ("squash", "Hardwood strip 22 mm (maple/beech) on sprung battens", None, None,
     "WSF specifies unsealed hardwood floor"),
    ("basketball_indoor", "Maple 22 mm", "PU 6 mm", "Vinyl 4 mm", "Tournament standard"),
    ("volleyball_indoor", "PU 6 mm", "Teak 22 mm", "Vinyl 4 mm", "Shock absorption"),
    ("gymnasium", "Rubber 8 mm (cardio) / 15-20 mm (free weights)", "Wooden", "Vinyl", "Equipment drops"),
    ("kabaddi", "PU 6 mm / mat", "Wooden", "Vinyl", "Barefoot grip"),
    ("wrestling_boxing_martial_arts", "Rubber 15-20 mm + mat", "PU mat", None, "Falls"),
    ("indoor_cricket_nets", "Turf 30 mm", "Rubber mat", None, "Ball behaviour"),
    ("football_11", "FIFA Quality Pro 50-60 mm", "FIFA Quality 50 mm", "Multi-sport 40 mm", "Certification"),
    ("football_7", "Multi-sport 40 mm", "Cricket 40 mm", "Poly 30 mm", "Cost/performance"),
    ("football_5_futsal", "Multi-sport 40 mm", "Cricket 40 mm", "Poly 30 mm", "Cost/performance"),
    ("box_cricket", "Cricket turf 40 mm", "Multi-sport 40 mm", "Poly 35 mm", "Bounce"),
    ("cricket_practice_nets", "Cricket 30 mm", "Multi 30 mm", "Poly 25 mm", "Bowling"),
    ("tennis", "Acrylic 3-5 mm (5-8 coats)", "Synthetic 5 mm", "Concrete + paint", "ITF"),
    ("padel", "Monofilament 12 mm + sand", None, None, "FIP"),
    ("pickleball", "Acrylic 3 mm", "Concrete + coating", None, "USA Pickleball"),
    ("basketball_outdoor", "Acrylic 3 mm", "PU 5 mm", "Concrete + coating", "Weather"),
    ("volleyball_outdoor", "PU 5 mm", "Sand", "Concrete", "All-weather"),
    ("beach_volleyball", "Washed silica sand 16 in", None, None, "FIVB"),
    ("hockey_turf", "FIH water-based 12-15 mm (needs irrigation)", "FIH sand-dressed 20-25 mm",
     "Multi-sport 40 mm (non-FIH, school use)",
     "FIH pitches are short-pile; 50 mm turf is football turf and is not hockey-legal"),
    ("athletic_track_400m", "Sandwich system 13 mm", "Full-PU 13 mm", "Spray-coat 13 mm (non-certified)",
     "World Athletics certified systems; spike-resistant"),
    ("athletic_track_200_250m", "Sandwich system 13 mm", "Full-PU 13 mm", "Spray-coat 13 mm (non-certified)",
     "World Athletics certified systems; spike-resistant"),
    ("skating_rink", "Concrete + coating", "Tiles", None, "Smooth"),
    ("kids_play_area", "EPDM system 40 mm (10 mm EPDM wearing + 30 mm SBR base; CFH 1.5 m)",
     "Rubber tiles 25-40 mm", "Grass / sand", "Fall protection - 15 mm EPDM alone gives CFH under 1 m"),
    ("swimming_pool_25m", "Anti-slip tiles", "Mosaic", "Marble", "Non-slip"),
    ("swimming_pool_50m", "Anti-slip tiles", "Mosaic", "Marble", "Non-slip"),
    ("multipurpose_court", "Acrylic 3 mm", "PU 5 mm", "Concrete", "Multi-line"),
]

# Part H's lux table, by sport group -- sports.py's own former _LUX_TABLE
# dict, now this app's working default for the Director-editable
# LightingLuxStandard table (audit gap #9). (category, lux_practice, lux_match, lux_tournament)
LIGHTING_LUX_STANDARDS_SEED = [
    ("court", 200, 500, 750),
    ("football_cricket", 200, 500, 750),  # tournament up to 1000 per H
    ("pool", 300, 500, None),
    ("gym", 300, None, None),
]

# Part H's pole table (open-air only) -- sports.py's own former
# _POLE_COUNT dict, now this app's working default for the Director-
# editable SportPoleCount table (audit gap #9). (sport_key, pole_count)
SPORT_POLE_COUNTS_SEED = [
    ("box_cricket", 4),
    ("football_7", 6),
    ("tennis", 4),
    ("basketball_outdoor", 4),
    ("padel", 4),
    ("swimming_pool_25m", 6),
    ("swimming_pool_50m", 6),
]

# Note R1 -- starter rate card, sourced from a review of 23 real historical
# NestaPrime quotations (2021-2026; see docs/annexures for the full working
# and the "Claude outputs" reference spreadsheet). Every row here is a
# *clean, isolable* per-unit rate from that review; lump-sum bundles that
# don't decompose to a trustworthy per-unit figure (LED floodlights,
# basketball/volleyball equipment "sets", the prefab steel shed, swimming
# pool civil work, pool filtration's 35%-of-civil formula, the 84%-of-MRP
# equipment margin) were deliberately left out rather than guessed. Three
# more categories (asphalt sub-base, surface repair/prep, acrylic/synthetic
# court coating) are parked pending accountant sign-off: no confident HSN/
# SAC match exists in the official CBIC classification for them.
#
# HSN/SAC codes and GST% are from CBIC's official "Scheme of Classification
# of Services" (Notification 11/2017-CT(Rate)) and the Sept-2025 GST 2.0
# rate notifications (9/2025-IGST(Rate), 15/2025-CT(Rate)) -- not guessed.
# gst_percent is None for everything on the standard 18% rate (uses the
# Master Settings global default); HSN 9506 sports-goods equipment is
# explicitly 5%, hence the override on the two pole rows.
#
# Seeded as Manual/unverified (RateItem's own default) -- per J.1, "unverified
# rates never become defaults." Nothing here is usable on a real quotation
# until a PM/Director reviews and confirms each item via the Rate Sheet
# screen. (category, item_name, spec, unit, hsn_sac, rate, gst_percent)
RATE_ITEM_SEED = [
    ("Civil", "Cement/RCC base — full slab", "Badminton-type, incl. TMT/curing", "sqft", "995454", 92.0, None),
    ("Civil", "Cement/RCC base — plastering-only", "Basketball-type, base prep only", "sqft", "995454", 69.0, None),
    ("Civil", "Base preparation — specialty surface", "EPDM play-area base", "sqmt", "995454", 1615.0, None),
    ("Civil", "Wall & drainage", "Toe wall + open drain", "rft", "995454", 150.0, None),
    ("Flooring", "PP Modular Tile — component only", "Supply + install, no civil", "sqft", "3918", 116.0, None),
    ("Flooring", "PP Modular Tile — full turnkey", "Incl. civil", "sqft", "3918", 175.0, None),
    ("Flooring", "PP Interlocking Tile 15mm", "2026-era, GST-inclusive pricing", "sqft", "3918", 120.0, None),
    ("Flooring", "Wood flooring — Teak", "20-22mm, domestic", "sqft", "4409", 395.0, None),
    ("Flooring", "Wood flooring — Teak (imported)", "21mm, imported", "sqft", "4409", 410.0, None),
    ("Flooring", "Wood flooring — Maple", "21mm, badminton", "sqft", "4409", 480.0, None),
    ("Flooring", "Wood flooring — Maple (squash)", "Squash court", "sqft", "4409", 380.0, None),
    ("Flooring", "PVC Vinyl Matt 4.5mm", "BWF-certified", "sqft", "3918", 235.0, None),
    ("Flooring", "PVC Vinyl Matt 8mm", "BWF-certified", "sqft", "3918", 205.0, None),
    ("Flooring", "Artificial grass 15mm", "Rest areas, 2026-era", "sqft", "5703", 98.0, None),
    ("Flooring", "Artificial grass 50mm", "Football ground", "sqft", "5703", 140.0, None),
    ("Flooring", "EPDM flooring 25mm", "19mm SBR + 6mm EPDM", "sqmt", "4016", 3498.0, None),
    ("Structure", "SS pipe railing", None, "rft", "7308", 440.0, None),
    ("Structure", "Chain-link fencing", "2\" mesh, 10ga, 10ft ht", "sqft", "7314", 120.0, None),
    ("Equipment", "Badminton pole — standard", "Movable, w/ net", "pair", "9506", 17472.0, 5.0),
    ("Equipment", "Badminton pole — premium", "Model 8129, heavy/wheels/competition", "pair", "9506", 40250.0, 5.0),
]

# Amendment 3 (Annexure 2), Section 7 -- "Complete Your Facility" cross-sell
# starter catalog. Director decision (Section-7-specs.md): seed only
# Fencing with real pricing (Note R1's chain-link rate, Rs 120/sqft --
# the same real historical figure already in RATE_ITEM_SEED above);
# Lighting/Seating/AMC have no defensible reference data anywhere in the
# 23 historical quotations reviewed for Note R1, so they're recorded as
# real catalog rows (sport-tagged, ready to use) with cost=None --
# inactive until a PM/Director enters a real cost, never fabricated for
# a client-facing document.
#
# Fencing's margin_percent (20.0) is a borrowed placeholder -- the middle
# of MARGIN_POLICY_SEED's general floor+target range -- not a real
# Director-set figure for this specific add-on; flagged here so it's
# easy to find and correct via the Cross-Sell admin screen rather than
# silently treated as authoritative.
#
# (name, category, description, cost, unit, margin_percent, all_sports,
#  is_active, sport_keys) -- sport_keys is a tuple of Sport.key values
# this add-on is suggested for; ignored when all_sports is True.
CROSS_SELL_ADDON_SEED = [
    (
        "Perimeter chain-link fencing", "fencing",
        "2\" mesh, 10ga, 10ft height -- Note R1 historical rate.",
        120.0, "sqft", 20.0, False, True,
        (
            "basketball_outdoor", "volleyball_outdoor", "tennis", "padel", "pickleball",
            "football_11", "football_7", "football_5_futsal", "box_cricket", "kabaddi",
        ),
    ),
    (
        "LED floodlight package", "lighting",
        "Court/ground floodlighting -- pending real cost (Note R1: every historical quote "
        "bundled fixtures/poles/wiring together, no isolated per-fixture rate).",
        None, None, None, True, False, (),
    ),
    (
        "Spectator seating", "seating",
        "Bleacher/stand seating -- pending real cost (no reference data in the 23 "
        "historical quotations reviewed for Note R1).",
        None, None, None, True, False, (),
    ),
    (
        "Annual Maintenance Contract (AMC)", "amc",
        "Recurring upkeep contract -- pending real cost (AMC exists today only as an "
        "unpriced Additional Scope checklist item, Part I).",
        None, None, None, True, False, (),
    ),
]
