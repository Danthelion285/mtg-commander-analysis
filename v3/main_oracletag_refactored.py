#loader


#imports
import pandas as pd
import requests
import json
from pathlib import Path

import pysqlite3 as sqlite3

import gzip

from theme_classifier import load_classifier, classify_card
# main idea

url = "https://mtgjson.com/api/v5/AllPrintings.json"
#pairing time required from the url.
handshake_time = requests.get(url, timeout=30)# handshake time of 30ms

handshake_time.raise_for_status()

data = handshake_time.json()
#status checks

handshake_time.raise_for_status()


# JSON vocabulay tags:
PROJECT_DIR = Path(r'd:\Python_Ironhack_precourse\Projects\MTG-dashboard\v3')
VOCABULARY_FILE = PROJECT_DIR / "themes.json"


def load_tags(filename):
    """Load a JSON vocabulary file."""

    file_path = PROJECT_DIR / filename

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


tag_vocabulary = load_tags("themes.json")
#supertags
themes = tag_vocabulary["themes"]
typals = tag_vocabulary["typals"]

# Load regex rules and approved Oracle Tag mappings.
RULES_FILE = PROJECT_DIR / "theme_rules.json"
classifier = load_classifier(VOCABULARY_FILE, RULES_FILE)
# prints to check on the number of themes.
print(f"Themes: {len(themes)}")
print(f"Typals: {len(typals)}")
print(f"Total: {len(themes) + len(typals)}")


#data output callback

# just a check step. Can be omitted after cleanup.
print(data.keys())

#THE DATA ITSELF.
sets = data["data"]
#my own sanity check.
print(f'How many sets?: {len(sets)}')

#accumulator. Add an empty list so I can populate later.
cards = []
#the for loop. 
for set_code, set_data in sets.items():
    for card in set_data.get("cards", []):
        card["setCode"] = set_code
        cards.append(card)

print(f"Number of cards: {len(cards)}")

#accesing the relevant columns in the mtg dataset.
dataset = pd.DataFrame(cards)
analysis_columns = [
    "uuid",
    "name",
    "type",
    "types",
    "subtypes",
    "supertypes",
    "colorIdentity",
    "colors",
    "manaValue",
    "keywords",
    "text",
    "edhrecRank",
    "edhrecSaltiness",
    "leadershipSkills",
    "setCode",
    "number"
]

analysis_df = dataset[
    [column for column in analysis_columns if column in dataset.columns]
].copy()
print(analysis_df)

#filter functions to get the legendary type.
def is_eligible_card(card):

    leadership = card.get("leadershipSkills") or {}

    legendary_creature = leadership.get("commander", False)

    return legendary_creature

def filter_eligible_cards(cards):

    eligible_cards = []

    for card in cards:
        if is_eligible_card(card):
            eligible_cards.append(card)

    return eligible_cards

# define the requirements. I guess a tagger is needed here.


# ORACLE TAGGING
# Retrieve Oracle Tags using the same Scryfall bulk-data source
# and hierarchy logic used by Sylvan Librarian.

ORACLE_TAGS_FILE = PROJECT_DIR / "oracle_tags.json"

if ORACLE_TAGS_FILE.exists():

    with open(ORACLE_TAGS_FILE, "r", encoding="utf-8") as file:
        oracle_tag_records = json.load(file)

else:
    session = requests.Session()

    session.headers.update({
    "User-Agent": "MTGCommanderAnalysis/1.0",
    "Accept": "application/json;q=0.9,*/*;q=0.8"
})

    print("Session User-Agent:", session.headers["User-Agent"])

    bulk_response = session.get(
    "https://api.scryfall.com/bulk-data",
    timeout=30
)

    print("Sent User-Agent:", bulk_response.request.headers.get("User-Agent"))
    print("Status:", bulk_response.status_code)
    print("Response:", bulk_response.text)

    bulk_response.raise_for_status()

    bulk_data = bulk_response.json()["data"]

    oracle_tag_source = next(
        item for item in bulk_data
        if item["type"] == "oracle_tags"
    )

    tags_response = session.get(
        oracle_tag_source["jsonl_download_uri"],
        timeout=60
    )
    tags_response.raise_for_status()

    decompressed_tags = gzip.decompress(tags_response.content)

    oracle_tag_records = [
        json.loads(line)
        for line in decompressed_tags.decode("utf-8").splitlines()
        if line.strip()
    ]

    with open(ORACLE_TAGS_FILE, "w", encoding="utf-8") as file:
        json.dump(
            oracle_tag_records,
            file,
            ensure_ascii=False
        )

print(f"Oracle Tag definitions: {len(oracle_tag_records)}")


# Build tag ID -> slug lookup
uuid_to_slug = {
    tag["id"]: tag["slug"]
    for tag in oracle_tag_records
}


# Build parent relationships
slug_to_parents = {}

for tag in oracle_tag_records:

    slug = tag["slug"]

    slug_to_parents[slug] = {
        uuid_to_slug[parent_id]
        for parent_id in tag.get("parent_ids", [])
        if parent_id in uuid_to_slug
    }


# Resolve all parent tags for every tag
all_ancestors = {}

for slug in slug_to_parents:

    ancestors = set()
    pending = list(slug_to_parents[slug])

    while pending:

        parent = pending.pop()

        if parent == slug or parent in ancestors:
            continue

        ancestors.add(parent)
        pending.extend(
            slug_to_parents.get(parent, set()) - ancestors
        )

    all_ancestors[slug] = ancestors


# Build Oracle ID -> assigned tags lookup
oracle_id_to_tags = {}

for tag in oracle_tag_records:

    slug = tag["slug"] #NOT A SLUG, it's from the repo doc on tagging keywords.

    for tagging in tag.get("taggings", []):

        oracle_id = tagging.get("oracle_id")

        if not oracle_id:
            continue

        if oracle_id not in oracle_id_to_tags:
            oracle_id_to_tags[oracle_id] = set()

        oracle_id_to_tags[oracle_id].add(slug)

        # Include parent tags, following Sylvan Librarian's logic
        oracle_id_to_tags[oracle_id].update(
            all_ancestors.get(slug, set())
        )


print(f"Cards with Oracle Tags: {len(oracle_id_to_tags)}")


# Create a separate classification dataframe
card_tags = analysis_df[
    analysis_df["leadershipSkills"].apply(
        lambda x: isinstance(x, dict)
        and x.get("commander", False)
    )
].copy()


# Retrieve Scryfall Oracle IDs from the original MTGJSON dataset
oracle_id_by_uuid = dataset.set_index("uuid")["identifiers"].apply(
    lambda x: x.get("scryfallOracleId")
    if isinstance(x, dict)
    else None
)

card_tags["oracle_id"] = card_tags["uuid"].map(oracle_id_by_uuid)


# Assign Oracle Tags to each commander
card_tags["oracle_tags"] = card_tags["oracle_id"].apply(
    lambda x: sorted(oracle_id_to_tags.get(x, set()))
    if x else []
)


# Classify commander-eligible cards using regex + weighted Oracle Tag rules.
print(f"Classification records: {len(card_tags)}")

classification_results = [
    classify_card(card, classifier)
    for card in card_tags.to_dict("records")
]

card_tags["themes"] = [result["themes"] for result in classification_results]
card_tags["typals"] = [result["typals"] for result in classification_results]


# Merge classification results into the original dataset
dataset = pd.merge(
    analysis_df,
    card_tags[
        ["uuid", "oracle_id", "oracle_tags", "themes", "typals"]
    ],
    on="uuid",
    how="left"
)

print("Merged records:", len(dataset))
print("Merged columns:", dataset.columns.tolist())

# Convert Python lists into JSON strings for SQLite
# Convert all Python lists and dictionaries into JSON strings
for column in dataset.columns:
    dataset[column] = dataset[column].apply(
        lambda x: json.dumps(x, ensure_ascii=False)
        if isinstance(x, (list, dict))
        else x
    )

#remove print duplicates
dataset = dataset.drop_duplicates(
    subset=["name"],
    keep="first"
).copy()

#converts and exports to the SQL database.
# SQLite database path
DATABASE_FILE = PROJECT_DIR / "mtg_cards_tagged_oracle.db"

# Connect to the database
connection = sqlite3.connect(DATABASE_FILE)

# Export dataframe
dataset.to_sql(
    "card_printings",
    connection,
    if_exists="replace",
    index=False
)

# Verify the number of records written
cursor = connection.cursor()

cursor.execute("SELECT COUNT(*) FROM card_printings")
sql_records = cursor.fetchone()[0]

print("Records exported:", sql_records)
print("Database location:", DATABASE_FILE)

connection.close()