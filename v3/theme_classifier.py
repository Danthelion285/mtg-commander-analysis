"""Lightweight, explainable MTG theme/typal classifier.

Accepts Python values or JSON-encoded SQLite fields. No database access.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, list) else [decoded]
        except json.JSONDecodeError:
            return [value]
    return [value]


def _subtype_forms(subtype):
    word = str(subtype).strip().lower()
    if not word:
        return set()
    forms = {word}
    irregular = {
        "elf": "elves", "dwarf": "dwarves", "wolf": "wolves",
        "mouse": "mice", "person": "people", "child": "children",
        "goose": "geese", "ox": "oxen"
    }
    if word in irregular:
        forms.add(irregular[word])
    elif word.endswith(("s", "x", "z", "ch", "sh")):
        forms.add(word + "es")
    else:
        forms.add(word + "s")
    return forms


def _compile_patterns(patterns):
    return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


def load_classifier(themes_path="themes.json", rules_path="theme_rules.json"):
    """Load vocabulary and compile direct, tag, and combined rules."""
    with open(themes_path, encoding="utf-8") as f:
        vocabulary = json.load(f)
    with open(rules_path, encoding="utf-8") as f:
        config = json.load(f)

    themes = set(vocabulary.get("themes", []))
    typals = set(vocabulary.get("typals", []))

    def validate_theme(theme, section):
        if theme not in themes:
            raise ValueError(f"Unknown theme in {section}: {theme}")

    direct_rules = []
    for rule in config.get("direct_rules", []):
        validate_theme(rule["theme"], "direct_rules")
        direct_rules.append({
            **rule,
            "weight": float(rule.get("weight", 3.0)),
            "patterns": _compile_patterns(rule["patterns"])
        })

    tag_rules = defaultdict(list)
    for rule in config.get("oracle_tag_rules", []):
        validate_theme(rule["theme"], "oracle_tag_rules")
        tag_rules[rule["tag"].strip().lower()].append({
            **rule,
            "weight": float(rule.get("weight", 1.0)),
            "confidence": float(rule.get("confidence", 1.0)),
            "relationship": rule.get("relationship", "direct"),
            # Related tags share a group so clusters of near-duplicate tags
            # do not overwhelm independent evidence.
            "group": rule.get("group", rule["tag"].split("-", 1)[0])
        })

    combined_rules = []
    for rule in config.get("combined_rules", []):
        validate_theme(rule["theme"], "combined_rules")
        combined_rules.append({
            **rule,
            "weight": float(rule.get("weight", 3.0)),
            "confidence": float(rule.get("confidence", 1.0)),
            "tag_patterns": _compile_patterns(rule.get("tag_patterns", [])),
            "text_patterns": _compile_patterns(rule.get("text_patterns", [])),
            "keyword_patterns": _compile_patterns(rule.get("keyword_patterns", [])),
        })

    return {
        "themes": themes,
        "typals": typals,
        "direct_rules": direct_rules,
        "tag_rules": dict(tag_rules),
        "combined_rules": combined_rules,
        "typals_from_subtypes": bool(config.get("typals_from_subtypes", True)),
        "threshold": float(config.get("default_theme_threshold", 3.0)),
        "max_score": float(config.get("max_theme_score", 10.0)),
        "diminishing_factor": float(config.get("tag_diminishing_factor", 0.5)),
    }


def classify_card(card, classifier, threshold=None):
    """Return labels, scores, and traceable evidence for one card."""
    rules_text = str(card.get("text") or "")
    keywords = [str(x).strip() for x in _as_list(card.get("keywords"))]
    keyword_text = " | ".join(keywords)
    tags = {str(x).strip().lower() for x in _as_list(card.get("oracle_tags"))}
    subtypes = {str(x).strip() for x in _as_list(card.get("subtypes"))}

    scores = defaultdict(float)
    evidence = defaultdict(list)

    # Direct Oracle-text evidence. A rule contributes once, regardless of
    # how many of its patterns match.
    for rule in classifier["direct_rules"]:
        matches = [p.pattern for p in rule["patterns"] if p.search(rules_text)]
        if matches:
            theme = rule["theme"]
            scores[theme] += rule["weight"]
            evidence[theme].append({
                "source": "regex", "relationship": "direct",
                "weight": rule["weight"], "matches": matches
            })

    # Oracle Tag evidence with diminishing returns inside related tag groups.
    group_counts = defaultdict(int)
    mappings = [
        (tag, mapping)
        for tag in sorted(tags)
        for mapping in classifier["tag_rules"].get(tag, [])
    ]
    mappings.sort(key=lambda item: (-item[1]["weight"], item[0], item[1]["theme"]))
    for tag, mapping in mappings:
        theme = mapping["theme"]
        group_key = (theme, mapping["group"])
        multiplier = classifier["diminishing_factor"] ** group_counts[group_key]
        group_counts[group_key] += 1
        contribution = mapping["weight"] * mapping["confidence"] * multiplier
        scores[theme] += contribution
        evidence[theme].append({
            "source": "oracle_tag", "tag": tag,
            "relationship": mapping["relationship"],
            "group": mapping["group"],
            "weight": mapping["weight"],
            "confidence": mapping["confidence"],
            "diminishing_multiplier": multiplier,
            "contribution": contribution
        })

    # Combined patterns capture interactions that an individual tag cannot.
    for rule in classifier["combined_rules"]:
        required_tags = set(rule.get("all_tags", []))
        any_tag_groups = rule.get("any_tag_groups", [])
        tags_ok = required_tags.issubset(tags)
        if any_tag_groups:
            tags_ok = tags_ok and all(any(tag in tags for tag in group) for group in any_tag_groups)
        tag_pattern_matches = [p.pattern for p in rule["tag_patterns"] if any(p.search(t) for t in tags)]
        text_matches = [p.pattern for p in rule["text_patterns"] if p.search(rules_text)]
        keyword_matches = [p.pattern for p in rule["keyword_patterns"] if p.search(keyword_text)]
        has_any_condition = bool(required_tags or any_tag_groups or rule["tag_patterns"] or rule["text_patterns"] or rule["keyword_patterns"])
        matched = tags_ok and has_any_condition
        if rule.get("require_text_match") and not text_matches:
            matched = False
        if rule.get("require_keyword_match") and not keyword_matches:
            matched = False
        if rule.get("require_tag_pattern_match") and not tag_pattern_matches:
            matched = False
        if matched:
            theme = rule["theme"]
            contribution = rule["weight"] * rule["confidence"]
            scores[theme] += contribution
            evidence[theme].append({
                "source": "combined_rule", "rule": rule.get("id", "unnamed"),
                "relationship": rule.get("relationship", "direct"),
                "weight": rule["weight"], "confidence": rule["confidence"],
                "contribution": contribution,
                "matched_tags": sorted(
                    required_tags.intersection(tags)
                    | {tag for group in any_tag_groups for tag in set(group).intersection(tags)}
                    | {tag for tag in tags if any(p.search(tag) for p in rule["tag_patterns"])}
                ),
                "tag_patterns": tag_pattern_matches,
                "text_patterns": text_matches,
                "keyword_patterns": keyword_matches
            })

    scores = {theme: min(score, classifier["max_score"]) for theme, score in scores.items()}
    cutoff = classifier["threshold"] if threshold is None else float(threshold)
    assigned_themes = sorted(theme for theme, score in scores.items() if score >= cutoff)

    if classifier["typals_from_subtypes"]:
        subtype_forms = set()
        for subtype in subtypes:
            subtype_forms.update(_subtype_forms(subtype))
        assigned_typals = sorted(t for t in classifier["typals"] if t.lower() in subtype_forms)
    else:
        assigned_typals = []

    return {
        "themes": assigned_themes,
        "typals": assigned_typals,
        "theme_scores": dict(sorted(scores.items(), key=lambda item: (-item[1], item[0]))),
        "evidence": dict(evidence)
    }


def classify_cards(cards, classifier, threshold=None):
    for card in cards:
        yield {**card, **classify_card(card, classifier, threshold=threshold)}
