# Política de cumplimiento para una release binaria de la GUI

Este documento define qué deberá contener una futura release pública
que incluya el ejecutable experimental de la GUI (`dist\yaas-gui.exe`
en Windows, `dist/yaas-gui` en Linux). Complementa
[`windows-release-compliance.md`](windows-release-compliance.md), que
cubre el ejecutable de la CLI. No constituye asesoramiento legal
profesional (ver
[`docs/decisions/0004-project-license.md`](../decisions/0004-project-license.md)).

## Estado actual

- La GUI es un esqueleto experimental: una ventana mínima con una
  pestaña de patrón de radiación vacía (adaptador Matplotlib y widget
  ya disponibles, sin proyectos ni simulaciones); ver
  [ADR 0010](../decisions/0010-adopt-pyside6-matplotlib-gui.md).
- Los ejecutables de la GUI solo se construyen de forma efímera en CI
  y localmente (`scripts/build_gui_windows.ps1`,
  `scripts/build_gui_linux.sh`). **No se publica ningún binario de la
  GUI**, y este repositorio todavía no cumple con lo que exigiría
  publicarlo: este documento describe ese paquete futuro, no uno
  existente.

## Qué incorpora el ejecutable de la GUI

Ver `THIRD_PARTY_NOTICES.md`, sección 4, para el inventario verificado.
En resumen:

- PySide6-Essentials y shiboken6 6.11.2 (licencia declarada
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`);
- bibliotecas y plugins de Qt 6.11.2 (`Qt6Core`, `Qt6Gui`,
  `Qt6Widgets`, `Qt6Svg`, `Qt6Network`, plugins de plataforma, imagen y
  estilo, traducciones);
- Matplotlib 3.11.2 (licencia propia de Matplotlib, basada en la PSF)
  con los backends QtAgg, Agg, SVG y PDF, y sus datos `mpl-data`
  (fuentes DejaVu, STIX, BaKoMa/cm, AFM y las 15 fuentes núcleo de
  PDF, imágenes, estilos y `matplotlibrc`);
- las dependencias transitivas de Matplotlib: contourpy, cycler,
  fonttools, kiwisolver, pillow (con libjpeg, zlib, FreeType, libwebp,
  HarfBuzz y otras bibliotecas compiladas en sus extensiones),
  pyparsing, python-dateutil, six, packaging y numpy (con OpenBLAS,
  LAPACK y el runtime de GCC en `libscipy_openblas64_*.dll`);
- `opengl32sw.dll` en Windows, con procedencia y licencia por relevar;
- el bootloader de PyInstaller (GPL-2.0-or-later WITH
  Bootloader-exception) y el runtime de Python con sus bibliotecas
  (por ejemplo, la `libcrypto` incluida en Python), igual que el
  ejecutable de la CLI.

El ejecutable de la GUI **no** incorpora PyNEC, NEC2++, Eigen, el
módulo `PySide6.QtNetwork` ni pyqtgraph (se excluyen explícitamente en
el build, que además falla si el análisis de PyInstaller los recoge o
menciona bibliotecas de una instalación ajena como XAMPP).

## Exportación de imágenes

El adaptador de la GUI exporta gráficos en PNG, SVG y PDF
(`RadiationPatternPlotAdapter.save_image`). Los archivos SVG y PDF
pueden incrustar subconjuntos de las fuentes incluidas en Matplotlib
(DejaVu por defecto); las licencias de DejaVu y STIX permiten ese uso,
pero sus avisos deben acompañar la distribución del ejecutable que las
contiene. Este documento no evalúa las condiciones aplicables a las
imágenes que genere cada usuario.

## Assets que deberá contener una futura release binaria de la GUI

1. El ejecutable de la GUI de cada plataforma publicada.
2. El código fuente exacto de YAAS correspondiente al tag de esa
   release.
3. `LICENSE` (GPL-3.0-only, la licencia propia de YAAS).
4. `THIRD_PARTY_NOTICES.md`.
5. Los textos completos de las licencias aplicables, **incluidos los
   de la LGPL-3.0 y la GPL (2.0 y 3.0) de Qt y PySide**, porque el
   wheel de PySide6-Essentials no los incluye (solo trae un aviso para
   licenciatarios comerciales).
6. Los avisos de copyright de Qt, PySide6 y shiboken6, y los de los
   componentes de terceros que Qt incorpora (a relevar con la
   documentación oficial de Qt).
7. Los textos de licencia de Matplotlib (su `LICENSE` completo, que
   incluye los avisos de DejaVu, STIX y BaKoMa, y `LICENSE_DEJAVU` y
   `LICENSE_STIX`), de Pillow (con los avisos de sus bibliotecas
   nativas), de numpy (incluidos OpenBLAS, LAPACK y el runtime de GCC)
   y de contourpy, cycler, fonttools (`LICENSE` y `LICENSE.external`),
   kiwisolver, pyparsing, python-dateutil, six y packaging.
   PyInstaller solo copia al ejecutable el `.dist-info` de numpy: los
   demás textos deben aportarse por separado.
8. El código fuente correspondiente de Qt y PySide6 utilizado, o una
   oferta o enlace válido según lo que exija la opción de licencia
   elegida, y la forma de obtenerlo para la versión exacta incorporada.
9. Bajo la opción LGPL de Qt: la posibilidad de que el usuario
   reemplace las bibliotecas Qt por versiones modificadas. Con un
   ejecutable `onefile` esto debe analizarse expresamente (por
   ejemplo, ofreciendo también una variante `onedir` o las
   instrucciones para reconstruir el ejecutable); elegir la LGPL no
   elimina las obligaciones de distribución.
10. Las instrucciones y scripts necesarios para reproducir el build
    (`scripts/build_gui_windows.ps1`, `scripts/build_gui_linux.sh` y la
    instalación con `python -m pip install -e ".[dev,gui]"`).
11. Checksums (SHA-256) de todos los assets.

## Pendiente antes de cualquier publicación

- Relevar el código de terceros incorporado por Qt y la procedencia y
  licencia de `opengl32sw.dll`.
- Relevar el contenido real del ejecutable de Linux (hoy solo se
  verificó el de Windows).
- Decidir la opción de licencia de Qt (GPL-3.0 o LGPL-3.0) y sus
  consecuencias para el formato del ejecutable.
- Documentar los componentes del runtime de Python incorporados (por
  ejemplo, `libcrypto-3.dll`, `libssl-3.dll` y `libffi-8.dll`; un
  pendiente que también aplica al ejecutable de la CLI).
- Reunir los textos de licencia de Matplotlib y sus dependencias
  (punto 7 de la lista anterior) y verificar el inventario completo de
  bibliotecas nativas incluidas en Pillow para la versión exacta
  incorporada.
- Relevar en Linux el conjunto de bibliotecas que Matplotlib, Pillow y
  numpy incorporan (allí sus wheels traen bibliotecas compartidas
  propias).
- Revisar todo lo anterior junto con
  `docs/decisions/0004-project-license.md`.
