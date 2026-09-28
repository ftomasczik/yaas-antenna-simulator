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

## 4. Notas de alcance

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
