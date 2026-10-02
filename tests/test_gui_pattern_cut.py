"""`CutSelection`: modelo del corte a dibujar (sin Qt).

Los ángulos de prueba son irregulares a propósito: así se comprueba que
la selección usa los ángulos reales del resultado y no los reconstruye
a partir de inicio y paso.
"""

import dataclasses

import pytest

from yaas.application import RadiationPatternAnalysis, summarize_radiation_pattern
from yaas.domain import RadiationPatternResult
from yaas.gui.controllers.pattern_cut import (
    DEFAULT_FLOOR_DB,
    PLOT_RANGE_DB,
    CutKind,
    CutSelection,
    available_cut_kinds,
    plot_floor_db,
)

THETA = (0.0, 7.5, 30.0, 90.0)
PHI = (0.0, 45.0, 100.0, 270.0, 359.0)


def analysis(theta=THETA, phi=PHI, gain=2.15):
    result = RadiationPatternResult(
        frequency_mhz=14.15,
        theta_angles_deg=tuple(theta),
        phi_angles_deg=tuple(phi),
        gain_db=tuple(tuple(gain for _ in phi) for _ in theta),
    )
    return RadiationPatternAnalysis(
        result=result, summary=summarize_radiation_pattern(result)
    )


@pytest.mark.parametrize(
    ("theta", "phi", "kinds"),
    [
        (THETA, (0.0,), (CutKind.VERTICAL,)),
        ((90.0,), PHI, (CutKind.AZIMUTH,)),
        (THETA, PHI, (CutKind.VERTICAL, CutKind.AZIMUTH)),
        ((90.0,), (0.0,), (CutKind.VERTICAL,)),
    ],
    ids=["theta-sweep", "phi-sweep", "full-grid", "single-direction"],
)
def test_available_kinds_by_shape(theta, phi, kinds):
    assert available_cut_kinds(analysis(theta, phi)) == kinds


def test_theta_sweep_selects_the_only_phi():
    selection = CutSelection.initial(analysis(THETA, (0.0,)))

    assert selection.kind is CutKind.VERTICAL
    assert selection.angles_deg == (0.0,)
    assert selection.fixed_angle_deg == 0.0
    assert not selection.can_change_kind
    assert not selection.can_change_angle


def test_phi_sweep_selects_the_only_theta():
    selection = CutSelection.initial(analysis((90.0,), PHI))

    assert selection.kind is CutKind.AZIMUTH
    assert selection.angles_deg == (90.0,)
    assert selection.fixed_angle_deg == 90.0
    assert not selection.can_change_kind
    assert not selection.can_change_angle


def test_single_direction_is_a_stable_one_point_vertical_cut():
    selection = CutSelection.initial(analysis((90.0,), (0.0,)))

    assert selection == CutSelection(
        analysis=selection.analysis, kind=CutKind.VERTICAL
    )
    assert not selection.can_change_kind
    assert not selection.can_change_angle
    with pytest.raises(ValueError):
        selection.with_kind(CutKind.AZIMUTH)


def test_full_grid_starts_deterministically_vertical_at_index_zero():
    selection = CutSelection.initial(analysis())

    assert (selection.kind, selection.phi_index, selection.theta_index) == (
        CutKind.VERTICAL, 0, 0,
    )
    assert selection.can_change_kind
    assert selection.can_change_angle


def test_vertical_lists_phi_and_azimuth_lists_theta():
    vertical = CutSelection.initial(analysis())
    azimuth = vertical.with_kind(CutKind.AZIMUTH)

    # Los ángulos reales del resultado, no reconstruidos.
    assert vertical.angles_deg == PHI
    assert azimuth.angles_deg == THETA


@pytest.mark.parametrize("index", [0, len(PHI) - 1])
def test_extreme_phi_indices(index):
    selection = CutSelection.initial(analysis()).with_index(index)

    assert selection.phi_index == index
    assert selection.fixed_angle_deg == PHI[index]


@pytest.mark.parametrize("index", [0, len(THETA) - 1])
def test_extreme_theta_indices(index):
    selection = (
        CutSelection.initial(analysis())
        .with_kind(CutKind.AZIMUTH)
        .with_index(index)
    )

    assert selection.theta_index == index
    assert selection.fixed_angle_deg == THETA[index]


def test_each_mode_keeps_its_own_index():
    selection = (
        CutSelection.initial(analysis())
        .with_index(3)  # phi = 270
        .with_kind(CutKind.AZIMUTH)
        .with_index(2)  # theta = 30
    )

    assert (selection.phi_index, selection.theta_index) == (3, 2)
    back = selection.with_kind(CutKind.VERTICAL)
    assert back.fixed_angle_deg == 270.0
    assert back.with_kind(CutKind.AZIMUTH).fixed_angle_deg == 30.0


@pytest.mark.parametrize("index", [-1, len(PHI), True, 1.0])
def test_invalid_indices_are_rejected(index):
    with pytest.raises(ValueError):
        CutSelection.initial(analysis()).with_index(index)


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "vertical"},
        {"theta_index": len(THETA)},
        {"phi_index": -1},
        {"analysis": object()},
    ],
)
def test_selection_validates_fields(changes):
    valid = {"analysis": analysis(), "kind": CutKind.VERTICAL}

    with pytest.raises(ValueError):
        CutSelection(**{**valid, **changes})


def test_floor_follows_the_summary_maximum_and_is_the_same_for_every_cut():
    selection = CutSelection.initial(analysis(gain=-3.2))

    assert selection.floor_db == -4.0 - PLOT_RANGE_DB
    assert selection.with_kind(CutKind.AZIMUTH).floor_db == selection.floor_db
    assert plot_floor_db(selection.analysis) == selection.floor_db


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
    assert CutSelection.initial(empty).floor_db == DEFAULT_FLOOR_DB


def test_selection_never_modifies_the_result():
    original = analysis()
    snapshot = dataclasses.replace(original.result)

    CutSelection.initial(original).with_kind(CutKind.AZIMUTH).with_index(3)

    assert original.result == snapshot


def test_selection_is_immutable():
    selection = CutSelection.initial(analysis())

    with pytest.raises(dataclasses.FrozenInstanceError):
        selection.phi_index = 1
