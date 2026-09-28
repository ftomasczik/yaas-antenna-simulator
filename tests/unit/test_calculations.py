import math

import pytest

from yaas.domain import calculate_swr


def test_swr_is_one_for_perfect_match():
    swr = calculate_swr(complex(50.0, 0.0))

    assert swr == pytest.approx(1.0)


def test_swr_for_reference_dipole_result():
    impedance = complex(67.43, -31.25)

    swr = calculate_swr(impedance)

    assert swr == pytest.approx(1.83, rel=0.01)


def test_swr_rejects_invalid_reference_impedance():
    with pytest.raises(ValueError):
        calculate_swr(
            impedance=complex(50.0, 0.0),
            reference_impedance=0.0,
        )


def test_swr_is_infinite_for_open_circuit():
    swr = calculate_swr(complex(math.inf, 0.0))

    assert math.isinf(swr)