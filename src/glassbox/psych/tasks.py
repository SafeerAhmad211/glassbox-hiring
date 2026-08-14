"""Scoring for published behavioural-task paradigms.

Commercial gamified assessment is built on experimental paradigms that have been in
the open literature for decades. This module implements the **canonical scoring rules
from the source papers**, not any vendor's proprietary variant.

That distinction matters in both directions. It keeps us clear of anyone's IP, and it
produces better science: a paradigm's reliability, validity, and known failure modes
are documented in peer review, whereas a vendor's variant is documented in a brochure.

Each function names its citation and returns the measure the source paper defines. Where
a paradigm has a known methodological controversy, the docstring says so rather than
quietly picking a side.

.. warning::
   These are research instruments. A score from any single task is a noisy estimate of
   a latent trait, and none of them is validated for employment selection on its own.
   Using one to make a hiring decision without local validation would be exactly the
   practice this project exists to document.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "BartTrial",
    "bart_score",
    "digit_span_score",
    "flanker_score",
    "stop_signal_rt",
    "tower_of_london_score",
    "trust_game_score",
]


@dataclass(frozen=True)
class BartTrial:
    """One balloon in the Balloon Analogue Risk Task.

    Args:
        pumps: Number of pumps the participant made.
        exploded: Whether the balloon burst.
        max_pumps: The balloon's burst threshold, if known.
    """

    pumps: int
    exploded: bool
    max_pumps: int | None = None


def bart_score(trials: Sequence[BartTrial]) -> dict[str, float | None]:
    """Score the Balloon Analogue Risk Task (Lejuez et al., 2002).

    The standard measure is **adjusted average pumps**: mean pumps on *unexploded*
    balloons only. Exploded balloons are excluded because the explosion truncates the
    participant's intended behaviour -- including them biases the measure downward
    precisely for the risk-taking participants the task aims to identify.

    Args:
        trials: The balloon trials, in order.

    Returns:
        Dict with:

        - ``adjusted_pumps``: mean pumps on unexploded balloons (the headline measure),
          or ``None`` if every balloon exploded.
        - ``total_pumps``: raw total across all trials.
        - ``explosion_rate``: fraction of balloons burst.
        - ``learning_slope``: OLS slope of pumps over trial index on unexploded
          balloons -- adaptation to feedback. ``None`` with fewer than 3 such trials.

    Raises:
        ValueError: If ``trials`` is empty.

    References:
        Lejuez, C. W., et al. (2002). Evaluation of a behavioral measure of risk
        taking: The Balloon Analogue Risk Task (BART). *Journal of Experimental
        Psychology: Applied*, 8(2), 75-84.
    """
    if not trials:
        raise ValueError("no trials supplied")

    unexploded = [t for t in trials if not t.exploded]

    adjusted = (
        sum(t.pumps for t in unexploded) / len(unexploded) if unexploded else None
    )

    learning_slope: float | None = None
    if len(unexploded) >= 3:
        indices = [float(i) for i, t in enumerate(trials) if not t.exploded]
        pumps = [float(t.pumps) for t in unexploded]
        mean_x = sum(indices) / len(indices)
        mean_y = sum(pumps) / len(pumps)
        denominator = sum((x - mean_x) ** 2 for x in indices)
        if denominator > 0:
            learning_slope = (
                sum((x - mean_x) * (y - mean_y) for x, y in zip(indices, pumps, strict=True))
                / denominator
            )

    return {
        "adjusted_pumps": adjusted,
        "total_pumps": float(sum(t.pumps for t in trials)),
        "explosion_rate": sum(1 for t in trials if t.exploded) / len(trials),
        "learning_slope": learning_slope,
    }


def digit_span_score(
    results: Sequence[tuple[int, bool]], *, trials_per_length: int = 2
) -> dict[str, float]:
    """Score a digit-span task.

    Args:
        results: ``(span_length, correct)`` pairs in presentation order.
        trials_per_length: Trials administered at each length. Used for the
            two-thirds criterion.

    Returns:
        Dict with:

        - ``max_span``: longest length recalled correctly at least once.
        - ``reliable_span``: longest length where at least two-thirds of trials were
          correct. More stable than ``max_span``, which rewards a single lucky trial.
        - ``total_correct``: count of correct trials.
        - ``accuracy``: proportion correct.

    Raises:
        ValueError: If ``results`` is empty or ``trials_per_length`` < 1.

    References:
        Wechsler digit-span lineage; see Jacobs (1887) for the original span method.
    """
    if not results:
        raise ValueError("no results supplied")
    if trials_per_length < 1:
        raise ValueError("trials_per_length must be at least 1")

    by_length: dict[int, list[bool]] = {}
    for length, correct in results:
        by_length.setdefault(length, []).append(correct)

    correct_lengths = [length for length, outcomes in by_length.items() if any(outcomes)]
    reliable_lengths = [
        length
        for length, outcomes in by_length.items()
        if sum(outcomes) / len(outcomes) >= 2 / 3
    ]

    total_correct = sum(1 for _, correct in results if correct)
    return {
        "max_span": float(max(correct_lengths)) if correct_lengths else 0.0,
        "reliable_span": float(max(reliable_lengths)) if reliable_lengths else 0.0,
        "total_correct": float(total_correct),
        "accuracy": total_correct / len(results),
    }


def flanker_score(
    congruent_rts: Sequence[float],
    incongruent_rts: Sequence[float],
    *,
    congruent_correct: int | None = None,
    incongruent_correct: int | None = None,
) -> dict[str, float | None]:
    """Score an Eriksen flanker task.

    The measure of interest is the **conflict effect**: mean incongruent RT minus mean
    congruent RT. Larger values indicate more interference from distractors, i.e. less
    efficient selective attention.

    Raw RT is confounded by general speed and by motivation; the difference score
    cancels most of that, which is why the literature reports it.

    Args:
        congruent_rts: Correct-trial reaction times, congruent condition (ms).
        incongruent_rts: Correct-trial reaction times, incongruent condition (ms).
        congruent_correct: Correct-trial count, for accuracy reporting.
        incongruent_correct: Correct-trial count, for accuracy reporting.

    Returns:
        Dict with ``conflict_effect``, ``mean_congruent_rt``, ``mean_incongruent_rt``,
        and ``rt_variability`` (SD of all RTs, ``None`` with fewer than 2 trials).

    Raises:
        ValueError: If either condition has no trials.

    References:
        Eriksen, B. A., & Eriksen, C. W. (1974). *Perception & Psychophysics*, 16(1).
        Fan, J., et al. (2002). Testing the efficiency and independence of attentional
        networks. *Journal of Cognitive Neuroscience*, 14(3).
    """
    if not congruent_rts or not incongruent_rts:
        raise ValueError("both conditions need at least one trial")

    mean_congruent = sum(congruent_rts) / len(congruent_rts)
    mean_incongruent = sum(incongruent_rts) / len(incongruent_rts)
    combined = list(congruent_rts) + list(incongruent_rts)

    result: dict[str, float | None] = {
        "conflict_effect": mean_incongruent - mean_congruent,
        "mean_congruent_rt": mean_congruent,
        "mean_incongruent_rt": mean_incongruent,
        "rt_variability": statistics.stdev(combined) if len(combined) > 1 else None,
    }

    if congruent_correct is not None and incongruent_correct is not None:
        total_trials = len(congruent_rts) + len(incongruent_rts)
        result["accuracy"] = (congruent_correct + incongruent_correct) / total_trials

    return result


def stop_signal_rt(
    go_rts: Sequence[float],
    stop_signal_delays: Sequence[float],
    stop_success_rate: float,
) -> float | None:
    """Estimate stop-signal reaction time (SSRT) by the integration method.

    SSRT is not directly observable -- a successfully inhibited response produces no
    RT. The horse-race model of Logan & Cowan (1984) recovers it: find the point in the
    go-RT distribution corresponding to the probability of *failing* to stop, and
    subtract mean stop-signal delay.

    .. note::
       The integration method is used here because Verbruggen et al. (2019) established
       it as the consensus estimator; the older mean method is biased when the response
       rate departs from 50%. SSRT estimates are unreliable when the stop-success rate
       is far from 0.5, so this returns ``None`` outside [0.1, 0.9] rather than
       reporting a number that looks precise and is not.

    Args:
        go_rts: Reaction times on go trials (ms).
        stop_signal_delays: Delays used on stop trials (ms).
        stop_success_rate: Proportion of stop trials successfully inhibited, in [0, 1].

    Returns:
        Estimated SSRT in ms, or ``None`` when it cannot be estimated reliably.
        **Lower SSRT means better inhibitory control.**

    Raises:
        ValueError: If inputs are empty or ``stop_success_rate`` is out of range.

    References:
        Logan, G. D., & Cowan, W. B. (1984). *Psychological Review*, 91(3), 295-327.
        Verbruggen, F., et al. (2019). A consensus guide to capturing the ability to
        inhibit actions. *eLife*, 8, e46323.
    """
    if not go_rts:
        raise ValueError("no go trials supplied")
    if not stop_signal_delays:
        raise ValueError("no stop-signal delays supplied")
    if not 0.0 <= stop_success_rate <= 1.0:
        raise ValueError(f"stop_success_rate must be in [0, 1], got {stop_success_rate}")

    if not 0.1 <= stop_success_rate <= 0.9:
        return None

    ordered = sorted(go_rts)
    # p(respond | stop signal) = 1 - p(inhibit); the nth RT at that quantile is the
    # point at which the stop process finished.
    p_respond = 1.0 - stop_success_rate
    index = min(len(ordered) - 1, max(0, math.ceil(p_respond * len(ordered)) - 1))
    nth_rt = ordered[index]

    mean_delay = sum(stop_signal_delays) / len(stop_signal_delays)
    return nth_rt - mean_delay


def tower_of_london_score(
    problems: Sequence[tuple[int, int, float]],
) -> dict[str, float | None]:
    """Score a Tower of London planning task.

    Args:
        problems: ``(moves_made, minimum_moves, first_move_latency_ms)`` per problem.

    Returns:
        Dict with:

        - ``solved_optimally``: fraction solved in the minimum number of moves.
        - ``excess_moves``: mean moves above minimum -- the core efficiency measure.
        - ``mean_planning_latency``: mean latency before the first move. Longer
          latencies with fewer excess moves indicate a plan-then-act strategy.
        - ``planning_efficiency``: correlation between latency and excess moves, or
          ``None`` with fewer than 3 problems or zero variance. **Negative values mean
          longer planning produced better solutions.**

    Raises:
        ValueError: If ``problems`` is empty or any ``minimum_moves`` is < 1.

    References:
        Shallice, T. (1982). Specific impairments of planning. *Philosophical
        Transactions of the Royal Society B*, 298(1089), 199-209.
    """
    if not problems:
        raise ValueError("no problems supplied")
    if any(minimum < 1 for _, minimum, _ in problems):
        raise ValueError("minimum_moves must be at least 1")

    excess = [float(moves - minimum) for moves, minimum, _ in problems]
    latencies = [latency for _, _, latency in problems]

    efficiency: float | None = None
    if len(problems) >= 3:
        mean_latency = sum(latencies) / len(latencies)
        mean_excess = sum(excess) / len(excess)
        covariance = sum(
            (lat - mean_latency) * (exc - mean_excess)
            for lat, exc in zip(latencies, excess, strict=True)
        )
        var_latency = sum((lat - mean_latency) ** 2 for lat in latencies)
        var_excess = sum((exc - mean_excess) ** 2 for exc in excess)
        if var_latency > 0 and var_excess > 0:
            efficiency = covariance / math.sqrt(var_latency * var_excess)

    return {
        "solved_optimally": sum(1 for e in excess if e == 0) / len(problems),
        "excess_moves": sum(excess) / len(excess),
        "mean_planning_latency": sum(latencies) / len(latencies),
        "planning_efficiency": efficiency,
    }


def trust_game_score(
    sent: float, endowment: float, *, multiplier: float = 3.0, returned: float | None = None
) -> dict[str, float | None]:
    """Score a trust (investment) game round.

    The investor sends some portion of an endowment; it is multiplied en route; the
    trustee returns some portion. The investor's send fraction is the standard
    operationalisation of **trust**; the trustee's return fraction is
    **trustworthiness/reciprocity**.

    .. note::
       "Trust" here means willingness to accept vulnerability for expected gain in this
       specific game. Treating it as a general personality trait, still less as a
       hiring criterion, goes well beyond what the paradigm establishes.

    Args:
        sent: Amount the investor sent.
        endowment: The investor's starting endowment.
        multiplier: Factor applied in transit. Conventionally 3.
        returned: Amount the trustee returned, if the second stage was played.

    Returns:
        Dict with ``trust`` (send fraction), ``amount_received`` (by the trustee),
        ``reciprocity`` (returned / received, or ``None``), and ``investor_payoff``.

    Raises:
        ValueError: On non-positive endowment, out-of-range ``sent``, negative
            ``returned``, or ``multiplier`` < 1.

    References:
        Berg, J., Dickhaut, J., & McCabe, K. (1995). Trust, reciprocity, and social
        history. *Games and Economic Behavior*, 10(1), 122-142.
    """
    if endowment <= 0:
        raise ValueError("endowment must be positive")
    if not 0 <= sent <= endowment:
        raise ValueError(f"sent ({sent}) must be in [0, {endowment}]")
    if multiplier < 1:
        raise ValueError("multiplier must be at least 1")
    if returned is not None and returned < 0:
        raise ValueError("returned must be non-negative")

    received = sent * multiplier
    reciprocity = (returned / received) if (returned is not None and received > 0) else None
    investor_payoff = endowment - sent + (returned or 0.0)

    return {
        "trust": sent / endowment,
        "amount_received": received,
        "reciprocity": reciprocity,
        "investor_payoff": investor_payoff,
    }
