#!/usr/bin/env python3
"""
Quick test script for the improved keyword matching logic.
"""

from pathlib import Path
import sys

# Setup path to import zotero_mcp modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from zotero_mcp.services.rss.rss_filter import RSSFilter


def test_matching():
    """Test the improved keyword matching logic."""
    filter = RSSFilter()

    # Test cases: (title, keyword, expected_match)
    test_cases = [
        # Basic cases
        (
            "Hybrid charge storage chemistries for energetic Zn-MnO2 batteries",
            "Zn-MnO2 battery",
            True,
        ),
        ("Zinc-ion batteries: A comprehensive review", "Zinc-ion batteries", True),
        ("Aqueous batteries for grid storage", "Aqueous batteries", True),
        # Hyphen variations
        ("Study of Zn MnO2 electrode materials", "Zn-MnO2", True),
        ("Zinc ion battery performance analysis", "Zinc-ion batteries", True),
        # Singular/plural (both directions should match via stemming)
        (
            "Single battery cell analysis",
            "batteries",
            True,  # "battery" matches "batteries" via stem
        ),
        (
            "Multiple batteries in series",
            "battery",
            True,  # "batteries" matches "battery" via stem
        ),
        # Word order / subset matching
        ("MnO2 cathode for Zn batteries", "MnO2 cathode", True),
        (
            "Operando XAS characterization of electrodes",
            "Operando characterization",
            True,
        ),
        # Should NOT match
        ("Lithium-ion battery advances", "Zn-MnO2 battery", False),
        ("Solar cell efficiency improvements", "Zinc-ion batteries", False),
    ]

    print("=" * 70)
    print("Testing improved keyword matching logic")
    print("=" * 70)
    print()

    passed = 0
    failed = 0

    for title, keyword, expected in test_cases:
        result = filter._matches_keyword(title, keyword)
        status = "✓ PASS" if result == expected else "✗ FAIL"

        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status}")
        print(f"  Title:    {title[:60]}...")
        print(f"  Keyword:  {keyword}")
        print(f"  Expected: {expected}, Got: {result}")
        print()

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


def test_with_real_data():
    """Test with the actual article titles from the email."""
    filter = RSSFilter()

    # Keywords from RSS_PROMPT (extracted by DeepSeek)
    keywords = [
        "Zn-MnO2 battery",
        "Manganese dioxide",
        "Zn anode",
        "Aqueous batteries",
        "Zinc-ion batteries",
        "In situ characterization",
        "Zn-ion battery",
        "Synchrotron radiation",
        "Operando characterization",
        "MnO2 cathode",
    ]

    # Article titles from Google Scholar Alerts
    articles = [
        "Hybrid charge storage chemistries for energetic Zn-MnO2 batteries",
        "Interfacial Design Strategies Using Metal-Organic Frameworks: A Comprehensive Review for Rechargeable Batteries",
        "A Review of Revealing the Impact of Transition Metals in Polyanionic Cathode Material",
        "High-Voltage Zero-Strain Mid-Mn Layered Cathode",
        "Recent advances in zinc ion batteries",
        "Operando X-ray studies of electrode materials",
    ]

    print()
    print("=" * 70)
    print("Testing with real article titles and keywords")
    print("=" * 70)
    print()
    print(f"Keywords: {keywords}")
    print()

    for article in articles:
        matches = [kw for kw in keywords if filter._matches_keyword(article, kw)]
        if matches:
            print(f"✓ MATCHED: {article[:60]}...")
            print(f"  Matched keywords: {matches}")
        else:
            print(f"✗ NO MATCH: {article[:60]}...")
        print()


if __name__ == "__main__":
    success = test_matching()
    test_with_real_data()
    sys.exit(0 if success else 1)
