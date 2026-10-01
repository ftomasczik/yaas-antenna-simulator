# Avisos de terceros

Este documento identifica los componentes de terceros que YAAS utiliza
o incorpora, y la licencia bajo la que se distribuye cada uno, según
evidencia verificable local (metadata instalada, archivos de licencia
empaquetados) y del proyecto upstream correspondiente. No reproduce el
texto completo de cada licencia: identifica dónde encontrarlo. El texto
de la licencia propia de YAAS está únicamente en `LICENSE`
(GPL-3.0-only).

Este documento no constituye asesoramiento legal profesional (ver
`docs/decisions/0004-project-license.md`).

## 1. Dependencias de ejecución declaradas por YAAS

Estas son las dependencias listadas en `[project.dependencies]` de
`pyproject.toml`; se instalan siempre, y su código se ejecuta en
tiempo de ejecución junto con YAAS.

### PyNEC 2.3.4

- Proyecto upstream: [python-necpp](https://github.com/tmolteno/python-necpp)
  (paquete publicado en PyPI como `PyNEC`).
- Metadata instalada (`License-Expression`): `GPL-3.0-only`.
- sdist verificado: `pynec-2.3.4.tar.gz`,
  SHA-256 `d448d038d2bcb4265d511b2440a5d5ce26081269a776d45139fb8bf17a475df4`.
- **Inconsistencia documentada, no oculta**: el sdist incluye un
  archivo `LICENCE.txt` con el texto plantilla de la GPLv2 (con
  marcadores de posición `{year}`/`{fullname}` sin completar), mientras
  que la metadata publicada del propio paquete (wheel/sdist) declara
  `GPL-3.0-only`. `GPL-2.0-or-later` (ver NEC2++ más abajo) permite
  acogerse a `GPL-3.0-only` mediante la opción "o una versión
  posterior", pero esto no confirma que la inconsistencia entre el
  `LICENCE.txt` plantilla y la metadata declarada sea intencional por
  parte del mantenedor de PyNEC.

### NEC2++

- Copyright: Timothy C. A. Molteno.
- Incorporado dentro de las fuentes de PyNEC (no es una dependencia
  Python separada).
- Encabezados reales de los archivos fuente (inspeccionados
  directamente en el sdist verificado arriba, no solo el
  `LICENCE.txt`/`COPYING` genérico): "either version 2 of the License,
  or (at your option) any later version" → **GPL-2.0-or-later**.

### Eigen (vendorizado dentro de PyNEC)

- Biblioteca de álgebra lineal C++ vendorizada dentro de
  `necpp_src/src/eigen/` en el sdist de PyNEC (no vendorizada
  directamente por YAAS).
- Licencia: **MPL-2.0**.

### NEC2 original (LLNL)

- Origen histórico de NEC2 (Fortran), Lawrence Livermore National
  Laboratory.
- Las fuentes conservan un aviso de responsabilidad ("disclaimer")
  típico de una obra del gobierno de EE. UU., sin una licencia de
  copyright explícita equivalente a las anteriores.
- No se inventa ni se declara aquí "dominio público" u otra licencia
  sin evidencia firme: se documenta únicamente lo verificado.

### numpy 2.5.3

- Metadata instalada (`License-Expression`):
  `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0` (múltiples
  licencias permisivas según el componente interno).
- Archivo de licencia empaquetado:
  `numpy-2.5.3.dist-info/LICENSE.txt`.

## 2. Herramientas de build/desarrollo

Estas dependencias están en `[project.optional-dependencies].dev` de
`pyproject.toml`, o son dependencias transitivas de esas herramientas
instaladas en el entorno virtual del proyecto (`.venv`). No se
ejecutan como parte de YAAS en tiempo de ejecución normal (CLI); se
usan para probar, empaquetar o construir el proyecto.

| Paquete | Versión | Licencia declarada | Rol |
|---|---|---|---|
| pytest | 9.1.1 | MIT | Framework de pruebas |
| pyinstaller | 6.22.3 | GPL-2.0-or-later WITH Bootloader-exception (ver más abajo) | Generación de `yaas.exe` |
| pyinstaller-hooks-contrib | 2026.7 | Apache-2.0 / GPL-2.0 (según componente) | Hooks de PyInstaller |
| Babel | 2.18.0 | BSD-3-Clause | Compilación de catálogos `.po`/`.mo` |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | Dependencia transitiva (pytest/PyInstaller) |
| pluggy | 1.6.0 | MIT | Dependencia transitiva de pytest |
| iniconfig | 2.3.0 | MIT | Dependencia transitiva de pytest |
| Pygments | 2.21.0 | BSD-2-Clause | Dependencia transitiva de pytest |
| altgraph | 0.17.5 | MIT | Dependencia transitiva de PyInstaller |
| pefile | 2024.8.26 | MIT | Dependencia transitiva de PyInstaller (análisis de binarios PE en Windows) |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | Dependencia transitiva de PyInstaller (Windows) |
| colorama | 0.4.6 | BSD | Dependencia transitiva (salida de consola en Windows) |
| setuptools | 84.0.0 | MIT | Backend de build (PEP 517) |
| wheel | 0.48.0 | MIT | Empaquetado de wheels |

Fuente de cada licencia: metadata instalada
(`importlib.metadata.distribution(<paquete>).metadata`) y, cuando el
paquete la incluye, su archivo `licenses/LICENSE` empaquetado en el
`.dist-info` correspondiente dentro de `.venv`.

**PyInstaller y la excepción de bootloader**: el archivo
`pyinstaller-6.22.3.dist-info/licenses/COPYING.txt` declara
explícitamente `SPDX-License-Identifier: (GPL-2.0-or-later WITH
Bootloader-exception)` para los archivos del bootloader
(`./bootloader/`), y aclara que esa excepción permite enlazar o
incorporar el bootloader compilado en un ejecutable generado sin que
eso imponga las condiciones de la GPL sobre el programa empaquetado.
Esta es la posición documentada por el propio proyecto PyInstaller, no
una conclusión legal independiente de YAAS.

## 3. Componentes transitivos incorporados al generar el ejecutable PyInstaller

Estos componentes **no se distribuyen** al publicar únicamente el
código fuente de este repositorio. Se incorporan físicamente dentro de
`dist\yaas.exe` cuando se ejecuta `scripts\build_windows.ps1`, y por lo
tanto son relevantes solo para una futura distribución binaria (ver
`docs/packaging/windows-release-compliance.md`):

- **Bootloader de PyInstaller**: GPL-2.0-or-later WITH
  Bootloader-exception (ver arriba). Según la propia excepción del
  proyecto, embeberlo en `yaas.exe` no impone por sí solo condiciones
  de la GPL sobre el código de YAAS.
- **Motor NEC2++ compilado (dentro de la extensión de PyNEC)**:
  GPL-2.0-or-later (headers reales de NEC2++, ver sección 1). A
  diferencia del bootloader, este componente **no tiene una excepción
  de enlace**: distribuir `yaas.exe` con PyNEC embebido implica ofrecer
  el código fuente correspondiente de PyNEC/NEC2++ (ver
  `docs/packaging/windows-release-compliance.md`).
- **Eigen** (vendorizado dentro de las fuentes de PyNEC/NEC2++):
  MPL-2.0, incorporado igualmente en el binario compilado de PyNEC.
- **Extensiones compiladas de numpy**: familia de licencias permisivas
  BSD/MIT/Zlib/CC0 (ver sección 1); solo requieren preservar el aviso
  de copyright correspondiente.
- El disclaimer histórico de NEC2/LLNL (ver sección 1) se conserva sin
  reformular, como parte del linaje del código incorporado.

## 4. Dependencias opcionales de la GUI (extra `gui`)

Estas dependencias solo se instalan con el extra opcional
(`python -m pip install -e ".[gui]"`, ver
`docs/decisions/0010-adopt-pyside6-matplotlib-gui.md`). La instalación
base, la CLI `yaas` y su ejecutable `dist\yaas.exe` no las usan ni las
incorporan (verificado construyendo `yaas.exe` con Qt y Matplotlib
instalados en el entorno: el análisis de PyInstaller no recogió
PySide6, shiboken6, Qt6 ni Matplotlib). Datos verificados el 2026-09-30 sobre las distribuciones
instaladas en un entorno limpio con Python 3.13 en Windows.

### PySide6-Essentials 6.11.2

- Proyecto upstream: Qt for Python (<https://pyside.org>, código en
  <https://code.qt.io/cgit/pyside/pyside-setup.git/>).
- Rol: dependencia **opcional** de ejecución (GUI); incluye las
  bibliotecas de Qt 6.11.2 y sus plugins.
- Metadata instalada (`Metadata-Version: 2.4`): el campo `License`
  declara `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`; no hay campo
  `License-Expression`.
- Único archivo de licencia empaquetado:
  `pyside6_essentials-6.11.2.dist-info/licenses/LicenseRef-Qt-Commercial.txt`,
  un aviso breve para quienes tienen licencia comercial de Qt. **El
  wheel no incluye los textos de la LGPL ni de la GPL**: una
  distribución binaria deberá aportarlos (ver
  `docs/packaging/gui-release-compliance.md`).
- Depende únicamente de `shiboken6==6.11.2`.

### shiboken6 6.11.2

- Mismo proyecto upstream y misma licencia declarada en el campo
  `License` (`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`).
- Único archivo de licencia empaquetado:
  `shiboken6-6.11.2.dist-info/licenses/LicenseRef-Qt-Commercial.txt`.

### Componentes incorporados a `dist\yaas-gui.exe`

Relevados del análisis de PyInstaller al ejecutar
`scripts\build_gui_windows.ps1` (Windows); en Linux el conjunto puede
diferir y todavía no se relevó localmente:

- Módulos de PySide6: `QtCore`, `QtGui` y `QtWidgets` (`QtNetwork` se
  excluye explícitamente).
- Bibliotecas: `Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Widgets.dll`,
  `Qt6Svg.dll`, `Qt6Network.dll` (dependencia binaria de otras
  bibliotecas Qt, sin el módulo Python ni sus plugins TLS),
  `pyside6.abi3.dll`, `shiboken6.abi3.dll` y `opengl32sw.dll`
  (renderizador OpenGL por software que viene en el wheel; su
  procedencia y licencia **no se verificaron** y deben relevarse antes
  de una distribución).
- Plugins de Qt: `platforms` (`qwindows`, `qoffscreen`, `qminimal`,
  `qdirect2d`), `imageformats` (`qgif`, `qicns`, `qico`, `qjpeg`,
  `qsvg`, `qtga`, `qtiff`, `qwbmp`, `qwebp`), `iconengines/qsvgicon`,
  `styles/qmodernwindowsstyle` y `generic/qtuiotouchplugin`.
- 96 catálogos de traducción `.qm` de Qt.
- Ningún módulo de Qt incorporado figura entre los que la
  documentación de Qt declara solo GPLv3; Qt Charts y Qt Graphs no se
  usan ni se incorporan.
- Qt contiene a su vez código de terceros (bibliotecas de imágenes,
  fuentes, compresión, etc.); su inventario debe relevarse con la
  documentación oficial de Qt ("Third-Party Code Used in Qt") antes de
  una distribución. No se relevó todavía.

### Matplotlib 3.11.2 y sus dependencias transitivas

Matplotlib (`matplotlib>=3.11.2,<4`) forma parte del extra `gui` desde
el adaptador de gráficos de patrones de radiación
(`yaas.gui.plots.radiation_pattern`); solo se importa dentro de
`yaas.gui`. Datos verificados el 2026-09-30 sobre las distribuciones
instaladas en un entorno limpio (`.[dev,gui]`, Python 3.13, Windows):

| Paquete | Versión | Licencia declarada (metadata) | Nuevo para la GUI |
|---|---|---|---|
| matplotlib | 3.11.2 | "License agreement for matplotlib versions 1.3.0 and later" (clasificador PSF) | Sí |
| contourpy | 1.4.0 | BSD-3-Clause | Sí |
| cycler | 0.12.1 | BSD (Copyright (c) 2015 matplotlib project) | Sí |
| fonttools | 4.66.1 | MIT (`LICENSE` y `LICENSE.external`) | Sí |
| kiwisolver | 1.5.1 | BSD | Sí |
| pillow | 12.3.0 | MIT-CMU | Sí |
| pyparsing | 3.3.3 | MIT | Sí |
| python-dateutil | 2.9.0.post0 | Dual BSD / Apache-2.0 | Sí |
| six | 1.17.0 | MIT | Sí (dependencia de python-dateutil) |
| numpy | 2.5.3 | Ver sección 1 | No: ya es dependencia base |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | No: ya estaba entre las herramientas de desarrollo (sección 2); ahora también la requiere Matplotlib en ejecución |

Notas verificadas:

- **Matplotlib**: el archivo `LICENSE` de su `.dist-info` (63.379
  caracteres) reúne la licencia propia de Matplotlib y los avisos de
  los componentes que incluye, entre ellos las fuentes DejaVu, STIX y
  BaKoMa. El paquete trae además
  `mpl-data/fonts/ttf/LICENSE_DEJAVU` y `LICENSE_STIX`.
- **Pillow**: en Windows, sus bibliotecas nativas están compiladas
  dentro de sus extensiones `.pyd`; su `LICENSE` (76.410 caracteres)
  incluye los avisos de libjpeg, zlib, FreeType, libwebp y HarfBuzz,
  entre otros.
- **numpy** (ya presente en la CLI): su wheel de Windows trae
  `numpy.libs\libscipy_openblas64_*.dll`, que según su `LICENSE.txt`
  incluye OpenBLAS (BSD-3-Clause), LAPACK (BSD-3-Clause-Open-MPI) y el
  runtime de GCC (GPL-3.0-or-later WITH GCC-exception-3.1).

### Componentes de Matplotlib incorporados a `dist\yaas-gui.exe`

Relevados del análisis de PyInstaller (`build\yaas-gui\Analysis-00.toc`)
en Windows, con `yaas-gui.exe` de 63,4 MB:

- Matplotlib con los backends `qtagg`, `qt`, `agg`, `mixed`, `svg` y
  `pdf` (estos dos últimos declarados con `--hidden-import`, porque
  `savefig` los carga dinámicamente) y su soporte común; no se
  incorporan Tk ni Tcl.
- `mpl-data` (204 archivos): 104 de fuentes (`ttf`, 42: DejaVu, STIX,
  BaKoMa/cm y sus licencias `LICENSE_DEJAVU` y `LICENSE_STIX`; `afm`,
  47; `pdfcorefonts`, 15), imágenes de la barra de herramientas, hojas
  de estilo, datos de ejemplo y `matplotlibrc`.
- numpy (incluida `libscipy_openblas64_*.dll`), contourpy, kiwisolver,
  fontTools, PIL (`_imaging`, `_imagingcms`, `_imagingmath`, `_webp`,
  `_avif` y `_imagingtk`, este último sin Tcl/Tk), dateutil,
  pyparsing, cycler, six y packaging.
- `libcrypto-3.dll`, `libssl-3.dll` y `libffi-8.dll` provienen del
  runtime de Python 3.13 (`Python313\DLLs`), no de instalaciones
  ajenas: el build falla si el análisis menciona `xampp`.
- PyInstaller solo copió el `.dist-info` de numpy (con sus licencias);
  los textos de licencia de Matplotlib, Pillow y del resto de las
  dependencias **no quedan dentro del ejecutable** y deberán
  acompañar una eventual distribución (ver
  `docs/packaging/gui-release-compliance.md`).

El ejecutable de la CLI (`dist\yaas.exe`, 19,6 MB) no incorpora
Matplotlib ni Qt (verificado construyéndolo con el extra `gui`
instalado).

## 5. Notas de alcance

- Publicar este repositorio como código fuente **no distribuye ningún
  binario de PyNEC ni de NEC2++**: el usuario que clona el repositorio
  instala PyNEC por su cuenta desde PyPI, bajo los términos que PyNEC
  declare en ese momento.
- Un ejecutable generado con `scripts\build_windows.ps1`
  (`dist\yaas.exe`) sí incorpora físicamente PyNEC/NEC2++, Eigen y el
  bootloader de PyInstaller, y por lo tanto **requiere un paquete de
  cumplimiento adicional** (fuentes correspondientes, textos de
  licencia aplicables, avisos de copyright) antes de publicarse como
  descarga binaria. Ver `docs/packaging/windows-release-compliance.md`.
- El ejecutable experimental de la GUI (`dist\yaas-gui.exe`,
  `dist/yaas-gui`) incorpora además Qt, PySide6, Matplotlib y sus
  dependencias (sección 4), y su
  eventual distribución requiere el paquete descrito en
  `docs/packaging/gui-release-compliance.md`. Hoy no se publica.
