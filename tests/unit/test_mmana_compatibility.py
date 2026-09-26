import pytest

from antsim.importers import (
    MmanaCompatibilityError,
    MmanaDocument,
    MmanaEnvironment,
    MmanaEnvironmentKind,
    MmanaLcqLoad,
    MmanaLoad,
    MmanaResistiveLoad,
    MmanaSegmentation,
    MmanaSource,
    MmanaWire,
    MmanaWireReference,
    analyze_mmana_compatibility,
    interpret_environment,
    interpret_load,
    interpret_segment_override,
    interpret_source,
)


# ---------------------------------------------------------------------------
# MmanaWireReference
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "anchor"),
    [
        ("w1b", "begin"),
        ("w1c", "center"),
        ("w1e", "end"),
    ],
)
def test_parses_begin_center_end_anchors(raw, anchor):
    reference = MmanaWireReference.parse(raw)

    assert reference.wire_number == 1
    assert reference.anchor == anchor
    assert reference.pulse_offset == 0


@pytest.mark.parametrize(
    ("raw", "expected_offset"),
    [
        ("w3c1", 1),
        ("w2c-2", -2),
        ("w5e3", 3),
        ("w1c0", 0),
    ],
)
def test_parses_positive_negative_and_zero_offsets(raw, expected_offset):
    reference = MmanaWireReference.parse(raw)

    assert reference.pulse_offset == expected_offset


@pytest.mark.parametrize(
    "raw",
    [
        "w0c",  # número de conductor no positivo
        "w01b",  # cero a la izquierda
        "w1x",  # ancla desconocida
        "1c",  # falta el prefijo "w"
        "wc1",  # falta el número de conductor
        "w1cX",  # texto adicional al final
        "w1c1x",  # texto adicional tras el desplazamiento
        "w1c+2",  # signo explícito no admitido
        "",  # vacío
        "w1",  # falta el ancla
    ],
)
def test_rejects_invalid_wire_reference_syntax(raw):
    with pytest.raises(ValueError, match="sintaxis inválida"):
        MmanaWireReference.parse(raw)


# ---------------------------------------------------------------------------
# Interpretación semántica de fuentes, cargas, entorno y segmentación
# ---------------------------------------------------------------------------


def test_interpret_source_exposes_phase_and_voltage():
    semantics = interpret_source(
        MmanaSource(wire_ref="w1c", value1=90.0, value2=0.5)
    )

    assert semantics.wire_reference == MmanaWireReference.parse("w1c")
    assert semantics.phase_degrees == 90.0
    assert semantics.voltage_volts == 0.5


def test_interpret_load_type_one_is_resistive():
    load = interpret_load(
        MmanaLoad(wire_ref="w1c1", load_type=1, values=(50.0, 0.0))
    )

    assert isinstance(load, MmanaResistiveLoad)
    assert load.wire_reference == MmanaWireReference.parse("w1c1")
    assert load.resistance_ohm == 50.0
    assert load.reactance_ohm == 0.0


def test_interpret_load_type_zero_is_lcq():
    load = interpret_load(
        MmanaLoad(wire_ref="w1c1", load_type=0, values=(10.0, 100.0, 50.0))
    )

    assert isinstance(load, MmanaLcqLoad)
    assert load.inductance_uh == 10.0
    assert load.capacitance_pf == 100.0
    assert load.quality_factor == 50.0


def test_interpret_load_rejects_wrong_value_count():
    with pytest.raises(ValueError, match="exactamente 2"):
        interpret_load(MmanaLoad(wire_ref="w1b", load_type=1, values=(1.0,)))

    with pytest.raises(ValueError, match="exactamente 3"):
        interpret_load(
            MmanaLoad(wire_ref="w1b", load_type=0, values=(1.0, 2.0))
        )


def test_interpret_environment_kinds():
    free_space = interpret_environment(
        MmanaEnvironment(values=(0.0, 5.0, 0.0, 50.0, 120.0, 60.0, 0.0))
    )
    perfect_ground = interpret_environment(
        MmanaEnvironment(values=(1.0, 5.0, 0.0, 50.0, 120.0, 60.0, 0.0))
    )
    real_ground = interpret_environment(
        MmanaEnvironment(values=(2.0, 5.0, 0.0, 50.0, 120.0, 60.0, 0.0))
    )

    assert free_space.kind is MmanaEnvironmentKind.FREE_SPACE
    assert perfect_ground.kind is MmanaEnvironmentKind.PERFECT_GROUND
    assert real_ground.kind is MmanaEnvironmentKind.REAL_GROUND
    assert free_space.reference_impedance_ohm == 50.0


def test_interpret_environment_exposes_additional_height_and_keeps_m_x_opaque():
    semantics = interpret_environment(
        MmanaEnvironment(values=(0.0, 12.5, 3.0, 50.0, 120.0, 60.0, 7.0))
    )

    assert semantics.additional_height_m == 12.5
    # M y X (en ese orden, junto a Az/El) permanecen opacos.
    assert semantics.unconfirmed_fields == (3.0, 120.0, 60.0, 7.0)


def test_interpret_segment_override_contract():
    from antsim.importers import MmanaSegmentOverrideKind as Kind

    assert interpret_segment_override(5.0) is Kind.MANUAL
    assert interpret_segment_override(0.0) is Kind.AUTOMATIC
    assert interpret_segment_override(-1.0) is Kind.TAPER_BOTH_ENDS
    assert interpret_segment_override(-2.0) is Kind.TAPER_FROM_BEGIN
    assert interpret_segment_override(-3.0) is Kind.TAPER_FROM_END
    assert interpret_segment_override(-4.0) is None
    assert interpret_segment_override(1.5) is None


# ---------------------------------------------------------------------------
# analyze_mmana_compatibility
# ---------------------------------------------------------------------------


def _wire(
    x1=-5.03,
    y1=0.0,
    z1=0.0,
    x2=5.03,
    y2=0.0,
    z2=0.0,
    radius=0.001,
    segment_override=-1.0,
) -> MmanaWire:
    return MmanaWire(x1, y1, z1, x2, y2, z2, radius, segment_override)


def _document(
    *,
    frequency_mhz=14.15,
    wires=None,
    sources=None,
    loads=(),
    environment_values=(0.0, 5.0, 0.0, 50.0, 0.0, 0.0, 0.0),
    segmentation_values=(400.0, 40.0, 2.0, 1.0),
    title="Dipolo de prueba",
    comment=None,
    comment_header=None,
    wires_header="***Wires***",
    source_header="*** Source ***",
    load_header="*** Load ***",
    segmentation_header="*** Segmentation ***",
    environment_header="*** G/H/M/R/AzEl/X ***",
) -> MmanaDocument:
    if wires is None:
        wires = (_wire(),)
    if sources is None:
        sources = (MmanaSource(wire_ref="w1c", value1=0.0, value2=1.0),)

    return MmanaDocument(
        title=title,
        marker="*",
        frequency_mhz=frequency_mhz,
        wires_header=wires_header,
        wires=tuple(wires),
        source_header=source_header,
        source_flag=0,
        sources=tuple(sources),
        load_header=load_header,
        load_flag=0,
        loads=tuple(loads),
        segmentation_header=segmentation_header,
        segmentation=MmanaSegmentation(values=segmentation_values),
        environment_header=environment_header,
        environment=MmanaEnvironment(values=environment_values),
        comment_header=comment_header,
        comment=comment,
        encoding="utf-8",
        line_terminator="\r\n",
    )


def test_minimal_compatible_document_has_no_errors():
    # El único segment_override admitido hoy (-1, tapering en ambos
    # extremos) siempre trae aparejada la advertencia de que AntSim no
    # puede reproducirlo exactamente: un documento compatible con cero
    # advertencias es imposible por diseño (ver
    # docs/research/mmana-format-characterization.md).
    report = analyze_mmana_compatibility(_document())

    assert report.is_compatible
    assert report.errors == ()
    assert [issue.code for issue in report.warnings] == [
        "segmentation-taper-not-reproducible"
    ]
    report.raise_if_incompatible()  # no debe lanzar


def test_multiple_sources_is_an_error():
    document = _document(
        sources=(
            MmanaSource(wire_ref="w1c", value1=0.0, value2=1.0),
            MmanaSource(wire_ref="w1c", value1=0.0, value2=1.0),
        )
    )

    report = analyze_mmana_compatibility(document)

    assert not report.is_compatible
    assert any(issue.code == "source-count-invalid" for issue in report.errors)


def test_no_sources_is_an_error():
    document = _document(sources=())

    report = analyze_mmana_compatibility(document)

    assert any(issue.code == "source-count-invalid" for issue in report.errors)


def test_source_referencing_unknown_wire_is_an_error():
    document = _document(
        sources=(MmanaSource(wire_ref="w5c", value1=0.0, value2=1.0),)
    )

    report = analyze_mmana_compatibility(document)

    assert any(issue.code == "wire-reference-unknown" for issue in report.errors)


def test_noncentered_source_is_an_error():
    document = _document(
        sources=(MmanaSource(wire_ref="w1b", value1=0.0, value2=1.0),)
    )

    report = analyze_mmana_compatibility(document)

    assert any(issue.code == "source-not-centered" for issue in report.errors)


def test_source_with_offset_is_an_error():
    document = _document(
        sources=(MmanaSource(wire_ref="w1c1", value1=0.0, value2=1.0),)
    )

    report = analyze_mmana_compatibility(document)

    assert any(issue.code == "source-not-centered" for issue in report.errors)


def test_source_with_invalid_reference_syntax_is_an_error():
    document = _document(
        sources=(MmanaSource(wire_ref="w1x", value1=0.0, value2=1.0),)
    )

    report = analyze_mmana_compatibility(document)

    assert any(
        issue.code == "wire-reference-syntax-invalid" for issue in report.errors
    )


@pytest.mark.parametrize(
    "load",
    [
        MmanaLoad(wire_ref="w1c1", load_type=1, values=(50.0, 0.0)),
        MmanaLoad(wire_ref="w1c1", load_type=0, values=(10.0, 100.0, 50.0)),
    ],
)
def test_loads_present_is_an_error_for_both_types(load):
    document = _document(loads=(load,))

    report = analyze_mmana_compatibility(document)

    assert any(issue.code == "loads-present" for issue in report.errors)


@pytest.mark.parametrize(
    ("environment_g", "expected_g_repr"),
    [
        (1.0, "1.0"),
        (2.0, "2.0"),
    ],
)
def test_ground_environments_are_errors(environment_g, expected_g_repr):
    document = _document(
        environment_values=(environment_g, 5.0, 0.0, 50.0, 0.0, 0.0, 0.0)
    )

    report = analyze_mmana_compatibility(document)

    ground_issues = [
        issue for issue in report.errors if issue.code == "environment-not-free-space"
    ]
    assert len(ground_issues) == 1
    assert expected_g_repr in ground_issues[0].message


def test_free_space_environment_is_not_an_error():
    document = _document(environment_values=(0.0, 5.0, 0.0, 50.0, 0.0, 0.0, 0.0))

    report = analyze_mmana_compatibility(document)

    assert not any(
        issue.code == "environment-not-free-space" for issue in report.errors
    )


@pytest.mark.parametrize("radius", [0.0, -0.001])
def test_invalid_radius_is_an_error(radius):
    document = _document(wires=(_wire(radius=radius),))

    report = analyze_mmana_compatibility(document)

    assert any(issue.code == "wire-radius-invalid" for issue in report.errors)


@pytest.mark.parametrize("frequency", [0.0, -14.15])
def test_invalid_frequency_is_an_error(frequency):
    document = _document(frequency_mhz=frequency)

    report = analyze_mmana_compatibility(document)

    assert any(issue.code == "frequency-invalid" for issue in report.errors)


@pytest.mark.parametrize("reference_impedance", [0.0, -50.0])
def test_invalid_reference_impedance_is_an_error(reference_impedance):
    document = _document(
        environment_values=(0.0, 5.0, 0.0, reference_impedance, 0.0, 0.0, 0.0)
    )

    report = analyze_mmana_compatibility(document)

    assert any(
        issue.code == "reference-impedance-invalid" for issue in report.errors
    )


@pytest.mark.parametrize("segment_override", [1.0, 0.0, -2.0, -3.0])
def test_unsupported_segment_override_is_an_error(segment_override):
    document = _document(wires=(_wire(segment_override=segment_override),))

    report = analyze_mmana_compatibility(document)

    assert any(
        issue.code == "wire-segment-override-unsupported" for issue in report.errors
    )


def test_taper_both_ends_segment_override_is_accepted_with_warning():
    document = _document(wires=(_wire(segment_override=-1.0),))

    report = analyze_mmana_compatibility(document)

    assert not any(
        issue.code == "wire-segment-override-unsupported" for issue in report.errors
    )
    assert any(
        issue.code == "segmentation-taper-not-reproducible"
        for issue in report.warnings
    )


@pytest.mark.parametrize("dm1_dm2", [(0.0, 40.0), (400.0, 0.0), (-1.0, 40.0)])
def test_invalid_segmentation_parameters_are_an_error(dm1_dm2):
    dm1, dm2 = dm1_dm2
    document = _document(segmentation_values=(dm1, dm2, 2.0, 1.0))

    report = analyze_mmana_compatibility(document)

    assert any(issue.code == "segmentation-invalid" for issue in report.errors)


@pytest.mark.parametrize("sc", [1.0, 3.0, 0.5, 3.5])
def test_sc_outside_documented_range_is_an_error(sc):
    document = _document(segmentation_values=(400.0, 40.0, sc, 1.0))

    report = analyze_mmana_compatibility(document)

    assert any(issue.code == "segmentation-invalid" for issue in report.errors)


@pytest.mark.parametrize("ec", [0.0, -1.0, 1.5])
def test_ec_not_a_positive_integer_is_an_error(ec):
    document = _document(segmentation_values=(400.0, 40.0, 2.0, ec))

    report = analyze_mmana_compatibility(document)

    assert any(issue.code == "segmentation-invalid" for issue in report.errors)


def test_valid_segmentation_parameters_are_not_an_error():
    document = _document(segmentation_values=(400.0, 40.0, 2.0, 1.0))

    report = analyze_mmana_compatibility(document)

    assert not any(issue.code == "segmentation-invalid" for issue in report.errors)


def test_no_relational_check_between_dm1_and_dm2():
    # DM1 < DM2 no está respaldado por documentación ni por una
    # decisión explícita: no debe rechazarse solo por eso.
    document = _document(segmentation_values=(10.0, 4000.0, 2.0, 1.0))

    report = analyze_mmana_compatibility(document)

    assert not any(issue.code == "segmentation-invalid" for issue in report.errors)


def test_expected_warnings_are_reported():
    document = _document(
        title="",
        comment_header="### Comment ###",
        comment="   ",
        sources=(MmanaSource(wire_ref="w1c", value1=5.0, value2=1.0),),
        environment_values=(0.0, 5.0, 0.0, 50.0, 90.0, 0.0, 0.0),
        wires_header="Wires!",
    )

    report = analyze_mmana_compatibility(document)

    codes = {issue.code for issue in report.warnings}
    assert "title-empty" in codes
    assert "comment-empty" in codes
    assert "source-phase-nonzero" in codes
    assert "environment-azel-not-preserved" in codes
    assert "section-header-noncanonical" in codes
    assert "segmentation-taper-not-reproducible" in codes
    assert report.is_compatible


def test_issue_codes_are_stable_identifiers_not_translated_sentences():
    document = _document(sources=())
    report = analyze_mmana_compatibility(document)

    for issue in report.issues:
        assert issue.code == issue.code.lower()
        assert " " not in issue.code
        assert issue.code.replace("-", "").isalnum()


def test_report_with_several_simultaneous_problems():
    document = _document(
        wires=(_wire(radius=-1.0),),
        sources=(
            MmanaSource(wire_ref="w1c", value1=0.0, value2=1.0),
            MmanaSource(wire_ref="w9c", value1=0.0, value2=1.0),
        ),
        loads=(MmanaLoad(wire_ref="w1c1", load_type=1, values=(50.0, 0.0)),),
        environment_values=(2.0, 5.0, 0.0, -50.0, 0.0, 0.0, 0.0),
    )

    report = analyze_mmana_compatibility(document)

    codes = {issue.code for issue in report.errors}
    assert {
        "wire-radius-invalid",
        "source-count-invalid",
        "wire-reference-unknown",
        "loads-present",
        "environment-not-free-space",
        "reference-impedance-invalid",
    } <= codes
    assert not report.is_compatible

    with pytest.raises(MmanaCompatibilityError) as error_info:
        report.raise_if_incompatible()

    assert set(issue.code for issue in error_info.value.issues) == codes
