"""Mock data for Pipeline Scout pages (pre-Phase 4 DB integration)."""
import datetime

_today = datetime.date.today()
_d = lambda n: (_today - datetime.timedelta(days=n)).strftime("%b %d, %Y")

MOCK_ACTIVITY = [
    {
        "date": _d(0),
        "company": "Midland Steel Works",
        "type": "Exec Hire",
        "detail": "New CFO appointed — Sarah Chen joins from Emerson Electric",
        "source": "PR Newswire",
    },
    {
        "date": _d(1),
        "company": "Great Lakes Distribution",
        "type": "Finance Hire",
        "detail": "Controller role posted — 10+ years ERP experience required",
        "source": "LinkedIn",
    },
    {
        "date": _d(2),
        "company": "Keystone Manufacturing",
        "type": "Acquisition",
        "detail": "Acquired by Summit Partners (PE-backed)",
        "source": "Business Wire",
    },
    {
        "date": _d(3),
        "company": "Cardinal Logistics",
        "type": "Expansion",
        "detail": "Opened new distribution center in Columbus, OH",
        "source": "Columbus Business First",
    },
    {
        "date": _d(4),
        "company": "Ohio Valley Metals",
        "type": "Exec Hire",
        "detail": "CFO transition — outgoing CFO retiring Q2 2026",
        "source": "RSS",
    },
]

MOCK_EVENTS = [
    {
        "date": "Apr 14, 2026",
        "title": "NetSuite SuiteWorld 2026",
        "location": "Las Vegas, NV",
        "type": "Conference",
        "note": "Annual user conference — key prospect attendance",
    },
    {
        "date": "Apr 22, 2026",
        "title": "Ohio Manufacturers Association Summit",
        "location": "Columbus, OH",
        "type": "Industry Event",
        "note": "Regional manufacturing leaders — strong CFO presence",
    },
    {
        "date": "May 6, 2026",
        "title": "ACG Capital Connection",
        "location": "Cleveland, OH",
        "type": "Networking",
        "note": "PE-backed deal flow — high CFO turnover audience",
    },
    {
        "date": "May 19, 2026",
        "title": "Midwest Distribution Forum",
        "location": "Chicago, IL",
        "type": "Industry Event",
        "note": "Wholesale / distribution vertical focus",
    },
]

MOCK_CHANGES = [
    {
        "date": _d(1),
        "company": "Midland Steel Works",
        "change": "Added to TAL",
        "reason": "New CFO signal — PR Newswire",
    },
    {
        "date": _d(2),
        "company": "Alpine Precision Parts",
        "change": "Score: 15 → 42",
        "reason": "Second signal: Controller hire posting",
    },
    {
        "date": _d(3),
        "company": "Keystone Manufacturing",
        "change": "Score: 20 → 65",
        "reason": "PE acquisition confirmed",
    },
    {
        "date": _d(5),
        "company": "Metro Packaging Group",
        "change": "Dismissed",
        "reason": "Recruiter firm — flagged",
    },
    {
        "date": _d(6),
        "company": "Buckeye Industrial Supply",
        "change": "Added to TAL",
        "reason": "New CFO announcement — LinkedIn",
    },
]

MOCK_TARGETS = [
    {
        "rank": 1,
        "company": "Keystone Manufacturing",
        "score": 65,
        "state": "PA",
        "vertical": "Manufacturing",
        "reason": "PE-backed + new CFO signal + >$50M revenue",
    },
    {
        "rank": 2,
        "company": "Midland Steel Works",
        "score": 58,
        "state": "OH",
        "vertical": "Manufacturing",
        "reason": "New CFO + legacy ERP signal",
    },
    {
        "rank": 3,
        "company": "Alpine Precision Parts",
        "score": 42,
        "state": "MI",
        "vertical": "Manufacturing",
        "reason": "Two signals in 30 days",
    },
    {
        "rank": 4,
        "company": "Great Lakes Distribution",
        "score": 38,
        "state": "OH",
        "vertical": "Distribution",
        "reason": "Controller hire + ZoomInfo validated",
    },
    {
        "rank": 5,
        "company": "Cardinal Logistics",
        "score": 35,
        "state": "OH",
        "vertical": "Distribution",
        "reason": "Expansion signal + right-sized company",
    },
]
