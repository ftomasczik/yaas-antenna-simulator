import pytest

from yaas.importers import (
    MmanaFormatError,
    load_mmana,
    parse_mmana,
)


def _document_text(
    *,
    title="Antena de prueba",
    frequency="14.15",
    wires=("0.0,\t0.0,\t0.0,\t1.0,\t0.0,\t0.0,\t0.001,\t-1",),
    source_flag=1,
    sources=("w1b,\t0.0,\t1.0",),
    load_flag=1,
    loads=(),
    segmentation="400,\t40,\t2.0,\t1",
    environment="0,\t0.0,\t0,\t50.0,\t120,\t60,\t0",
    comment=None,
    trailing_extra=None,
):
    """Construye el texto de un documento .maa sintético válido por defecto."""
    lines = [
        title,
        "*",
        frequency,
        "***Wires***",
        str(len(wires)),
        *wires,
        "*** Source ***",
        f"{len(sources)},\t{source_flag}",
        *sources,
        "*** Load ***",
        f"{len(loads)},\t{load_flag}",
        *loads,
        "*** Segmentation ***",
        segmentation,
        "*** G/H/M/R/AzEl/X ***",
        environment,
    ]
    if comment is not None:
        lines.append("### Comment ###")
        lines.extend(comment.splitlines())
    if trailing_extra is not None:
        lines.extend(trailing_extra)
    return "\n".join(lines) + "\n"


def test_parses_minimal_valid_document():
    document = parse_mmana(_document_text())

    assert document.title == "Antena de prueba"
    assert document.marker == "*"
    assert document.frequency_mhz == 14.15
    assert len(document.wires) == 1
    assert document.wires[0].x2 == 1.0
    assert document.wires[0].segment_override == -1.0
    assert len(document.sources) == 1
    assert document.sources[0].wire_ref == "w1b"
    assert document.source_flag == 1
    assert document.loads == ()
    assert document.load_flag == 1
    assert document.segmentation.values == (400.0, 40.0, 2.0, 1.0)
    assert document.environment.values == (0.0, 0.0, 0.0, 50.0, 120.0, 60.0, 0.0)
    assert document.comment_header is None
    assert document.comment is None


def test_parses_multiple_wires():
    wires = (
        "0.0,\t0.0,\t0.0,\t1.0,\t0.0,\t0.0,\t0.001,\t-1",
        "1.0,\t0.0,\t0.0,\t2.0,\t0.0,\t0.0,\t0.002,\t-1",
        "2.0,\t0.0,\t0.0,\t3.0,\t0.0,\t0.0,\t0.003,\t-1",
    )
    document = parse_mmana(_document_text(wires=wires))

    assert len(document.wires) == 3
    assert document.wires[2].x1 == 2.0
    assert document.wires[2].radius == 0.003


@pytest.mark.parametrize(
    "sources",
    [
        ("w1b,\t0.0,\t1.0",),
        ("w5c,\t0.0,\t0.5", "w6c,\t0.0,\t0.5"),
    ],
)
def test_parses_single_and_multiple_sources(sources):
    document = parse_mmana(_document_text(sources=sources))

    expected_refs = tuple(row.split(",")[0] for row in sources)

    assert len(document.sources) == len(sources)
    assert tuple(source.wire_ref for source in document.sources) == expected_refs


def test_preserves_load_types_without_interpretation():
    loads = (
        "w1e,\t0,\t40.0,\t0.0,\t200.0",
        "w1b,\t1,\t10.0,\t0.0",
    )
    document = parse_mmana(_document_text(loads=loads))

    assert len(document.loads) == 2

    trap_like = document.loads[0]
    assert trap_like.wire_ref == "w1e"
    assert trap_like.load_type == 0
    assert trap_like.values == (40.0, 0.0, 200.0)

    resistive = document.loads[1]
    assert resistive.wire_ref == "w1b"
    assert resistive.load_type == 1
    assert resistive.values == (10.0, 0.0)


def test_load_with_same_wire_ref_twice_is_preserved():
    loads = (
        "w2c,\t0,\t1.214245,\t79.0,\t200.0",
        "w2c,\t0,\t0.638275,\t62.0,\t200.0",
    )
    document = parse_mmana(_document_text(loads=loads))

    assert len(document.loads) == 2
    assert document.loads[0].wire_ref == document.loads[1].wire_ref == "w2c"
    assert document.loads[0].values != document.loads[1].values


def test_preserves_multiline_comment_as_opaque_text():
    comment = (
        " 5 band delta loop\n"
        " Fres   BW (SWR<2)\n"
        " 3.55  - 200 kHz\n"
        "14.05 - 340 kHz "
    )
    document = parse_mmana(_document_text(comment=comment))

    assert document.comment_header == "### Comment ###"
    assert document.comment == comment


def test_comment_header_without_body_is_empty_string():
    text = _document_text() + "### Comment ###\n"
    document = parse_mmana(text)

    assert document.comment_header == "### Comment ###"
    assert document.comment == ""


def test_unexpected_trailing_content_is_preserved_not_discarded():
    """Contenido final que no sigue el patrón "### Comment ###" no se descarta."""
    document = parse_mmana(
        _document_text(trailing_extra=["#!raw!#", "unlabeled stray data", "42,7"])
    )

    assert document.comment_header == "#!raw!#"
    assert document.comment == "unlabeled stray data\n42,7"


def test_load_mmana_reads_utf8_file(tmp_path):
    destination = tmp_path / "dipole.maa"
    destination.write_text(_document_text(title="Dipole"), encoding="utf-8")

    document = load_mmana(destination)

    assert document.title == "Dipole"
    assert document.encoding == "utf-8"


def test_load_mmana_reads_utf8_with_bom(tmp_path):
    destination = tmp_path / "dipole.maa"
    text = _document_text(title="Dipole con BOM")
    destination.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))

    document = load_mmana(destination)

    assert document.title == "Dipole con BOM"
    assert document.encoding == "utf-8-sig"


def test_load_mmana_reads_cp1251_file_when_signalled_by_undefined_byte(tmp_path):
    # 0x8F es indefinido en CP1252 pero es una letra cirílica válida en
    # CP1251 (Ѐ / U+0407 no; en este caso U+040F "Џ"), así que el
    # detector puede resolverlo sin necesidad de legacy_encoding.
    title_with_decisive_byte = "Џ" + " provoda"
    text = _document_text(title=title_with_decisive_byte)
    destination = tmp_path / "decisive.maa"
    destination.write_bytes(text.encode("cp1251"))

    document = load_mmana(destination)

    assert document.encoding == "cp1251"
    assert document.title == title_with_decisive_byte


def test_load_mmana_rejects_ambiguous_legacy_encoding_without_hint(tmp_path):
    # "café" solo usa el byte 0xE9, definido tanto en CP1251 como en
    # CP1252: es el caso genuinamente ambiguo que no debe resolverse
    # en silencio.
    text = _document_text(title="café")
    destination = tmp_path / "ambiguous.maa"
    destination.write_bytes(text.encode("cp1252"))

    with pytest.raises(MmanaFormatError, match="ambiguo"):
        load_mmana(destination)


def test_load_mmana_uses_explicit_legacy_encoding_cp1252(tmp_path):
    text = _document_text(title="café")
    destination = tmp_path / "latin.maa"
    destination.write_bytes(text.encode("cp1252"))

    document = load_mmana(destination, legacy_encoding="cp1252")

    assert document.encoding == "cp1252"
    assert document.title == "café"


def test_load_mmana_uses_explicit_legacy_encoding_cp1251_on_same_bytes(tmp_path):
    # Los mismos bytes crudos, reinterpretados como CP1251, producen un
    # título en cirílico completamente distinto: demuestra que la
    # elección de codificación no es cosmética.
    text = _document_text(title="café")
    destination = tmp_path / "same-bytes.maa"
    destination.write_bytes(text.encode("cp1252"))

    document = load_mmana(destination, legacy_encoding="cp1251")

    assert document.encoding == "cp1251"
    assert document.title != "café"
    assert document.title.encode("cp1251") == "café".encode("cp1252")


def test_rejects_invalid_marker():
    text = _document_text().replace("\n*\n", "\n**\n", 1)

    with pytest.raises(MmanaFormatError, match="marcador literal"):
        parse_mmana(text)


def test_rejects_incorrect_wire_count():
    # Se declaran 2 conductores pero solo se provee 1: el análisis
    # consume la siguiente línea (el encabezado de fuentes) como si
    # fuera la segunda fila de conductor y falla su validación de
    # forma, revelando el contador incorrecto.
    text = _document_text(wires=("0.0,\t0.0,\t0.0,\t1.0,\t0.0,\t0.0,\t0.001,\t-1",))
    text = text.replace("\n1\n0.0", "\n2\n0.0", 1)

    with pytest.raises(MmanaFormatError, match="fila de conductor"):
        parse_mmana(text)


def test_rejects_truncated_wire_row():
    text = _document_text(wires=("0.0,\t0.0,\t0.0,\t1.0,\t0.0,\t0.0",))

    with pytest.raises(MmanaFormatError, match="fila de conductor"):
        parse_mmana(text)


def test_rejects_invalid_number():
    text = _document_text(wires=("0.0,\t0.0,\tNaNaNa,\t1.0,\t0.0,\t0.0,\t0.001,\t-1",))

    with pytest.raises(MmanaFormatError, match="valor numérico inválido"):
        parse_mmana(text)


def test_rejects_missing_section():
    # Archivo truncado justo después de declarar el conductor: falta
    # por completo la sección de fuentes.
    lines = [
        "Antena truncada",
        "*",
        "14.15",
        "***Wires***",
        "1",
        "0.0,\t0.0,\t0.0,\t1.0,\t0.0,\t0.0,\t0.001,\t-1",
    ]
    text = "\n".join(lines) + "\n"

    with pytest.raises(MmanaFormatError, match="fuentes"):
        parse_mmana(text)


def test_load_error_includes_path_and_line_number(tmp_path):
    destination = tmp_path / "broken.maa"
    destination.write_text(
        _document_text().replace("\n*\n", "\n?\n", 1),
        encoding="utf-8",
    )

    with pytest.raises(MmanaFormatError) as error_info:
        load_mmana(destination)

    error = error_info.value
    assert error.path == destination
    assert error.line_number == 2
    assert str(destination) in str(error)
    assert "línea 2" in str(error)
