"""Unit tests for scoring and round logic (pure functions, no I/O)."""
import pytest

from app.game import rules


def test_normalize_and_match():
    assert rules.normalize_guess("  Ice   CREAM ") == "ice cream"
    assert rules.is_correct_guess("ICE cream", "ice cream")
    assert not rules.is_correct_guess("icecream", "ice cream")
    assert not rules.is_correct_guess("", "cat")


def test_round_multiplier_grows_with_round_number():
    assert rules.round_multiplier(1) == 1.0
    assert rules.round_multiplier(2) == pytest.approx(1.1)
    assert rules.round_multiplier(5) == pytest.approx(1.4)
    assert rules.round_multiplier(0) == 1.0


def test_guesser_points_faster_is_better():
    fast = rules.guesser_points(remaining_seconds=80, round_seconds=80, round_number=1)
    mid = rules.guesser_points(40, 80, 1)
    slow = rules.guesser_points(1, 80, 1)
    assert fast == 200 and mid == 150 and slow >= 100
    assert fast > mid > slow


def test_guesser_points_floor_and_clamp():
    assert rules.guesser_points(0, 80, 1) == 100          # still rewarded for correctness
    assert rules.guesser_points(-5, 80, 1) == 100         # negative remaining clamped
    assert rules.guesser_points(500, 80, 1) == 200        # cannot exceed max
    assert rules.guesser_points(10, 0, 1) == 0            # invalid duration


def test_guesser_points_scale_with_round():
    assert rules.guesser_points(80, 80, 3) == 240          # 200 * 1.2
    assert rules.guesser_points(80, 80, 3) > rules.guesser_points(80, 80, 1)


def test_drawer_points():
    assert rules.drawer_points(0, 1) == 0
    assert rules.drawer_points(1, 1) == 40
    assert rules.drawer_points(3, 1) == 120
    assert rules.drawer_points(1, 2) == 44


def test_mask_word():
    assert rules.mask_word("cat") == "_ _ _"
    assert rules.mask_word("ice cream") == "_ _ _    _ _ _ _ _"


def test_pick_next_drawer_rotation():
    order = [1, 2, 3, 4]
    assert rules.pick_next_drawer(order, {1, 2, 3, 4}, None) == 1
    assert rules.pick_next_drawer(order, {1, 2, 3, 4}, 1) == 2
    assert rules.pick_next_drawer(order, {1, 2, 3, 4}, 4) == 1          # wraps
    assert rules.pick_next_drawer(order, {1, 3, 4}, 1) == 3              # skips ineligible
    assert rules.pick_next_drawer(order, {2}, 2) == 2                    # only one left
    assert rules.pick_next_drawer(order, set(), 1) is None
    assert rules.pick_next_drawer([], {1}, None) is None
    assert rules.pick_next_drawer(order, {3}, 99) == 3                   # unknown previous


def test_rank_leaderboard_ties_and_winners():
    board = rules.rank_leaderboard([(1, "A", 100), (2, "B", 300), (3, "C", 300), (4, "D", 50)])
    assert [e["rank"] for e in board] == [1, 1, 3, 4]
    assert [e["is_winner"] for e in board] == [True, True, False, False]


def test_rank_leaderboard_no_winner_when_all_zero():
    board = rules.rank_leaderboard([(1, "A", 0), (2, "B", 0)])
    assert all(not e["is_winner"] for e in board)
