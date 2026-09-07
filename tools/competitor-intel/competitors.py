"""
Competitor configuration for each client.

YouTube channels and Instagram handles to scrape weekly for content research.
Update these lists as needed — they drive the weekly content plan.
"""

# ── Info Space Leaders ─────────────────────────────────────────────────────────
#
# Big names in the info product / coaching / creator economy space.
# These are benchmarks — not direct competitors but reference points for what
# premium personal brand + offer operators look like at scale.
#
INFO_SPACE_LEADERS = [
    {
        "rank": 1,
        "name": "Alex Hormozi",
        "handle": "alexhormozi",
        "primary_platform": "youtube",
        "platforms": ["youtube", "instagram"],
        "niche": "Business Acquisition",
        "notes": "Acquisition.com · $200M+ portfolio · B2B client acquisition model",
        "yt_url": "https://youtube.com/@AlexHormozi",
        "ig_url": "https://instagram.com/alexhormozi",
        "reach": "2.4M YouTube",
    },
    {
        "rank": 2,
        "name": "Iman Gadzhi",
        "handle": "imangadzhi",
        "primary_platform": "youtube",
        "platforms": ["youtube", "instagram"],
        "niche": "Agency / Info Products",
        "notes": "IAG Media · SMMA education · scaled to $40M before 25",
        "yt_url": "https://youtube.com/@imangadzhi",
        "ig_url": "https://instagram.com/imangadzhi",
        "reach": "1.9M YouTube",
    },
    {
        "rank": 3,
        "name": "Dan Koe",
        "handle": "thedankoe",
        "primary_platform": "youtube",
        "platforms": ["youtube", "instagram", "twitter"],
        "niche": "Creator Economy",
        "notes": "The Modern Mastery · 1-person business model · prolific writer",
        "yt_url": "https://youtube.com/@thedankoe",
        "ig_url": "https://instagram.com/thedankoe",
        "reach": "1.1M YouTube",
    },
    {
        "rank": 4,
        "name": "Codie Sanchez",
        "handle": "codiesanchez",
        "primary_platform": "youtube",
        "platforms": ["youtube", "instagram", "twitter"],
        "niche": "Unconventional Business",
        "notes": "Contrarian Thinking · buying businesses · multi-platform content machine",
        "yt_url": "https://youtube.com/@CodieSanchez",
        "ig_url": "https://instagram.com/codiesanchez",
        "reach": "1.3M YouTube",
    },
    {
        "rank": 5,
        "name": "Justin Welsh",
        "handle": "thejustinwelsh",
        "primary_platform": "instagram",
        "platforms": ["instagram", "twitter", "youtube"],
        "niche": "Creator / Solo Business",
        "notes": "Saturday Solopreneur · $5M+ from solo brand · LinkedIn + newsletter focus",
        "yt_url": "https://youtube.com/@JustinWelsh",
        "ig_url": "https://instagram.com/thejustinwelsh",
        "reach": "600K Instagram",
    },
    {
        "rank": 6,
        "name": "Cole Gordon",
        "handle": "cole.gordon",
        "primary_platform": "instagram",
        "platforms": ["instagram", "youtube"],
        "niche": "High-Ticket Sales",
        "notes": "Remote Closing Academy · VSL funnels · coaching closers at scale",
        "yt_url": "https://youtube.com/@ColeGordon",
        "ig_url": "https://instagram.com/cole.gordon",
        "reach": "400K Instagram",
    },
    {
        "rank": 7,
        "name": "Leila Hormozi",
        "handle": "leilahormozi",
        "primary_platform": "instagram",
        "platforms": ["instagram", "youtube"],
        "niche": "Operations / Scaling",
        "notes": "Acquisition.com COO · operations at scale · women in business angle",
        "yt_url": "https://youtube.com/@LeilaHormozi",
        "ig_url": "https://instagram.com/leilahormozi",
        "reach": "1.8M Instagram",
    },
    {
        "rank": 8,
        "name": "Hamza Ahmed",
        "handle": "hamza.ahmed096",
        "primary_platform": "youtube",
        "platforms": ["youtube", "instagram"],
        "niche": "Self-Improvement",
        "notes": "Discipline + lifestyle · young audience · YouTube-first brand",
        "yt_url": "https://youtube.com/@HamzaAhmedPH",
        "ig_url": "https://instagram.com/hamza.ahmed096",
        "reach": "1.5M YouTube",
    },
    {
        "rank": 9,
        "name": "Russell Brunson",
        "handle": "russellbrunson",
        "primary_platform": "youtube",
        "platforms": ["youtube", "instagram"],
        "niche": "Funnels / Marketing",
        "notes": "ClickFunnels founder · OG info product marketer · book funnel king",
        "yt_url": "https://youtube.com/@RussellBrunson",
        "ig_url": "https://instagram.com/russellbrunson",
        "reach": "800K YouTube",
    },
    {
        "rank": 10,
        "name": "Myron Golden",
        "handle": "myrongolden",
        "primary_platform": "youtube",
        "platforms": ["youtube", "instagram"],
        "niche": "Wealth / Speaking",
        "notes": "BOSS Moves · stage presence + offer creation · high ticket mindset",
        "yt_url": "https://youtube.com/@MyronGolden",
        "ig_url": "https://instagram.com/myrongolden",
        "reach": "450K YouTube",
    },
    {
        "rank": 11,
        "name": "Brendon Burchard",
        "handle": "brendonburchard",
        "primary_platform": "youtube",
        "platforms": ["youtube", "instagram"],
        "niche": "High Performance",
        "notes": "High Performance Academy · OG personal brand · coaching + courses",
        "yt_url": "https://youtube.com/@BrendonBurchard",
        "ig_url": "https://instagram.com/brendonburchard",
        "reach": "700K YouTube",
    },
    {
        "rank": 12,
        "name": "Grant Cardone",
        "handle": "grantcardone",
        "primary_platform": "youtube",
        "platforms": ["youtube", "instagram"],
        "niche": "Sales / Real Estate",
        "notes": "10X brand · Cardone Capital · polarizing high-energy content style",
        "yt_url": "https://youtube.com/@GrantCardone",
        "ig_url": "https://instagram.com/grantcardone",
        "reach": "1.2M YouTube",
    },
]

# ── The client ────────────────────────────────────────────────────────────────
#
# Fill this in per client, from the competitor research in phase 2. Two groups,
# handled differently downstream:
#
#   direct    : same offer, same audience. Mine their TOPICS and ANGLES so the
#               client makes the better version of what already works in their lane.
#   reference : creators in any niche whose numbers are far ahead. Mine their
#               HOOKS and FORMATS and carry them into the client's world. Never
#               copy their subject matter, only the shape.
#
# Handles only, no @ and no URL. YouTube wants the channel handle as it appears
# after the @ in the channel URL; Instagram wants the username.
#
# The flat "youtube" and "instagram" lists are what the scrapers actually read.
# Keep them in step with the two groups above, because nothing checks that for you.
#
CLIENT_COMPETITORS = {
    # Direct niche competitors (topics + angles).
    "competitors_youtube": [
        # "TheirChannelHandle",
    ],
    "competitors_instagram": [
        # "their_ig_username",
    ],

    # Viral / format references (hooks + formats), not necessarily this niche.
    "reference_youtube": [
        # "ABigChannelHandle",
    ],
    "reference_instagram": [
        # "a_big_ig_username",
    ],

    # Combined flat lists consumed by the scrapers.
    "youtube": [],
    "instagram": [],

    "name": "",              # the client's name, as it should appear in a script
    "niche": (
        # One or two sentences: who they help and with what. This goes into the
        # research prompt, so vague wording here produces vague angles.
        ""
    ),
    "brand_voice_path": "knowledge/BRAND_VOICE.md",
    "youtube_videos_per_week": 2,
    "reels_per_week": 14,
}

# Older scripts imported this under the previous name. Keep both pointing at one dict
# so a half-updated script cannot quietly read an empty roster.
CLIENT_COMPETITORS.setdefault("name", "")
