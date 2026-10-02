"""Controles para elegir el corte del patrón que se dibuja.

Solo presenta una `CutSelection` (modo y ángulo fijo) y avisa los
cambios del usuario como índices: no decide qué modos admite la grilla
ni dibuja. Los ángulos que lista son los del `RadiationPatternResult`,
tal como vienen, nunca reconstruidos desde inicio y paso.
"""

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from yaas.gui import texts
from yaas.gui.controllers.pattern_cut import CutKind, CutSelection

_KIND_LABELS = {
    CutKind.VERTICAL: texts.CUT_KIND_VERTICAL,
    CutKind.AZIMUTH: texts.CUT_KIND_AZIMUTH,
}
_ANGLE_LABELS = {
    CutKind.VERTICAL: texts.CUT_ANGLE_LABEL_VERTICAL,
    CutKind.AZIMUTH: texts.CUT_ANGLE_LABEL_AZIMUTH,
}


class CutSelectorWidget(QWidget):
    """Selector de modo y de ángulo fijo.

    Señales (solo ante una acción del usuario, nunca al actualizar los
    controles desde ``show_selection``):

    - ``kind_selected(CutKind)``;
    - ``index_selected(int)``: índice del ángulo fijo del modo activo.
    """

    kind_selected = Signal(object)
    index_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        kind_label = QLabel(texts.CUT_KIND_LABEL)
        self._kind = QComboBox()
        self._kind.setObjectName("cutKind")
        kind_label.setBuddy(self._kind)

        self._angle_label = QLabel(texts.CUT_ANGLE_LABEL_EMPTY)
        self._angle_label.setObjectName("cutAngleLabel")
        self._angle = QComboBox()
        self._angle.setObjectName("cutAngle")
        self._angle_label.setBuddy(self._angle)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(kind_label)
        layout.addWidget(self._kind)
        layout.addWidget(self._angle_label)
        layout.addWidget(self._angle)
        layout.addStretch(1)

        self._kind.activated.connect(self._on_kind_activated)
        self._angle.activated.connect(self.index_selected.emit)
        self.show_selection(None, enabled=False)

    @property
    def kind_combo(self) -> QComboBox:
        return self._kind

    @property
    def angle_combo(self) -> QComboBox:
        return self._angle

    @property
    def angle_label(self) -> str:
        return self._angle_label.text()

    def show_selection(
        self, selection: CutSelection | None, *, enabled: bool
    ) -> None:
        """Muestra ``selection``; sin ella, los controles quedan vacíos.

        ``enabled`` en False deshabilita ambos selectores (por ejemplo,
        durante un cálculo). Con ``enabled`` en True, cada selector se
        habilita solo si ofrece más de una opción.
        """
        with QSignalBlocker(self._kind), QSignalBlocker(self._angle):
            self._kind.clear()
            self._angle.clear()
            self._kinds: tuple[CutKind, ...] = ()
            if selection is None:
                self._angle_label.setText(texts.CUT_ANGLE_LABEL_EMPTY)
                self._kind.setEnabled(False)
                self._angle.setEnabled(False)
                return

            self._kinds = selection.available_kinds
            for kind in self._kinds:
                self._kind.addItem(_KIND_LABELS[kind])
            self._kind.setCurrentIndex(
                selection.available_kinds.index(selection.kind)
            )
            self._angle_label.setText(_ANGLE_LABELS[selection.kind])
            for angle in selection.angles_deg:
                self._angle.addItem(texts.angle_text(angle))
            self._angle.setCurrentIndex(selection.index)

            self._kind.setEnabled(enabled and selection.can_change_kind)
            self._angle.setEnabled(enabled and selection.can_change_angle)

    def _on_kind_activated(self, combo_index: int) -> None:
        # Por posición en la tupla de modos (no por itemData: un str-Enum
        # podría volver como str simple).
        if 0 <= combo_index < len(self._kinds):
            self.kind_selected.emit(self._kinds[combo_index])
