import pytest

from yaas.importers import (
    TouchstoneFormatError,
    load_touchstone_s1p,
    parse_touchstone_s1p,
)


def test_parse_touchstone_ri():
    sweep = parse_touchstone_s1p(
        """
! NanoVNA example
# MHz S RI R 50
14.000 0.20 -0.10
14.100 0.10 -0.05 ! inline comment
14.200 0.00 0.00
"""
    )

    assert len(sweep.points) == 3
    assert sweep.start_frequency_mhz == 14.0
    assert sweep.stop_frequency_mhz == 14.2
    assert sweep.reference_impedance == 50.0
    assert (
        sweep.points[0].reflection_coefficient
        == complex(0.20, -0.10)
    )
    assert sweep.points[-1].swr == pytest.approx(1.0)


def test_parse_touchstone_converts_hz_to_mhz():
    sweep = parse_touchstone_s1p(
        """
# Hz S RI R 50
14000000 0.0 0.0
14100000 0.1 0.0
"""
    )

    assert sweep.start_frequency_mhz == 14.0
    assert sweep.stop_frequency_mhz == 14.1


def test_parse_touchstone_ma():
    sweep = parse_touchstone_s1p(
        """
# MHz S MA R 50
14.0 0.5 90.0
"""
    )

    coefficient = (
        sweep.points[0].reflection_coefficient
    )

    assert coefficient.real == pytest.approx(
        0.0,
        abs=1e-12,
    )
    assert coefficient.imag == pytest.approx(0.5)


def test_parse_touchstone_db():
    sweep = parse_touchstone_s1p(
        """
# MHz S DB R 50
14.0 -6.020599913 180.0
"""
    )

    coefficient = (
        sweep.points[0].reflection_coefficient
    )

    assert coefficient.real == pytest.approx(-0.5)
    assert coefficient.imag == pytest.approx(
        0.0,
        abs=1e-12,
    )


def test_load_touchstone_file(tmp_path):
    source = tmp_path / "measurement.s1p"
    source.write_text(
        "# MHz S RI R 50\n"
        "14.0 0.0 0.0\n",
        encoding="utf-8",
    )

    sweep = load_touchstone_s1p(source)

    assert len(sweep.points) == 1
    assert sweep.points[0].frequency_mhz == 14.0


def test_rejects_data_before_options():
    with pytest.raises(
        TouchstoneFormatError,
        match="faltan las opciones",
    ):
        parse_touchstone_s1p(
            "14.0 0.0 0.0\n"
        )


def test_rejects_unsupported_format():
    with pytest.raises(
        TouchstoneFormatError,
        match="formato no compatible",
    ):
        parse_touchstone_s1p(
            "# MHz S XY R 50\n"
            "14.0 0.5 45.0\n"
        )


def test_rejects_malformed_data():
    with pytest.raises(
        TouchstoneFormatError,
        match="tres valores",
    ):
        parse_touchstone_s1p(
            "# MHz S RI R 50\n"
            "14.0 0.5\n"
        )


def test_rejects_empty_measurement():
    with pytest.raises(
        TouchstoneFormatError,
        match="no contiene mediciones",
    ):
        parse_touchstone_s1p(
            "# MHz S RI R 50\n"
        )


def test_rejects_multiple_option_lines():
    with pytest.raises(
        TouchstoneFormatError,
        match="más de un encabezado",
    ):
        parse_touchstone_s1p(
            "# MHz S RI R 50\n"
            "# MHz S RI R 50\n"
            "14.0 0.0 0.0\n"
        )


def test_rejects_unordered_frequencies():
    with pytest.raises(
        TouchstoneFormatError,
        match="estrictamente crecientes",
    ):
        parse_touchstone_s1p(
            "# MHz S RI R 50\n"
            "15.0 0.0 0.0\n"
            "14.0 0.0 0.0\n"
        )

@pytest.mark.parametrize(
    ("unit", "frequency", "expected_mhz"),
    [
        ("Hz", 14_150_000.0, 14.15),
        ("kHz", 14_150.0, 14.15),
        ("MHz", 14.15, 14.15),
        ("GHz", 0.01415, 14.15),
    ],
)
def test_converts_frequency_units_to_mhz(
    unit,
    frequency,
    expected_mhz,
):
    sweep = parse_touchstone_s1p(
        f"# {unit} S RI R 50\n"
        f"{frequency} 0.0 0.0\n"
    )

    assert (
        sweep.points[0].frequency_mhz
        == pytest.approx(expected_mhz)
    )


def test_touchstone_options_are_case_insensitive():
    sweep = parse_touchstone_s1p(
        "# mhz s ma r 50\n"
        "14.15 0.5 0.0\n"
    )

    assert (
        sweep.points[0].reflection_coefficient
        == pytest.approx(complex(0.5, 0.0))
    )