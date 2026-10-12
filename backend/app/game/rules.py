"""Pure game rules: guess matching, scoring, drawer rotation, leaderboard.

Kept free of I/O so scoring and round logic are trivially unit-testable.
"""
from __future__ import annotations

import math
import re

BASE_POINTS = 100          # awarded for any correct guess
TIME_BONUS_MAX = 100       # extra points scaled by remaining time
ROUND_BONUS_STEP = 0.10    # +10% per round after the first
DRAWER_POINTS_PER_GUESS = 40


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def normalize_guess(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def is_correct_guess(guess: str, word: str) -> bool:
    return normalize_guess(guess) == normalize_guess(word)


def round_multiplier(round_number: int) -> float:
    return 1.0 + ROUND_BONUS_STEP * (max(round_number, 1) - 1)


def guesser_points(remaining_seconds: float, round_seconds: float, round_number: int) -> int:
    """Correctness (base) + time taken (bonus for remaining time) scaled by round number."""
    if round_seconds <= 0:
        return 0
    frac = min(max(remaining_seconds / round_seconds, 0.0), 1.0)
    return _round_half_up((BASE_POINTS + TIME_BONUS_MAX * frac) * round_multiplier(round_number))


def drawer_points(correct_guess_count: int, round_number: int) -> int:
    return _round_half_up(DRAWER_POINTS_PER_GUESS * correct_guess_count * round_multiplier(round_number))


def mask_word(word: str) -> str:
    """Hint shown to guessers: underscores per letter, wider gap for spaces."""
    return " ".join("  " if c == " " else "_" for c in word)


def pick_next_drawer(order: list[int], eligible: set[int], previous: int | None) -> int | None:
    """Next eligible player after `previous` in join order (cyclic)."""
    if not order or not eligible:
        return None
    start = (order.index(previous) + 1) if previous in order else 0
    for i in range(len(order)):
        pid = order[(start + i) % len(order)]
        if pid in eligible:
            return pid
    return None


def rank_leaderboard(players: list[tuple[int, str, int]]) -> list[dict]:
    """Competition ranking (ties share a rank). Winners = rank 1 with score > 0."""
    ordered = sorted(players, key=lambda t: (-t[2], t[1].lower()))
    board: list[dict] = []
    prev_score: int | None = None
    rank = 0
    for i, (pid, name, score) in enumerate(ordered):
        if score != prev_score:
            rank = i + 1
            prev_score = score
        board.append({"rank": rank, "player_id": pid, "name": name, "score": score, "is_winner": False})
    top = board[0]["score"] if board else 0
    for e in board:
        e["is_winner"] = e["rank"] == 1 and top > 0
    return board
