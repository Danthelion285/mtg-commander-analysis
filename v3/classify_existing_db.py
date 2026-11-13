"""Reclassify Oracle-ID cards in an existing MTG Commander SQLite database.

Only the themes column is updated. The schema, source fields, and typals are
left untouched. Cards are classified once per Oracle ID so reprints stay in sync.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path
from theme_classifier import load_classifier, classify_card


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", help="Existing SQLite database path")
    SCRIPT_DIR = Path(__file__).resolve().parent

    parser.add_argument(
    "--themes",
    default=str(SCRIPT_DIR / "themes.json")
    )

    parser.add_argument(
    "--rules",
    default=str(SCRIPT_DIR / "theme_rules.json")
    )
    args = parser.parse_args()

    db_path = Path(args.database)
    classifier = load_classifier(args.themes, args.rules)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM card_printings WHERE oracle_id IS NOT NULL").fetchall()

    cards = {}
    for row in rows:
        oid = row["oracle_id"]
        if not oid:
            continue
        if oid not in cards:
            cards[oid] = {
                "name": row["name"], "text": row["text"],
                "keywords": row["keywords"], "subtypes": row["subtypes"],
                "oracle_tags": row["oracle_tags"]
            }

    results = {oid: classify_card(card, classifier) for oid, card in cards.items()}
    updates = [
        (json.dumps(results[row["oracle_id"]]["themes"], ensure_ascii=False), row["uuid"])
        for row in rows if row["oracle_id"]
    ]
    con.executemany("UPDATE card_printings SET themes = ? WHERE uuid = ?", updates)
    con.commit()

    remaining = con.execute("""SELECT COUNT(*) FROM card_printings
        WHERE oracle_id IS NOT NULL AND (themes IS NULL OR themes = '' OR themes = '[]')""").fetchone()[0]
    total = con.execute("SELECT COUNT(*) FROM card_printings").fetchone()[0]
    print(f"Oracle IDs classified: {len(results)}")
    print(f"Commander printings updated: {len(updates)}")
    print(f"Printings remaining without themes: {remaining}")
    print(f"Total database rows (unchanged): {total}")
    con.close()


if __name__ == "__main__":
    main()
