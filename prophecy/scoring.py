"""
Scoring derivations for label rows.

`labels.json` (and the in-memory bucket built by `prophecy query`) ships
sufficient statistics only:

  - hits         = Σ wᵢ·aᵢ     (weighted true-answer count)
  - total        = Σ wᵢ        (total prompt weight)
  - cert_sum     = Σ wᵢ·cᵢ     (weighted certainty, where cᵢ is 0..100)
  - hit_cert_sum = Σ wᵢ·aᵢ·cᵢ  (per-prompt-coupled weighted certainty of yes answers)

Every downstream metric — hit rate, average certainty, the four score modes
the viewer exposes — derives from those four primitives. Both this module
and the JS `score-math.js` compute identical numbers from the same inputs;
keep them in sync if you change a formula.
"""

from collections.abc import Mapping

# Score mode identifiers used by both the CLI table and the JS viewer's
# score-mode dropdowns. The JS side hardcodes the same strings — change
# them in both places, and add a new option to the dropdowns when adding
# a mode here.
SCORE_MODES = ("weighted", "hit", "coverage", "coupled")


def hit_rate(row: Mapping[str, float]) -> float:
    """Σ wᵢ·aᵢ / Σ wᵢ — fraction of weighted prompts that answered yes."""
    total = row["total"]
    return row["hits"] / total if total else 0.0


def avg_certainty(row: Mapping[str, float]) -> float:
    """Σ wᵢ·cᵢ / Σ wᵢ — weighted mean certainty, in 0..100."""
    total = row["total"]
    return row["cert_sum"] / total if total else 0.0


def story_score(row: Mapping[str, float], mode: str) -> float:
    """Per-row score in [0, 1] under the named mode.

    - "hit"      : hit_rate (ignores certainty)
    - "coverage" : 1 if any yes, else 0
    - "weighted" : hit_rate × avg_certainty/100 (product of two means;
                   default, preserves pre-coupled-mode behavior)
    - "coupled"  : Σ wᵢ·aᵢ·cᵢ / Σ wᵢ / 100 (each yes contributes its
                   own certainty; noes contribute 0 but pull the denominator)

    A confidently-wrong "no" leaves the coupled score untouched but raises
    the product-of-means "weighted" score, since it pulls avg_certainty up
    without pulling hit_rate down. The two modes can disagree noticeably.
    """
    total = row["total"]
    if not total:
        return 0.0
    rate = row["hits"] / total
    if mode == "hit":
        return rate
    if mode == "coverage":
        return 1.0 if row["hits"] > 0 else 0.0
    if mode == "coupled":
        return row["hit_cert_sum"] / total / 100.0
    # "weighted" (default): hit_rate × avg_certainty/100
    return rate * (row["cert_sum"] / total) / 100.0
