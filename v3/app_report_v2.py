
# IMPORTS

import pysqlite3 as sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# DATABASE

DB_PATH = Path(__file__).parent
con = sqlite3.connect(DB_PATH / "mtg_cards_tagged_oracle.db")
# st.write("Script location:", Path(__file__).resolve())
# st.write("Database location:", DB_PATH / "mtg_cards_tagged_oracle.db")
# st.write("SQLite version:", sqlite3.sqlite_version)

# PAGE TITLE

st.title("MTG Commander Analytics")

st.write("Commander is a Magic: The Gathering format where each deck consists of 99 cards and a commander." \
         " By definition, a commander is a card type belonging to the legendary class of cards. However, not all of these legendaries are considered as such." \
         " Usually, only creatures, vehicles, spaceships and planeswalkers (cards that represent a player in the battelfield) are eligible." \
         " Additionally, there are sets and online releases that cannot be counted towards what constitute as a commander, simply because they are either designed without legal play in mind or the card effects would not translate well in paper play."
        " It is typically played with 2-5 players, called a pod. " \
        " Multiple themes and typals can be assigned to cards. The analysis serve to show which themes are the most common across the format.")


# Helper: only use these two trusted column names
def get_tags(column, query):
    return pd.read_sql(query.format(tag_column=column), con)


# ==================================================
# QUERY 0: CARD COUNT
# ==================================================
st.write("Firstly, do you know that there are over 30,000 cards in the game without alternate arts and reprints?" \
         "The number below shows the filtered dataset based on EDHrec, the central database for MTG.")

total_card_count = pd.read_sql("""
    SELECT COUNT(DISTINCT uuid) AS total_card_count
    FROM card_printings
""", con).iloc[0, 0]

st.metric("Total MTG Cards", int(total_card_count))


# ==================================================
# QUERY 1: COMMANDER COUNT
# ==================================================
st.write("Now, we can also find out how many cards are actually commander-viable? To do this, we apply the restrictions mentioned earlier.")
commander_count = pd.read_sql("""
    SELECT COUNT(DISTINCT oracle_id) AS commander_count
    FROM card_printings
    WHERE json_extract(leadershipSkills, '$.commander') = 1
""", con).iloc[0, 0]

st.metric("Total Commanders", int(commander_count))

st.write("It is a stark difference from the total of unique cards in the game.")

# ==================================================
# QUERY 2: ARCHETYPE SALTINESS
# ==================================================
st.write ("When discussing the format, an important measure is the salt score. According to EDHrec, the scale is from 0 - 4." \
          "0 means that the card does not invite issues to the game balance or player perception, and 4 being the saltiest, typically associated with strategies that are too unfair for other player.")

st.write("Although there are over 400 themes, I decided to separate the difference between mechanical themes and typals.")

st.header("Most Notorious Top 15 Archetypes")

salt_query = """
SELECT
    tag.value AS strategy,
    COUNT(DISTINCT cp.oracle_id) AS card_count,
    ROUND(AVG(cp.edhrecSaltiness), 2) AS average_salt
FROM card_printings AS cp,
     json_each(cp.{tag_column}) AS tag
WHERE cp.oracle_id IS NOT NULL
  AND cp.edhrecSaltiness IS NOT NULL
GROUP BY tag.value
ORDER BY average_salt DESC;
"""

theme_salt = get_tags("themes", salt_query)
typal_salt = get_tags("typals", salt_query)

fig = px.bar(
    theme_salt.head(15),
    x="average_salt",
    y="strategy",
    orientation="h",
    title="Top 15 Themes by Average Saltiness"
)
fig.update_layout(xaxis_range=[0, 4], yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, use_container_width=True)

fig = px.bar(
    typal_salt.head(15),
    x="average_salt",
    y="strategy",
    orientation="h",
    title="Top 15 Typals by Average Saltiness"
)
fig.update_layout(xaxis_range=[0, 4], yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, use_container_width=True)

st.write("What we see here are that the highest salt-inducing themes are: Madness, Annihilator, and Land Destruction trailing behind these two.")
st.markdown("- Madness mechanic, a mechanic where you discard a card to pay a casting spell's cost, usually ends up winning games before others could set-up their boards.")
st.markdown("- Annihilator, usually linked to a creature type called the Eldrazi, has a mechanic where if they declare an attack, they may destroy X number of permanents on any opponent's field.")
st.markdown("- Land Destruction is quite similar to Annihilator, but restricted to destorying the primary way to pay spell costs, ergo, the mana system that magic is built upon. On other formats, they are banned.")
# ==================================================
# QUERY 3: MOST COMMON STRATEGY BY COLOUR
# ==================================================
st.write(" Next in the analysis is looking at the most commonly found strategy by colour. Here, we would be seeing what most pods prefer to play with.")
st.write(" Most players actually play a combination of colours, so this data is not as representative, still, it gives an insight into what goes in a game of commander.")

st.header("Most Common Strategy by Colour")
st.write("")
colour_query = """
WITH colour_strategies AS (
    SELECT
        colour.value AS colour,
        tag.value AS strategy,
        COUNT(DISTINCT cp.oracle_id) AS card_count
    FROM card_printings AS cp,
         json_each(cp.colorIdentity) AS colour,
         json_each(cp.{tag_column}) AS tag
    WHERE cp.oracle_id IS NOT NULL
    GROUP BY colour.value, tag.value
),
ranked_strategies AS (
    SELECT
        colour,
        strategy,
        card_count,
        RANK() OVER (
            PARTITION BY colour
            ORDER BY card_count DESC
        ) AS strategy_rank
    FROM colour_strategies
)
SELECT colour, strategy, card_count
FROM ranked_strategies
WHERE strategy_rank = 1
ORDER BY colour;
"""

theme_colour = get_tags("themes", colour_query)
typal_colour = get_tags("typals", colour_query)

fig = px.bar(
    theme_colour,
    x="colour",
    y="card_count",
    color="strategy",
    title="Most Common Theme by Colour",
    labels={"colour": "Colour", "card_count": "Card Count", "strategy": "Theme"}
)
st.plotly_chart(fig, use_container_width=True)

fig = px.bar(
    typal_colour,
    x="colour",
    y="card_count",
    color="strategy",
    title="Most Common Typal by Colour",
    labels={"colour": "Colour", "card_count": "Card Count", "strategy": "Typal"}
)
st.plotly_chart(fig, use_container_width=True)

st.write("Unsurprisingly, the most common mechanic played is card draw, with green being into +1/+1, a type of mechanic where you grow your creatures' powers.")
st.write(" As for the typals, All of them are dominated by humans! That's... we can call TR (Typal Resource) I suppose.")
# ==================================================
# QUERY 4: MOST COMMON STRATEGY AMONG COMMANDERS
# ==================================================
st.write(" With a human dominated typal out of the way, I got curious with the amount of commanders that supports a theme.")
st.write(" Again, these mechanics typically would be played with other mechanics on the charts and off-charts as well.")

st.header("Most Common Strategies Among Commanders")

commander_query = """
SELECT
    tag.value AS strategy,
    COUNT(DISTINCT commander.oracle_id) AS commander_count
FROM card_printings AS commander,
     json_each(commander.{tag_column}) AS tag
WHERE commander.oracle_id IS NOT NULL
  AND json_extract(commander.leadershipSkills, '$.commander') = 1
GROUP BY tag.value
ORDER BY commander_count DESC;
"""

theme_commanders = get_tags("themes", commander_query)
typal_commanders = get_tags("typals", commander_query)

fig = px.bar(
    theme_commanders.head(10),
    x="commander_count",
    y="strategy",
    orientation="h",
    title="Top 10 Themes Among Commanders"
)
fig.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, use_container_width=True)

fig = px.bar(
    typal_commanders.head(15),
    x="commander_count",
    y="strategy",
    orientation="h",
    title="Top 10 Typals Among Commanders"
)
fig.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, use_container_width=True)

st.write("The themes department seemed a bit more evenly spread out, except for the card draw. After all, you do win more games by drawing cards.")
st.write("The data does track with what I see in games of the local shop I play at. Even I usually play Control and Graveyard decks.")
st.write("The typal, again, humans seems to take the spotlight, but to see the next tribe, the elves in the 300s is a huge difference. It does not mean that there are more humans than elves when other non-legendaries are considered. ")
# ==================================================
# QUERY 5: MOST COMMON CURVE FOR EACH STRATEGY
# ==================================================
st.markdown("Finally, I save the best analysis for the last. The next one is a different angle on how the commanders' mana value says about the curve of a deck. In commander deck building:")
st.write(". Tipping point = Commander's mana value - 1")
st.write("It means that most (70% and above) of the commander's access to their preferred playstyle should be online before casting your commander. There are of course some exception to this guideline.")

st.header("Mana Curve by TOP 10 Strategy")

curve_query = """
WITH strategy_counts AS (
    SELECT
        tag.value AS strategy,
        COUNT(DISTINCT cp.oracle_id) AS total_cards
    FROM card_printings AS cp,
         json_each(cp.{tag_column}) AS tag
    WHERE cp.oracle_id IS NOT NULL
    GROUP BY tag.value
),
top_strategies AS (
    SELECT strategy
    FROM strategy_counts
    ORDER BY total_cards DESC
    LIMIT 10
)
SELECT
    tag.value AS strategy,
    cp.manaValue,
    COUNT(DISTINCT cp.oracle_id) AS card_count
FROM card_printings AS cp,
     json_each(cp.{tag_column}) AS tag
WHERE cp.oracle_id IS NOT NULL
  AND cp.manaValue IS NOT NULL
  AND tag.value IN (SELECT strategy FROM top_strategies)
GROUP BY tag.value, cp.manaValue
ORDER BY tag.value, cp.manaValue;
"""

theme_curve = get_tags("themes", curve_query)
typal_curve = get_tags("typals", curve_query)

fig = px.line(
    theme_curve,
    x="manaValue",
    y="card_count",
    color="strategy",
    markers=True,
    title="Mana Curve by Theme",
    labels={
        "manaValue": "Mana Value",
        "card_count": "Card Count",
        "strategy": "Theme"
    }
)
st.plotly_chart(fig, use_container_width=True)

fig = px.line(
    typal_curve,
    x="manaValue",
    y="card_count",
    color="strategy",
    markers=True,
    title="Mana Curve by Typal",
    labels={
        "manaValue": "Mana Value",
        "card_count": "Card Count",
        "strategy": "Typal"
    }
)
st.plotly_chart(fig, use_container_width=True)
st.write("So by theme, a lot of commanders fall in the 3-4 mana curve across the top 10. Most players do not play commanders above 7, as getting to the upper mana costs without fast mana isn't possible before a game ends.")
st.write("Note that although I can disregard anything above 10, I chose to show all, as it gives players an option to build with a high-costed commander.")
st.write("As for the typals, As shown in the other charts, humans dominate the commander space, and to an extent, the legendary class, but, they're typically NOT just a human.")
st.write("What this shows instead is that, most players prefer picking a commander that are 3 mana, and that is also seen across the other typals. It's because setting up too fast for a commander cast at turn 1-2 would paint a fat target on you, and may mess up with your own tipping point.")
st.write("Something to understand as well is that there is an interesting building philosophy; that of the exponential ramp archetype. Not shown here, but it is essentially cheating out your ramp from 1->2->4->7 or 8 mana, and most commander games usually ramp within the first 5 turns, with a N+1 boost. So 1->2->4-> 5/6, assuming you draw into lands and a mana source for the first 4 turns.")
st.write("So what this means is that the turbo ramping commander would like to be at mana value 2 or 4, hence an explanation as to why there are some mana value 2 choices as well.")

st.write("This is still the first glimpse of the analysis, where we explore the data on commanders. I made this report to study more into player behaviour when choosing a commander for their decks. Hopefully it's been an interesting read.")
# CLOSE DATABASE
st.write("sources:")
st.markdown(" - https://github.com/jbylund/sylvan_librarian?utm_source=chatgpt.com")
st.markdown(" - https://edhrec.com/tags")
st.markdown(" - https://scryfall.com/docs/api")
con.close()
