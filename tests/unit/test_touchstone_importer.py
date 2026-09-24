import pytest

from antsim.importers import (
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
        match="solamente se admite el formato RI",
    ):
        parse_touchstone_s1p(
            "# MHz S MA R 50\n"
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