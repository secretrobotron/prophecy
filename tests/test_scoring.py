"""Tests for prophecy.scoring — the pure derivation layer over the
sufficient-statistics shape of label rows.

The four primitives shipped in labels.json are:
  hits         = Σ wᵢ·aᵢ
  total        = Σ wᵢ
  cert_sum     = Σ wᵢ·cᵢ
  hit_cert_sum = Σ wᵢ·aᵢ·cᵢ
Every metric is derived from those — these tests pin the derivations,
and a parallel JS suite in viewer/test/score-math.test.js pins the same
formulas on the browser side.
"""

import math

import pytest

from prophecy import scoring


def row(**fields):
    """Helper to build a label-row-shaped dict with the four primitives."""
    return {
        "hits": fields.get("hits", 0.0),
        "total": fields.get("total", 0.0),
        "cert_sum": fields.get("cert_sum", 0.0),
        "hit_cert_sum": fields.get("hit_cert_sum", 0.0),
    }


class TestHitRate:
    def test_yes_only(self):
        assert scoring.hit_rate(row(hits=4, total=4)) == 1.0

    def test_partial(self):
        assert scoring.hit_rate(row(hits=3, total=4)) == 0.75

    def test_no_only(self):
        assert scoring.hit_rate(row(hits=0, total=4)) == 0.0

    def test_zero_total_does_not_divide_by_zero(self):
        assert scoring.hit_rate(row(hits=0, total=0)) == 0.0


class TestAvgCertainty:
    def test_returns_weighted_mean_certainty_in_0_to_100(self):
        # cert_sum = 5*80 + 2*60 + 1*100 = 620; total = 8 → 77.5
        assert scoring.avg_certainty(row(cert_sum=620, total=8)) == 77.5

    def test_zero_total_does_not_divide_by_zero(self):
        assert scoring.avg_certainty(row(total=0, cert_sum=0)) == 0.0


class TestStoryScore:
    def test_hit_mode_ignores_certainty(self):
        r = row(hits=3, total=4, cert_sum=200, hit_cert_sum=200)
        assert scoring.story_score(r, "hit") == 0.75

    def test_coverage_mode_is_binary(self):
        assert scoring.story_score(row(hits=1, total=4), "coverage") == 1.0
        assert scoring.story_score(row(hits=0, total=4), "coverage") == 0.0

    def test_weighted_mode_is_product_of_means(self):
        # hit_rate=0.75; avg_cert=80 → score = 0.75 × 0.80 = 0.60
        r = row(hits=3, total=4, cert_sum=320)
        assert scoring.story_score(r, "weighted") == pytest.approx(0.60)

    def test_coupled_mode_uses_hit_cert_sum(self):
        # hit_cert_sum = 3*100 = 300; total=4 → 300/4/100 = 0.75
        r = row(hits=3, total=4, cert_sum=320, hit_cert_sum=300)
        assert scoring.story_score(r, "coupled") == pytest.approx(0.75)

    def test_zero_total_returns_zero_for_every_mode(self):
        r = row(hits=0, total=0, cert_sum=0, hit_cert_sum=0)
        for mode in scoring.SCORE_MODES:
            assert scoring.story_score(r, mode) == 0.0

    def test_unknown_mode_falls_back_to_weighted_default(self):
        r = row(hits=3, total=4, cert_sum=320)
        # Same answer as weighted mode.
        assert scoring.story_score(r, "??") == pytest.approx(0.60)

    def test_coupled_diverges_from_weighted_when_noes_are_confident(self):
        """The whole motivation for adding 'coupled' — a confidently-wrong 'no'
        raises avg_certainty (which pulls the weighted score up) but contributes
        nothing to hit_cert_sum (so the coupled score is unaffected)."""
        # Two prompts: yes with cert=80, no with cert=100. Equal weights.
        # hit_rate = 0.5; avg_cert = 90 → weighted = 0.5 × 0.90 = 0.45
        # hit_cert_sum = 80; total = 2 → coupled = 80/2/100 = 0.40
        r = row(hits=1, total=2, cert_sum=180, hit_cert_sum=80)
        assert scoring.story_score(r, "weighted") == pytest.approx(0.45)
        assert scoring.story_score(r, "coupled") == pytest.approx(0.40)
        # Now make the no LESS confident: cert=20 instead of 100.
        # hit_rate unchanged at 0.5; avg_cert = 50 → weighted = 0.25
        # hit_cert_sum unchanged at 80 → coupled still 0.40
        r2 = row(hits=1, total=2, cert_sum=100, hit_cert_sum=80)
        assert scoring.story_score(r2, "weighted") == pytest.approx(0.25)
        assert scoring.story_score(r2, "coupled") == pytest.approx(0.40)


class TestScoreModesConstant:
    def test_contains_every_implemented_mode(self):
        """SCORE_MODES is the public contract; every name in it must work
        in story_score and vice versa."""
        for mode in scoring.SCORE_MODES:
            v = scoring.story_score(row(hits=2, total=4, cert_sum=300, hit_cert_sum=200), mode)
            assert 0.0 <= v <= 1.0 and not math.isnan(v)
