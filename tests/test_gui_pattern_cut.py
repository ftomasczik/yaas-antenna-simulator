"""Elección del corte inicial de un patrón calculado (sin Qt)."""

import dataclasses

import pytest

from yaas.application import RadiationPatternAnalysis, summarize_radiation_pattern
from yaas.domain import RadiationPatternResult
from yaas.gui.controllers.pattern_cut import (
    DEFAULT_FLOOR_DB,
    PLOT_RANGE_DB,
    CutKind,
    PatternCut,
    choose_initial_cut,
    plot_floor_db,
)


def analysis(theta, phi, gain=2.15):
    result = RadiationPatternResult(
        frequency_mhz=14.15,
        theta_angles_deg=tuple(theta),
        phi_angles_deg=tuple(phi),
        gain_db=tuple(tuple(gain for _ in phi) for _ in theta),
    )
    return RadiationPatternAnalysis(
        result=result, summary=summarize_radiation_pattern(result)
    )


def test_vertical_cut_for_theta_sweep():
    cut = choose_initial_cut(analysis(range(0, 181, 10), [0.0]))

    assert cut == PatternCut(
        kind=CutKind.VERTICAL,
        index=0,
        floor_db=2.0 - PLOT_RANGE_DB,
        has_more_cuts=False,
    )


def test_azimuth_cut_for_phi_sweep():
    cut = choose_initial_cut(analysis([90.0], range(0, 361, 10)))

    assert cut.kind is CutKind.AZIMUTH
    assert cut.index == 0
    assert not cut.has_more_cuts


def test_full_grid_starts_with_the_first_vertical_cut_and_flags_more():
    cut = choose_initial_cut(analysis(range(0, 91, 10), range(0, 360, 90)))

    assert cut.kind is CutKind.VERTICAL
    assert cut.index == 0
    # Hará falta un selector para ver los demás cortes.
    assert cut.has_more_cuts


def test_single_direction_is_a_one_point_vertical_cut():
    cut = choose_initial_cut(analysis([90.0], [0.0]))

    assert cut.kind is CutKind.VERTICAL
    assert not cut.has_more_cuts


def test_floor_follows_the_summary_maximum():
    assert plot_floor_db(analysis([0.0, 10.0], [0.0], gain=-3.2)) == -4.0 - PLOT_RANGE_DB


def test_floor_without_maximum_uses_the_default():
    result = RadiationPatternResult(
        frequency_mhz=14.15,
        theta_angles_deg=(0.0, 10.0),
        phi_angles_deg=(0.0,),
        gain_db=((None,), (None,)),
    )
    empty = RadiationPatternAnalysis(
        result=result, summary=summarize_radiation_pattern(result)
    )

    assert plot_floor_db(empty) == DEFAULT_FLOOR_DB
    assert choose_initial_cut(empty).floor_db == DEFAULT_FLOOR_DB


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "vertical"},
        {"index": -1},
        {"index": True},
        {"floor_db": float("nan")},
    ],
)
def test_cut_validates_fields(changes):
    valid = {
        "kind": CutKind.VERTICAL,
        "index": 0,
        "floor_db": -40.0,
        "has_more_cuts": False,
    }

    with pytest.raises(ValueError):
        PatternCut(**{**valid, **changes})


def test_cut_is_immutable():
    cut = choose_initial_cut(analysis([0.0, 10.0], [0.0]))

    with pytest.raises(dataclasses.FrozenInstanceError):
        cut.index = 1
