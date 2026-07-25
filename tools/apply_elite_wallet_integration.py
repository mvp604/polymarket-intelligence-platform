from pathlib import Path

event_types = Path("src/event_types.py")
text = event_types.read_text(encoding="utf-8")
constant = 'ELITE_WALLET_PROFILED = "EliteWalletProfiled"'
if constant not in text:
    anchor = 'OPPORTUNITY_ENRICHED = "OpportunityEnriched"'
    if anchor not in text:
        raise SystemExit("Could not find OpportunityEnriched in src/event_types.py")
    text = text.replace(anchor, anchor + "\n" + constant, 1)
    event_types.write_text(text, encoding="utf-8")

enrichment = Path("src/opportunity_enrichment_engine.py")
text = enrichment.read_text(encoding="utf-8")
old = """    wallet_quality = normalized_score(
        value_from(
            row,
            "cluster_wallet_quality",
            "wallet_quality_score",
        )
    )"""
new = """    wallet_quality = normalized_score(
        value_from(
            row,
            "cluster_wallet_quality",
            "wallet_quality_score",
        )
    )

    elite_profile_quality = 0.0
    if table_exists(connection, "elite_wallet_profiles"):
        wallet_addresses = []
        for candidate in (
            value_from(row, "wallets_json"),
            value_from(row, "wallet_addresses_json"),
            value_from(row, "wallets"),
        ):
            if not candidate:
                continue
            if isinstance(candidate, str):
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    parsed = [item.strip() for item in candidate.split(",")]
            else:
                parsed = candidate
            if isinstance(parsed, list):
                wallet_addresses.extend(str(item) for item in parsed if item)

        if wallet_addresses:
            placeholders = ",".join("?" for _ in wallet_addresses)
            profile_row = connection.execute(
                f"SELECT AVG(wallet_score) FROM elite_wallet_profiles "
                f"WHERE wallet IN ({placeholders})",
                wallet_addresses,
            ).fetchone()
            elite_profile_quality = normalized_score(
                profile_row[0] if profile_row else 0
            )

    if elite_profile_quality > 0:
        wallet_quality = clamp(
            wallet_quality * 0.35 + elite_profile_quality * 0.65
        )"""
if old in text:
    text = text.replace(old, new, 1)
elif "elite_profile_quality" not in text:
    raise SystemExit("Could not locate wallet quality block in enrichment engine")
enrichment.write_text(text, encoding="utf-8")
print("Elite wallet event and enrichment integration applied.")
