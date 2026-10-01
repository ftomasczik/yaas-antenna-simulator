"""Adaptador Matplotlib de patrones y su widget (offscreen, sin capturas).

La orientación, los nulos y el recorte se verifican con los datos de las
líneas y las transformaciones de Matplotlib, nunca comparando píxeles.
"""

import copy
import math
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("matplotlib")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from yaas.domain import RadiationPatternResult  # noqa: E402
from yaas.gui.plots.radiation_pattern import (  # noqa: E402
    RadiationPatternPlotAdapter,
    RadiationPatternPlotSummary,
    _prepare_series,
)
from yaas.gui.widgets.radiation_pattern_plot import (  # noqa: E402
    EMPTY_MESSAGE,
    RadiationPatternPlotWidget,
)

REPO = Path(__file__).resolve().parents[2]
FLOOR = -40.0


@pytest.fixture(scope="module", autouse=True)
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def adapter():
    return RadiationPatternPlotAdapter()


def azimuth_result(gains=(None, 2.0, -60.0, 1.0, None)):
    """Corte de azimut con phi = 0, 90, 180, 270, 360."""
    return RadiationPatternResult(
        frequency_mhz=14.15,
        theta_angles_deg=(90.0,),
        phi_angles_deg=(0.0, 90.0, 180.0, 270.0, 360.0),
        gain_db=(tuple(gains),),
    )


def vertical_result(theta, gains):
    return RadiationPatternResult(
        frequency_mhz=14.15,
        theta_angles_deg=tuple(theta),
        phi_angles_deg=(0.0,),
        gain_db=tuple((gain,) for gain in gains),
    )


def only_line(axes):
    (line,) = axes.lines
    return line


# ---------------------------------------------------------------------------
# A. Preparación de datos
# ---------------------------------------------------------------------------


def test_prepare_series_contract():
    gains = (None, -50.0, FLOOR, -10.0, 3.5)
    snapshot = tuple(gains)

    values, nulls, clipped = _prepare_series(gains, FLOOR)

    assert math.isnan(values[0])
    assert values[1:] == (FLOOR, FLOOR, -10.0, 3.5)
    assert nulls == 1
    # Un valor igual al piso no cuenta como recortado.
    assert clipped == 1
    assert gains == snapshot
    assert -999.99 not in values


def test_prepare_series_returns_new_data():
    gains = [1.0, None]

    values, _, _ = _prepare_series(gains, FLOOR)

    assert values is not gains
    assert gains == [1.0, None]


# ---------------------------------------------------------------------------
# B. Corte de azimut (polar)
# ---------------------------------------------------------------------------


def display_point(axes, phi_deg, radius):
    return axes.transData.transform((math.radians(phi_deg), radius))


def test_azimuth_orientation_follows_the_yaas_convention(adapter):
    adapter.plot_azimuth(azimuth_result(), theta_index=0, floor_db=FLOOR)
    axes = adapter.axes
    adapter.canvas.draw()
    top = axes.get_ylim()[1]

    center = display_point(axes, 0.0, FLOOR)
    points = {phi: display_point(axes, phi, top) for phi in (0, 90, 180, 270, 360)}

    # Coordenadas de display de Matplotlib: y crece hacia arriba.
    assert points[0][0] > center[0] + 10 and abs(points[0][1] - center[1]) < 1
    assert points[90][1] > center[1] + 10 and abs(points[90][0] - center[0]) < 1
    assert points[180][0] < center[0] - 10 and abs(points[180][1] - center[1]) < 1
    assert points[270][1] < center[1] - 10 and abs(points[270][0] - center[0]) < 1
    # 360 coincide geométricamente con 0.
    assert points[360] == pytest.approx(points[0], abs=1e-6)
    # Antihorario: el ángulo en pantalla crece con phi.
    screen_angles = [
        math.degrees(math.atan2(points[phi][1] - center[1], points[phi][0] - center[0])) % 360
        for phi in (0, 90, 180, 270)
    ]
    assert screen_angles == pytest.approx([0.0, 90.0, 180.0, 270.0], abs=0.5)
    assert axes.get_theta_direction() == 1


def test_azimuth_uses_the_original_angles_and_marks_nulls(adapter):
    result = azimuth_result()

    summary = adapter.plot_azimuth(result, theta_index=0, floor_db=FLOOR)
    line = only_line(adapter.axes)

    assert list(line.get_xdata()) == [math.radians(p) for p in result.phi_angles_deg]
    y = list(line.get_ydata())
    assert math.isnan(y[0]) and math.isnan(y[4])
    assert y[1:4] == [2.0, FLOOR, 1.0]
    assert summary == RadiationPatternPlotSummary(
        total_points=5, null_points=2, clipped_points=1, floor_db=FLOOR
    )


def test_azimuth_clipped_value_is_drawn_on_the_floor_not_lost(adapter):
    adapter.plot_azimuth(azimuth_result(), theta_index=0, floor_db=FLOOR)
    axes = adapter.axes
    adapter.canvas.draw()

    # phi=180 (-60 dBi) se recortó al piso: el punto que realmente se
    # dibujó es finito en pantalla y cae en el centro, a diferencia de
    # un nulo (que sería NaN).
    line = only_line(axes)
    drawn = (line.get_xdata()[2], line.get_ydata()[2])
    clipped_point = axes.transData.transform(drawn)
    assert all(math.isfinite(c) for c in clipped_point)
    assert clipped_point == pytest.approx(display_point(axes, 0.0, FLOOR), abs=1e-6)


def test_azimuth_labels_and_limits(adapter):
    adapter.plot_azimuth(azimuth_result(), theta_index=0, floor_db=FLOOR)
    axes = adapter.axes

    assert axes.name == "polar"
    assert axes.get_title() == "Azimuth cut (theta = 90 deg)"
    assert axes.get_ylabel() == "Gain (dBi)"
    assert "elevation" not in axes.get_title().lower()
    assert axes.get_ylim() == (FLOOR, 2.0)


# ---------------------------------------------------------------------------
# C. Corte vertical (cartesiano)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "theta,expected_xlim",
    [
        (tuple(float(t) for t in range(0, 181, 30)), (0.0, 180.0)),
        (tuple(float(t) for t in range(0, 91, 15)), (0.0, 90.0)),
        ((10.0, 30.0, 50.0), (10.0, 50.0)),
    ],
    ids=["free_space_0_180", "ground_0_90", "subrange_10_50"],
)
def test_vertical_uses_only_the_result_theta(adapter, theta, expected_xlim):
    gains = [1.0] * len(theta)

    adapter.plot_vertical(vertical_result(theta, gains), phi_index=0, floor_db=FLOOR)
    axes = adapter.axes
    line = only_line(axes)

    assert axes.name == "rectilinear"
    assert tuple(line.get_xdata()) == theta  # sin reflejar ni agregar datos
    assert axes.get_xlim() == expected_xlim


def test_vertical_nulls_clipping_and_labels(adapter):
    result = vertical_result((0.0, 45.0, 90.0, 135.0), (3.0, None, -70.0, -5.0))

    summary = adapter.plot_vertical(result, phi_index=0, floor_db=FLOOR)
    axes = adapter.axes
    y = list(only_line(axes).get_ydata())

    assert y[0] == 3.0 and math.isnan(y[1]) and y[2] == FLOOR and y[3] == -5.0
    assert (summary.null_points, summary.clipped_points) == (1, 1)
    assert axes.get_xlabel() == "theta (deg)"
    assert axes.get_ylabel() == "Gain (dBi)"
    assert axes.get_title() == "Vertical cut (phi = 0 deg)"
    assert axes.get_ylim() == (FLOOR, 3.0)


def test_vertical_single_theta_has_a_non_degenerate_range(adapter):
    adapter.plot_vertical(vertical_result((90.0,), (1.0,)), phi_index=0, floor_db=FLOOR)

    low, high = adapter.axes.get_xlim()
    assert low < 90.0 < high


# ---------------------------------------------------------------------------
# D. Actualización y casos límite
# ---------------------------------------------------------------------------


def test_updates_reuse_the_canvas_without_accumulating(adapter):
    canvas = adapter.canvas
    first = vertical_result((0.0, 90.0), (1.0, 2.0))
    second = azimuth_result((1.0, 1.5, 0.5, 1.0, 1.0))

    adapter.plot_vertical(first, phi_index=0, floor_db=FLOOR)
    adapter.plot_azimuth(second, theta_index=0, floor_db=FLOOR)
    adapter.plot_azimuth(second, theta_index=0, floor_db=FLOOR)
    adapter.plot_vertical(first, phi_index=0, floor_db=FLOOR)

    assert adapter.canvas is canvas
    assert adapter.figure.axes == [adapter.axes]
    assert adapter.axes.name == "rectilinear"
    assert len(adapter.axes.lines) == 1
    assert len(adapter.axes.texts) == 0
    # La línea corresponde al último resultado, no a uno anterior.
    assert list(only_line(adapter.axes).get_ydata()) == [1.0, 2.0]


@pytest.mark.parametrize("cut", ["azimuth", "vertical"])
def test_all_null_cut_is_drawn_without_inventing_a_maximum(adapter, cut):
    if cut == "azimuth":
        summary = adapter.plot_azimuth(azimuth_result((None,) * 5), theta_index=0, floor_db=FLOOR)
    else:
        summary = adapter.plot_vertical(
            vertical_result((0.0, 90.0), (None, None)), phi_index=0, floor_db=FLOOR
        )
    axes = adapter.axes

    assert all(math.isnan(v) for v in only_line(axes).get_ydata())
    assert summary.null_points == summary.total_points
    assert summary.clipped_points == 0
    assert axes.get_ylim() == (FLOOR, FLOOR + 10.0)  # rango no degenerado
    assert axes.get_title()


def test_all_values_on_the_floor_still_have_a_range(adapter):
    adapter.plot_azimuth(azimuth_result((-80.0,) * 5), theta_index=0, floor_db=FLOOR)

    assert adapter.axes.get_ylim() == (FLOOR, FLOOR + 10.0)


def test_clear_removes_the_plot(adapter):
    adapter.plot_azimuth(azimuth_result(), theta_index=0, floor_db=FLOOR)

    adapter.clear()

    assert adapter.axes is None
    assert adapter.figure.axes == []


@pytest.mark.parametrize(
    "call",
    [
        lambda a, r: a.plot_azimuth(r, theta_index=1, floor_db=FLOOR),
        lambda a, r: a.plot_azimuth(r, theta_index=-1, floor_db=FLOOR),
        lambda a, r: a.plot_azimuth(r, theta_index=True, floor_db=FLOOR),
        lambda a, r: a.plot_vertical(r, phi_index=5, floor_db=FLOOR),
        lambda a, r: a.plot_azimuth(r, theta_index=0, floor_db=math.nan),
        lambda a, r: a.plot_vertical(r, phi_index=0, floor_db=True),
    ],
    ids=[
        "theta_out_of_range", "theta_negative", "theta_bool",
        "phi_out_of_range", "floor_nan", "floor_bool",
    ],
)
def test_invalid_indices_and_floors_are_rejected(adapter, call):
    with pytest.raises(ValueError):
        call(adapter, azimuth_result())


def test_non_result_is_rejected(adapter):
    with pytest.raises(TypeError, match="RadiationPatternResult"):
        adapter.plot_azimuth(None, theta_index=0, floor_db=FLOOR)


def test_plotting_does_not_modify_the_result(adapter):
    result = azimuth_result()
    snapshot = copy.deepcopy(result)

    adapter.plot_azimuth(result, theta_index=0, floor_db=FLOOR)
    adapter.plot_vertical(result, phi_index=2, floor_db=FLOOR)

    assert result == snapshot


@pytest.mark.parametrize(
    "fields",
    [
        {"total_points": -1, "null_points": 0, "clipped_points": 0, "floor_db": 0.0},
        {"total_points": True, "null_points": 0, "clipped_points": 0, "floor_db": 0.0},
        {"total_points": 2, "null_points": 3, "clipped_points": 0, "floor_db": 0.0},
        {"total_points": 3, "null_points": 2, "clipped_points": 2, "floor_db": 0.0},
        {"total_points": 1, "null_points": 0, "clipped_points": 0, "floor_db": math.inf},
        {"total_points": 1, "null_points": 0, "clipped_points": 0, "floor_db": False},
    ],
    ids=["negative", "bool_count", "nulls_over_total", "clipped_over_finite", "floor_inf", "floor_bool"],
)
def test_plot_summary_rejects_invalid_values(fields):
    with pytest.raises(ValueError):
        RadiationPatternPlotSummary(**fields)


# ---------------------------------------------------------------------------
# E. Widget
# ---------------------------------------------------------------------------


def test_widget_starts_empty_and_shows_cuts():
    widget = RadiationPatternPlotWidget()

    assert widget.status_text == EMPTY_MESSAGE
    assert widget.adapter.axes is None
    assert widget.adapter.canvas.parent() is widget

    summary = widget.show_azimuth(azimuth_result(), theta_index=0, floor_db=FLOOR)
    assert widget.adapter.axes.name == "polar"
    assert widget.status_text == "5 points, 2 null, 1 drawn at the -40 dBi floor."
    assert summary.total_points == 5

    widget.show_vertical(vertical_result((0.0, 90.0), (1.0, None)), phi_index=0, floor_db=FLOOR)
    assert widget.adapter.axes.name == "rectilinear"

    widget.clear()
    assert widget.adapter.axes is None
    assert widget.status_text == EMPTY_MESSAGE
    widget.close()


def test_widget_never_loads_the_engine():
    # En un proceso nuevo, con PyNEC bloqueado: construir el widget y
    # dibujar no intenta cargar el motor.
    code = textwrap.dedent("""
        import importlib.abc, sys
        class NoEngine(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] == "PyNEC":
                    raise ImportError("PyNEC blocked for test")
        sys.meta_path.insert(0, NoEngine())
        from PySide6.QtWidgets import QApplication
        app = QApplication([])
        from yaas.domain import RadiationPatternResult
        from yaas.gui.window import MainWindow
        window = MainWindow()
        result = RadiationPatternResult(
            frequency_mhz=14.15, theta_angles_deg=(90.0,),
            phi_angles_deg=(0.0, 90.0), gain_db=((1.0, None),),
        )
        window.radiation_pattern_plot.show_azimuth(result, theta_index=0, floor_db=-40.0)
        window.radiation_pattern_plot.adapter.canvas.draw()
        loaded = [m for m in ("PyNEC", "yaas.engines.pynec") if m in sys.modules]
        assert not loaded, loaded
    """)
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=REPO,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


# ---------------------------------------------------------------------------
# F. Exportación de imágenes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extension,signature",
    [(".png", b"\x89PNG\r\n\x1a\n"), (".svg", b"<svg"), (".pdf", b"%PDF")],
)
@pytest.mark.parametrize("as_string", [False, True], ids=["path", "str"])
def test_save_image_formats(adapter, tmp_path, extension, signature, as_string):
    result = azimuth_result()
    snapshot = copy.deepcopy(result)
    adapter.plot_azimuth(result, theta_index=0, floor_db=FLOOR)
    destination = tmp_path / f"pattern{extension}"

    returned = adapter.save_image(str(destination) if as_string else destination)

    assert returned == destination
    content = destination.read_bytes()
    assert len(content) > 0
    if extension == ".svg":
        assert signature in content[:2000]
    else:
        assert content.startswith(signature)
    assert result == snapshot


def test_save_image_uppercase_extension(adapter, tmp_path):
    adapter.plot_azimuth(azimuth_result(), theta_index=0, floor_db=FLOOR)

    assert adapter.save_image(tmp_path / "PATTERN.PNG").stat().st_size > 0


@pytest.mark.parametrize("name", ["pattern", "pattern.bmp", "pattern.jpg"])
def test_save_image_rejects_missing_or_unsupported_extensions(adapter, tmp_path, name):
    adapter.plot_azimuth(azimuth_result(), theta_index=0, floor_db=FLOOR)

    with pytest.raises(ValueError, match=r"\.png, \.svg o \.pdf"):
        adapter.save_image(tmp_path / name)

    assert not (tmp_path / name).exists()


def test_save_image_does_not_create_directories(adapter, tmp_path):
    adapter.plot_azimuth(azimuth_result(), theta_index=0, floor_db=FLOOR)

    with pytest.raises(FileNotFoundError):
        adapter.save_image(tmp_path / "no-existe" / "pattern.png")

    assert not (tmp_path / "no-existe").exists()
