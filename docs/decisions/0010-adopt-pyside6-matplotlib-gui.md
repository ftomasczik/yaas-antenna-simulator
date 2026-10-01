# ADR 0010: Adoptar PySide6 y Matplotlib para la primera GUI

- Estado: Aceptada
- Fecha: 2026-09-30

## Contexto

YAAS ya separa dominio, proyectos, motores, exportadores, CLI y capa de
aplicación ([ADR 0003](0003-separate-engine.md)). La
[fase 8](../phases/phase-8-radiation-patterns.md) entregó patrones de
radiación de punta a punta (cálculo, esquema v4, exportación CSV y NEC,
CLI), pero sin ninguna visualización. Los casos de uso de patrones ya
viven en `yaas.application.radiation_pattern`, de modo que una GUI
puede reutilizarlos sin importar la CLI.

La
[investigación previa](../research/gui-radiation-visualization.md)
comparó PySide6 + Matplotlib, PySide6 + pyqtgraph y Qt nativo, con
prototipos fuera del repositorio. Sus conclusiones que condicionan esta
decisión:

- Los patrones de YAAS son pequeños (cientos o pocos miles de puntos):
  Matplotlib dibujó un corte en ~55 ms y pyqtgraph en ~3 ms, ambos
  suficientes. Importan más la convención polar, la exportación y la
  mantenibilidad que el rendimiento bruto.
- Matplotlib tiene proyección polar nativa con la orientación de YAAS
  configurable y verificada, huecos para nulos y exportación PNG, SVG y
  PDF. pyqtgraph 0.14 no tiene gráfico polar y su exportación SVG falló
  con PySide6 6.11.2. Qt Charts (`QPolarChart`) está obsoleto y usa la
  orientación de una brújula.
- En los experimentos realizados con PyNEC 2.3.4 sobre Windows y
  CPython 3.13, las llamadas nativas ensayadas retuvieron el GIL
  durante la mayor parte de su ejecución; un hilo de trabajo no evitó
  una pausa de ~490 ms de la interfaz en un patrón grande sobre tierra
  real.
- Un ejecutable mínimo con PySide6 y Matplotlib ocupó ~73 MB, frente a
  los ~20 MB del ejecutable actual de la CLI.

La GUI no debe acoplarse a PyNEC ni duplicar la lógica que ya resuelven
el dominio, la aplicación y los exportadores.

## Decisión

### Tecnología

Para la primera GUI de YAAS se adopta:

- **PySide6** como toolkit de interfaz.
- **Matplotlib** como visualizador 2D, integrado mediante su backend Qt
  (`backend_qtagg`).
- Un **`RadiationPatternPlotAdapter`** propio como única frontera con
  Matplotlib, para poder reemplazarlo sin tocar el resto de la GUI.
- **Gráfico polar** para el corte de azimut y **gráfico cartesiano
  `theta` frente a dBi** para el primer corte vertical.
- **Patrón 3D postergado.**

No se adopta pyqtgraph en esta fase; puede reevaluarse para gráficos
cartesianos de alta interacción. No se adopta Qt Charts: está obsoleto,
su edición abierta es solo GPLv3 y su polar exigiría remapear la
orientación. Ninguna API gráfica entra al dominio ni a
`yaas.application`.

### Dependencias opcionales

La GUI se incorporará mediante un extra opcional, tentativamente:

```powershell
python -m pip install -e ".[gui]"
```

- La instalación base y la CLI deben seguir funcionando sin Qt ni
  Matplotlib.
- Esta decisión no fija si el extra usará el metapaquete `PySide6` o
  solo `PySide6-Essentials`: el prototipo usó el metapaquete completo y
  hace falta una prueba específica.
- `pytest-qt`, cuando se adopte, será solo una dependencia de
  desarrollo y pruebas.
- Esta tarea no modifica `pyproject.toml`.

### Ejecutables y entry points

- CLI: `yaas`, sin cambios.
- GUI: un entry point futuro separado, nombre tentativo `yaas-gui`.
- Ejecutable congelado de la GUI futuro, separado del de la CLI.

Razones: la CLI no debe cargar Qt; su binario debe seguir siendo
pequeño (no crecer de ~20 MB a ~73 MB); un fallo de plugins Qt no debe
afectar a la CLI; y ambos binarios pueden necesitar políticas de
distribución distintas. Los nombres marcan la dirección
arquitectónica; pueden confirmarse en la tarea de implementación si
aparece una restricción técnica real.

### Arquitectura

```text
widgets / vistas
  -> controlador o view-model
    -> yaas.application
      -> dominio, proyectos, motores (protocolo) y exportadores
```

- `RadiationPatternPlotAdapter` depende de Matplotlib; los casos de uso
  de `yaas.application` no.
- La GUI reutiliza el workflow ya extraído:
  `prepare_radiation_pattern_request`, `calculate_radiation_pattern`,
  `summarize_radiation_pattern`, `export_project_radiation_pattern_nec`
  y `yaas.exporters.export_radiation_pattern_csv`.
- La GUI no puede:
  - importar PyNEC ni un motor concreto fuera del punto de
    construcción del motor;
  - importar `nec_context` ni manipular arrays numpy nativos;
  - leer archivos `.yaas` manualmente (usa `yaas.projects`);
  - construir tarjetas NEC;
  - duplicar el resumen, el máximo o las exportaciones;
  - ejecutar cálculos pesados en el hilo principal.

### Concurrencia

Primera implementación:

- `QThread` con un worker `QObject`, detrás de una abstracción
  `SimulationRunner`;
- un trabajo incompatible por vez;
- resultados inmutables enviados a la interfaz por señal, a un
  `QObject` que vive en el hilo principal;
- cancelación cooperativa entre llamadas nativas, y descarte del
  resultado de un trabajo cancelado;
- nunca `QThread.terminate()`.

Limitaciones aceptadas:

- `QThread` no garantiza fluidez mientras una extensión nativa
  conserve el GIL.
- Con la evidencia actual, una llamada nativa en curso no puede
  interrumpirse de forma segura.
- Un proceso separado queda como alternativa si las pruebas reales
  muestran pausas inaceptables. `SimulationRunner` debe permitir
  sustituir la estrategia sin cambiar widgets ni controlador. La
  cancelación mediante proceso separado **no está resuelta**: requiere
  su propio diseño (ciclo de vida, serialización, errores, limpieza y
  comportamiento en PyInstaller y Windows).

### Contrato visual

**Azimut (polar):**

- `phi=0°` en +X (derecha) y `phi=90°` en +Y (arriba);
- sentido antihorario;
- los ángulos son los valores reales de `phi` del resultado.

**Vertical inicial (cartesiano):**

- eje X: `theta` en grados; eje Y: ganancia en dBi;
- `theta` de 0 a 180 en espacio libre y de 0 a 90 con tierra;
- `theta` nunca se rotula como elevación;
- no se reflejan datos.

**Nulos y piso:**

- `None` se convierte en NaN solo dentro del adaptador y produce una
  discontinuidad;
- los valores finitos bajo el piso de la escala se recortan solo
  visualmente;
- los datos, el CSV, los tooltips y los resúmenes conservan siempre el
  valor real;
- el adaptador informa la cantidad de nulos y de valores recortados.

### Pruebas

La adopción futura debe incluir:

- pruebas unitarias del controlador o view-model, sin GUI;
- `pytest-qt` como dependencia de desarrollo;
- `QT_QPA_PLATFORM=offscreen` en CI;
- pruebas estructurales del adaptador: orientación mediante
  transformaciones de coordenadas, nulos mediante segmentos o
  discontinuidades, y recorte mediante los datos y los metadatos;
- un smoke test de inicio y cierre del ejecutable.

La comparación píxel a píxel no es la prueba principal.

### CI y empaquetado

Requisitos para la tarea de adopción:

- un job de GUI separado, en Windows y Ubuntu 24.04, en modo
  `offscreen`;
- prueba real de instalación de los wheels;
- prueba de PyInstaller, incluidos los plugins Qt y el backend de
  Matplotlib;
- verificación de que la CLI se instala y funciona sin dependencias de
  GUI;
- medición del tamaño y del tiempo de arranque;
- ningún artefacto publicado inicialmente.

Ubuntu 22.04 se mantiene como compatibilidad del núcleo (suite de la
CLI). La GUI empieza en Windows y Ubuntu 24.04, que es donde ya corre
el build efímero de Linux; 22.04 puede agregarse después de comprobar
en la práctica los wheels y las bibliotecas de sistema de Qt.

### Licencias

- PySide6 y Qt deben revisarse por binding y por los módulos y plugins
  efectivamente incorporados al ejecutable.
- Matplotlib requiere conservar sus avisos, y lo mismo sus fuentes y
  dependencias incorporadas.
- Elegir la opción LGPL de Qt no elimina las obligaciones de
  distribución.
- Antes de distribuir el binario de la GUI deben actualizarse
  `THIRD_PARTY_NOTICES.md`, la política de cumplimiento, los textos de
  licencia y las instrucciones y fuentes aplicables. No se modifican
  ahora porque las dependencias todavía no se adoptaron.

Nada de esto constituye asesoramiento legal definitivo (ver
[ADR 0004](0004-project-license.md) y
[`docs/packaging/windows-release-compliance.md`](../packaging/windows-release-compliance.md)).

## Alternativas consideradas

1. **PySide6 + pyqtgraph.** Rechazada para la primera GUI: no tiene
   gráfico polar (habría que dibujarlo a mano) y su exportación SVG
   falló en el prototipo. Su mayor rendimiento no es necesario para los
   tamaños de YAAS.
2. **Solo Qt (Qt Charts, Qt Graphs o `QPainter`).** Rechazada: Qt
   Charts está obsoleto, Qt Graphs no ofrece polar 2D, ambos son solo
   GPLv3 en su edición abierta, y dibujar a mano escalas, ticks y
   exportación vectorial cuesta mucho para el valor inicial.
3. **GUI web.** Rechazada por ahora: agrega otro stack (servidor local,
   navegador y JavaScript) y otro modelo de empaquetado, sin resolver
   mejor la visualización 2D.
4. **Tkinter.** Rechazada: viene con Python y Matplotlib tiene backend
   para él, pero el proyecto ya había fijado PySide6 como dirección de
   la GUI (`AGENTS.md`), y la investigación evaluó y verificó la
   integración con Qt, no con Tk. No se evaluó en profundidad.
5. **Comenzar directamente con 3D.** Rechazada: agrega una dependencia
   nativa grande y no resuelve la primera necesidad, los cortes 2D.
6. **Seguir solo con la CLI.** Rechazada como estrategia de largo
   plazo: la CLI se mantiene, pero no permite ver patrones; la GUI se
   suma sin reemplazarla.

## Consecuencias

### Positivas

- Gráfico polar nativo, con la convención de YAAS verificada.
- Exportación de imágenes (PNG, SVG y PDF).
- Separación de capas: la GUI solo orquesta casos de uso existentes.
- La CLI y su ejecutable siguen siendo livianos.
- Pruebas sin pantalla (`offscreen`) en CI.
- El adaptador permite reemplazar el backend gráfico en el futuro.

### Negativas

- Dependencias grandes (Qt y Matplotlib con sus dependencias).
- Un ejecutable de GUI mucho mayor que el de la CLI.
- Plugins Qt y bibliotecas de sistema que verificar en cada
  plataforma.
- Complejidad de concurrencia, agravada porque PyNEC retuvo el GIL en
  las llamadas ensayadas.
- Obligaciones de distribución adicionales.
- Matplotlib es más lento que pyqtgraph (sin impacto práctico con los
  tamaños actuales).
- Dos ejecutables y dos builds que mantener.

## Alcance excluido

Esta decisión no incluye:

- la implementación de ventanas;
- un editor geométrico;
- el patrón 3D;
- patrones multifrecuencia;
- polarización;
- temas definitivos;
- instaladores;
- la publicación de binarios;
- un proceso separado para los cálculos;
- accesibilidad completa.

## Condiciones antes de implementar

La primera tarea que agregue dependencias de GUI deberá:

1. confirmar si `PySide6-Essentials` alcanza o hace falta el
   metapaquete `PySide6`;
2. crear el extra `gui`;
3. mantener limpia la instalación base (sin Qt ni Matplotlib);
4. actualizar `THIRD_PARTY_NOTICES.md`;
5. actualizar la documentación de cumplimiento;
6. agregar el job de CI en modo `offscreen`;
7. verificar PyInstaller en Windows y Linux;
8. medir el tamaño del ejecutable;
9. crear un esqueleto que abra y cierre la ventana sin usar el motor.

## Evidencia

- [`docs/research/gui-radiation-visualization.md`](../research/gui-radiation-visualization.md):
  comparación de alternativas, prototipos, medición del GIL, tamaños y
  licencias.
- [`docs/phases/phase-8-radiation-patterns.md`](../phases/phase-8-radiation-patterns.md):
  patrones de radiación, convención angular validada y regla del
  máximo.
- [ADR 0003](0003-separate-engine.md): separación entre dominio, motor
  e interfaces.
- [ADR 0004](0004-project-license.md): licencia GPL-3.0-only de YAAS.
- [ADR 0009](0009-add-radiation-pattern-schema-v4.md): persistencia del
  patrón en el esquema `.yaas` v4.
