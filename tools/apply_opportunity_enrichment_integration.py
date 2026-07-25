from pathlib import Path

event_types = Path("src/event_types.py")
text = event_types.read_text(encoding="utf-8")
line = 'OPPORTUNITY_ENRICHED = "OpportunityEnriched"'
if line not in text:
    anchor = 'OPPORTUNITY_UPDATED = "OpportunityUpdated"'
    if anchor not in text:
        raise SystemExit("Could not find OpportunityUpdated in src/event_types.py")
    text = text.replace(anchor, anchor + "\n" + line, 1)
    event_types.write_text(text, encoding="utf-8")

review = Path("src/institutional_review_engine.py")
text = review.read_text(encoding="utf-8")
old = 'SOURCE_EVENT_TYPES = ("OpportunityCreated", "OpportunityUpdated")'
new = (
    'SOURCE_EVENT_TYPES = (\n'
    '    "OpportunityCreated",\n'
    '    "OpportunityUpdated",\n'
    '    "OpportunityEnriched",\n'
    ')'
)
if old in text:
    text = text.replace(old, new, 1)
elif '"OpportunityEnriched"' not in text:
    raise SystemExit(
        "Could not locate SOURCE_EVENT_TYPES in "
        "src/institutional_review_engine.py"
    )
review.write_text(text, encoding="utf-8")

print("OpportunityEnriched event integration applied.")
