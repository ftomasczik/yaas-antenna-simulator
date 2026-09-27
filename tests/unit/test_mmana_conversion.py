import math

import pytest

from antsim.application import (
    UNIFORM_SEGMENTATION_DIVISOR,
    convert_mmana_to_project,
    derive_nec_segments,
)
from antsim.importers import (
    MmanaCompatibilityError,
    MmanaDocument,
    MmanaEnvironment,
    MmanaLoad,
    MmanaSegmentation,
    MmanaSource,
    MmanaWire,
    analyze_mmana_compatibility,
)
from antsim.domain import FreeSpaceEnvironment
from antsim.projects import AntennaProject, SweepSettings

SPEED_OF_LIGHT_M_PER_S = 299_792_458.0


def _wavelength_m(frequency_mhz: float) -> float:
    return SPEED_OF_LIGHT_M_PER_S / (frequency_mhz * 1e6)


# ---------------------------------------------------------------------------
# derive_nec_segments
# ---------------------------------------------------------------------------


def test_derive_nec_segments_uses_divisor_160():
    assert UNIFORM_SEGMENTATION_DIVISOR == 160

    frequency_mhz = 14.15
    wire_length_m = 10.06

    target_length_m = _wavelength_m(frequency_mhz) / 160
    expected = math.ceil(wire_length_m / target_length_m)
    if expected % 2 == 0:
        expected += 1  # conductor alimentado en este caso

    assert derive_nec_segments(
        wire_length_m, frequency_mhz, requires_center_segment=True
    ) == expected


def test_derive_nec_segments_matches_reference_dipole_convergence_study():
    # Mismo dipolo y misma frecuencia que
    # docs/research/nec-segmentation-convergence.md: 77 segmentos en
    # lambda/160 (verificado independientemente con PyNEC en esa
    # investigación).
    assert derive_nec_segments(10.06, 14.15, requires_center_segment=True) == 77


def test_derive_nec_segments_minimum_of_one():
    # Un conductor mucho mas corto que target_length da bruto=0 antes
    # del piso; con el piso, el resultado nunca es menor que 1.
    tiny_length_m = 1e-9
    segments = derive_nec_segments(
        tiny_length_m, 14.15, requires_center_segment=False
    )
    assert segments == 1


def test_odd_adjustment_applies_only_when_required():
    # Mismo largo y frecuencia; el unico cambio es
    # requires_center_segment. Se usa el largo exacto (no redondeado)
    # del lado del loop cuadrado del estudio de convergencia, que ese
    # estudio ya confirmo que da un bruto par (40) en lambda/160.
    frequency_mhz = 14.15
    wire_length_m = _wavelength_m(frequency_mhz) / 4.0

    not_fed = derive_nec_segments(
        wire_length_m, frequency_mhz, requires_center_segment=False
    )
    fed = derive_nec_segments(
        wire_length_m, frequency_mhz, requires_center_segment=True
    )

    assert not_fed % 2 == 0  # bruto par, confirmado por el estudio de convergencia
    assert fed == not_fed + 1
    assert fed % 2 == 1


@pytest.mark.parametrize(
    ("wire_length_m", "frequency_mhz"),
    [
        (math.nan, 14.15),
        (math.inf, 14.15),
        (0.0, 14.15),
        (-1.0, 14.15),
        (10.0, math.nan),
        (10.0, math.inf),
        (10.0, 0.0),
        (10.0, -14.15),
    ],
)
def test_derive_nec_segments_rejects_invalid_inputs(wire_length_m, frequency_mhz):
    with pytest.raises(ValueError):
        derive_nec_segments(
            wire_length_m, frequency_mhz, requires_center_segment=False
        )


# ---------------------------------------------------------------------------
# convert_mmana_to_project
# ---------------------------------------------------------------------------


def _wire(x1, y1, z1, x2, y2, z2, radius=0.001, segment_override=-1.0) -> MmanaWire:
    return MmanaWire(x1, y1, z1, x2, y2, z2, radius, segment_override)


def _sweep() -> SweepSettings:
    return SweepSettings(start_frequency_mhz=13.5, stop_frequency_mhz=15.5, points=81)


def _document(
    *,
    title="TEST_01",
    frequency_mhz=14.15,
    wires=None,
    sources=None,
    loads=(),
    environment_values=(0.0, 5.0, 0.0, 50.0, 120.0, 60.0, 0.0),
    segmentation_values=(800.0, 80.0, 2.0, 2.0),
    comment=None,
    comment_header=None,
) -> MmanaDocument:
    if wires is None:
        wires = (_wire(-5.03, 0.0, 0.0, 5.03, 0.0, 0.0),)
    if sources is None:
        sources = (MmanaSource(wire_ref="w1c", value1=0.0, value2=1.0),)

    return MmanaDocument(
        title=title,
        marker="*",
        frequency_mhz=frequency_mhz,
        wires_header="***Wires***",
        wires=tuple(wires),
        source_header="***Source***",
        source_flag=0,
        sources=tuple(sources),
        load_header="***Load***",
        load_flag=0,
        loads=tuple(loads),
        segmentation_header="***Segmentation***",
        segmentation=MmanaSegmentation(values=segmentation_values),
        environment_header="***G/H/M/R/AzEl/X***",
        environment=MmanaEnvironment(values=environment_values),
        comment_header=comment_header,
        comment=comment,
        encoding="utf-8",
        line_terminator="\r\n",
    )


def test_converts_experimental_base_dipole():
    # Reproduce 00-base-dipole.maa (C:\dev\mmana-experiments), el
    # experimento controlado que confirmo el contrato de campos usado
    # por todo el trabajo de esta fase.
    document = _document()

    project = convert_mmana_to_project(document, sweep=_sweep())

    assert project.frequency_mhz == 14.15
    assert project.reference_impedance == 50.0
    assert len(project.wires) == 1

    # La conversión MMANA no pasa environment explícitamente: el
    # documento fuente ya es de espacio libre (G=0), y en fase 7A
    # cualquier entorno con tierra se rechaza antes de llegar aquí
    # (analyze_mmana_compatibility -> MmanaCompatibilityError).
    assert project.environment == FreeSpaceEnvironment()

    wire = project.wires[0]
    assert wire.tag == 1
    assert wire.radius_m == 0.001
    assert wire.segments == 77  # ver test_derive_nec_segments_matches_reference_dipole_convergence_study

    assert project.source.wire_tag == 1
    assert project.source.segment == 39  # (77 + 1) // 2
    assert project.source.voltage == pytest.approx(complex(1.0, 0.0))


def test_wire_tags_preserve_document_order():
    wires = (
        _wire(0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        _wire(1.0, 0.0, 0.0, 2.0, 0.0, 0.0),
        _wire(2.0, 0.0, 0.0, 3.0, 0.0, 0.0),
    )
    sources = (MmanaSource(wire_ref="w2c", value1=0.0, value2=1.0),)

    project = convert_mmana_to_project(
        _document(wires=wires, sources=sources), sweep=_sweep()
    )

    assert [wire.tag for wire in project.wires] == [1, 2, 3]


def test_source_is_placed_on_the_correct_wire_and_center_segment():
    wires = (
        _wire(0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        _wire(1.0, 0.0, 0.0, 2.0, 0.0, 0.0),
    )
    sources = (MmanaSource(wire_ref="w2c", value1=0.0, value2=1.0),)

    project = convert_mmana_to_project(
        _document(wires=wires, sources=sources), sweep=_sweep()
    )

    fed_wire = next(w for w in project.wires if w.tag == 2)
    assert project.source.wire_tag == 2
    assert project.source.segment == (fed_wire.segments + 1) // 2
    assert fed_wire.segments % 2 == 1


@pytest.mark.parametrize(
    ("phase_degrees", "expected"),
    [
        (0.0, complex(1.0, 0.0)),
        (90.0, complex(0.0, 1.0)),
        (180.0, complex(-1.0, 0.0)),
    ],
)
def test_phase_and_voltage_conversion(phase_degrees, expected):
    sources = (MmanaSource(wire_ref="w1c", value1=phase_degrees, value2=1.0),)

    project = convert_mmana_to_project(
        _document(sources=sources), sweep=_sweep()
    )

    assert project.source.voltage.real == pytest.approx(expected.real, abs=1e-9)
    assert project.source.voltage.imag == pytest.approx(expected.imag, abs=1e-9)


def test_radius_is_passed_through_in_meters():
    wires = (_wire(-5.03, 0.0, 0.0, 5.03, 0.0, 0.0, radius=0.002),)

    project = convert_mmana_to_project(
        _document(wires=wires), sweep=_sweep()
    )

    assert project.wires[0].radius_m == 0.002


def test_additional_height_applied_to_every_wire_z_coordinate():
    wires = (
        _wire(0.0, 0.0, 8.0, 1.0, 0.0, 8.0),
        _wire(0.0, 0.0, 8.0, -5.0, 0.0, 0.5),
        _wire(1.0, 0.0, 8.0, 5.0, 0.0, 0.5),
    )
    sources = (MmanaSource(wire_ref="w1c", value1=0.0, value2=1.0),)
    # H = 3.0 en el campo G/H/M/R/AzEl/X.
    environment_values = (0.0, 3.0, 0.0, 50.0, 0.0, 0.0, 0.0)

    project = convert_mmana_to_project(
        _document(wires=wires, sources=sources, environment_values=environment_values),
        sweep=_sweep(),
    )

    for original, converted in zip(wires, project.wires):
        assert converted.start.z == pytest.approx(original.z1 + 3.0)
        assert converted.end.z == pytest.approx(original.z2 + 3.0)
        # X/Y no se modifican.
        assert converted.start.x == pytest.approx(original.x1)
        assert converted.start.y == pytest.approx(original.y1)


def test_reference_impedance_comes_from_environment():
    project = convert_mmana_to_project(
        _document(environment_values=(0.0, 0.0, 0.0, 75.0, 0.0, 0.0, 0.0)),
        sweep=_sweep(),
    )

    assert project.reference_impedance == 75.0


def test_metadata_from_title_and_comment():
    project = convert_mmana_to_project(
        _document(
            title="Dipolo de 20 metros",
            comment="Nota de prueba",
            comment_header="### Comment ###",
        ),
        sweep=_sweep(),
    )

    assert project.metadata.name == "Dipolo de 20 metros"
    assert project.metadata.description == "Nota de prueba"


def test_metadata_description_is_empty_when_no_comment():
    project = convert_mmana_to_project(_document(comment=None), sweep=_sweep())

    assert project.metadata.description == ""


def test_sweep_settings_preserved_by_identity():
    sweep = _sweep()

    project = convert_mmana_to_project(_document(), sweep=sweep)

    assert project.sweep is sweep


def test_loads_are_rejected():
    loads = (MmanaLoad(wire_ref="w1c", load_type=1, values=(50.0, 0.0)),)

    with pytest.raises(MmanaCompatibilityError):
        convert_mmana_to_project(_document(loads=loads), sweep=_sweep())


def test_multiple_sources_are_rejected():
    sources = (
        MmanaSource(wire_ref="w1c", value1=0.0, value2=1.0),
        MmanaSource(wire_ref="w1c", value1=0.0, value2=1.0),
    )

    with pytest.raises(MmanaCompatibilityError):
        convert_mmana_to_project(_document(sources=sources), sweep=_sweep())


@pytest.mark.parametrize("ground_code", [1.0, 2.0])
def test_ground_environments_are_rejected(ground_code):
    environment_values = (ground_code, 0.0, 0.0, 50.0, 0.0, 0.0, 0.0)

    with pytest.raises(MmanaCompatibilityError):
        convert_mmana_to_project(
            _document(environment_values=environment_values), sweep=_sweep()
        )


@pytest.mark.parametrize("wire_ref", ["w1b", "w1e", "w1c1", "w1c-2"])
def test_noncentered_or_offset_sources_are_rejected(wire_ref):
    sources = (MmanaSource(wire_ref=wire_ref, value1=0.0, value2=1.0),)

    with pytest.raises(MmanaCompatibilityError):
        convert_mmana_to_project(_document(sources=sources), sweep=_sweep())


def test_incompatible_document_never_produces_a_partial_project():
    loads = (MmanaLoad(wire_ref="w1c", load_type=1, values=(50.0, 0.0)),)
    document = _document(loads=loads)

    with pytest.raises(MmanaCompatibilityError) as error_info:
        convert_mmana_to_project(document, sweep=_sweep())

    # No hay ningun AntennaProject parcial que inspeccionar: la unica
    # salida posible de esta llamada fue la excepcion.
    assert error_info.value.issues
    assert all(issue.severity == "error" for issue in error_info.value.issues)


def test_conversion_is_deterministic():
    document = _document()
    sweep = _sweep()

    first = convert_mmana_to_project(document, sweep=sweep)
    second = convert_mmana_to_project(document, sweep=sweep)

    assert first == second


def test_empty_title_raises_compatibility_error_not_project_metadata_value_error():
    # El titulo vacio es ahora un ERROR de compatibilidad estable
    # (title-empty), detectado ANTES de intentar construir
    # ProjectMetadata. Si esto fallara, convert_mmana_to_project
    # levantaria un ValueError generico de ProjectMetadata en vez de
    # un MmanaCompatibilityError, ocultando la causa real.
    document = _document(title="   ")

    # pytest.raises(MmanaCompatibilityError) por si solo ya distingue
    # esto de un ValueError generico: MmanaCompatibilityError es una
    # subclase de ValueError, pero un ValueError liso (el que
    # lanzaria ProjectMetadata) NO es instancia de
    # MmanaCompatibilityError, asi que un ValueError de
    # ProjectMetadata haria fallar este `with`, no pasarlo por error.
    with pytest.raises(MmanaCompatibilityError) as error_info:
        convert_mmana_to_project(document, sweep=_sweep())

    assert any(issue.code == "title-empty" for issue in error_info.value.issues)


# ---------------------------------------------------------------------------
# Contrato entre analyze_mmana_compatibility y convert_mmana_to_project
# ---------------------------------------------------------------------------


def _compatible_documents() -> list[MmanaDocument]:
    """Varios documentos distintos, todos compatibles por construccion."""
    single_wire = _document()
    three_wires_fed_last = _document(
        wires=(
            _wire(0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            _wire(1.0, 0.0, 0.0, 2.0, 0.0, 0.0),
            _wire(2.0, 0.0, 0.0, 3.0, 0.0, 0.0),
        ),
        sources=(MmanaSource(wire_ref="w3c", value1=0.0, value2=1.0),),
    )
    phase_90 = _document(
        sources=(MmanaSource(wire_ref="w1c", value1=90.0, value2=2.5),)
    )
    phase_beyond_360 = _document(
        sources=(MmanaSource(wire_ref="w1c", value1=450.0, value2=1.0),)
    )
    custom_reference_impedance = _document(
        environment_values=(0.0, 0.0, 0.0, 75.0, 0.0, 0.0, 0.0)
    )
    negative_height = _document(
        environment_values=(0.0, -3.5, 0.0, 50.0, 0.0, 0.0, 0.0)
    )
    with_comment = _document(comment="Nota", comment_header="### Comment ###")
    without_comment = _document(comment=None)

    return [
        single_wire,
        three_wires_fed_last,
        phase_90,
        phase_beyond_360,
        custom_reference_impedance,
        negative_height,
        with_comment,
        without_comment,
    ]


@pytest.mark.parametrize("document", _compatible_documents())
def test_every_compatible_document_converts_without_mmana_attributable_errors(
    document,
):
    """Contrato central de esta fase: compatible implica convertible.

    Para cada documento con is_compatible == True,
    convert_mmana_to_project debe completar sin lanzar ninguna
    excepcion atribuible al contenido MMANA (en particular, nunca
    MmanaCompatibilityError: eso significaria que
    analyze_mmana_compatibility no esta garantizando realmente todas
    las precondiciones que usa la conversion).
    """
    assert analyze_mmana_compatibility(document).is_compatible

    project = convert_mmana_to_project(document, sweep=_sweep())

    assert isinstance(project, AntennaProject)
