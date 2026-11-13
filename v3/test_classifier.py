import unittest
from theme_classifier import load_classifier, classify_card
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

CLASSIFIER = load_classifier(
    SCRIPT_DIR / "themes.json",
    SCRIPT_DIR / "theme_rules.json"
)

class ClassifierRegressionTests(unittest.TestCase):
    def test_tarland_spellslinger_tokens(self):
        card = {
            "name": "Tarland the Skysummoner",
            "oracle_tags": ["evasion", "repeatable-creature-tokens", "repeatable-token-generator", "synergy-instant", "synergy-sorcery"],
            "text": "", "keywords": []
        }
        themes = classify_card(card, CLASSIFIER)["themes"]
        self.assertIn("Spellslinger", themes)
        self.assertIn("Tokens", themes)

    def test_ulamog_annihilator_control_graveyard(self):
        card = {
            "name": "Ulamog, Gyre of the Infinite",
            "oracle_tags": ["attack-trigger", "attacking-matters-self", "card-advantage", "draw", "pure-draw", "recursion", "removal-permanent", "removal-sacrifice"],
            "text": "Annihilator 4 — Whenever this creature attacks, defending player sacrifices four permanents.",
            "keywords": ["Annihilator 4"]
        }
        themes = classify_card(card, CLASSIFIER)["themes"]
        for expected in ("Annihilator", "Control", "Graveyard"):
            self.assertIn(expected, themes)

    def test_aurelia_extra_combat_without_false_ramp(self):
        card = {
            "name": "Aurelia, War Leader",
            "oracle_tags": ["attack-trigger", "attacking-matters-self", "evasion", "extra-combat-phase", "extra-untap", "phase-manipulation", "untapper", "untapper-creature"],
            "text": "Flying, vigilance, haste. Whenever Aurelia attacks for the first time each turn, untap all creatures you control. After this phase, there is an additional combat phase.",
            "keywords": ["Flying", "Vigilance", "Haste"]
        }
        themes = classify_card(card, CLASSIFIER)["themes"]
        self.assertIn("Aggro", themes)
        self.assertIn("Extra Combats", themes)
        self.assertNotIn("Ramp", themes)

    def test_untapping_creature_alone_is_not_ramp(self):
        card = {
            "name": "Untap test",
            "oracle_tags": ["extra-untap", "untapper", "untapper-creature"],
            "text": "Untap target creature.", "keywords": []
        }
        self.assertNotIn("Ramp", classify_card(card, CLASSIFIER)["themes"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
