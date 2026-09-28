# ADR 0004: Adoptar una licencia compatible con PyNEC

- Estado: Aceptada
- Fecha: 2026-09-20
- Fecha de revisión: 2026-09-27

## Contexto

El proyecto incorpora PyNEC y NEC2++ como componentes fundamentales
del motor de simulación.

PyNEC se distribuye actualmente en PyPI bajo la licencia
GPL-3.0-only.

La aplicación se distribuirá junto con PyNEC y con las bibliotecas
necesarias para ejecutar NEC2++.

Por lo tanto, la licencia del proyecto debe ser compatible con las
obligaciones de esos componentes.

## Evidencia (revisión 2026-09-27)

Esta revisión inspeccionó directamente el código fuente de la
distribución PyNEC 2.3.4 (sdist `pynec-2.3.4.tar.gz`, SHA-256
`d448d038d2bcb4265d511b2440a5d5ce26081269a776d45139fb8bf17a475df4`),
no solo su metadata publicada ni un archivo `COPYING`/`LICENSE.txt`
genérico:

- La metadata instalada de PyNEC 2.3.4 declara
  `License-Expression: GPL-3.0-only`.
- El sdist incluye, sin embargo, un `LICENCE.txt` con el texto
  plantilla completo de la GPLv2 (marcadores `{year}`/`{fullname}` sin
  completar) — es decir, la metadata declarada y el archivo de
  licencia empaquetado son inconsistentes entre sí. Esto se documenta
  como lo que es, una inconsistencia de la distribución de PyNEC, sin
  ocultarla y sin resolverla unilateralmente en nombre de ese proyecto.
- Los encabezados reales de los archivos fuente de NEC2++ (el motor
  C++ incorporado dentro de PyNEC, con copyright de Timothy C. A.
  Molteno) declaran genuinamente "either version 2 of the License, or
  (at your option) any later version" → **GPL-2.0-or-later**.
- `GPL-2.0-or-later` permite, mediante su propia cláusula "o una
  versión posterior", acogerse a GPL-3.0 sin conflicto: esto hace que
  `GPL-3.0-only` sea una licencia compatible para YAAS, aunque no
  confirma que la metadata `GPL-3.0-only` de PyNEC sea, en sí misma,
  una elección deliberada y documentada por su mantenedor (ver
  inconsistencia arriba).
- Eigen, vendorizado dentro de las fuentes de PyNEC/NEC2++
  (`necpp_src/src/eigen/`), se distribuye bajo **MPL-2.0**.
- NEC2 original (Fortran, Lawrence Livermore National Laboratory)
  conserva únicamente el disclaimer histórico de responsabilidad
  propio de una obra del gobierno de EE. UU., sin una licencia de
  copyright explícita equivalente a las anteriores; no se declara aquí
  "dominio público" ni ninguna otra licencia sin evidencia firme.

Detalle completo de cada componente y su evidencia en
`THIRD_PARTY_NOTICES.md`.

## Decisión

El proyecto se desarrolla como software de código abierto.

La licencia definitiva del código propio de YAAS es:

    GNU General Public License v3.0 only (GPL-3.0-only)

Se descarta explícitamente **GPL-2.0-only**: NEC2++, el componente de
terceros más restrictivo en la cadena de dependencias, ya se declara
`GPL-2.0-or-later` (no `GPL-2.0-only`), y la propia distribución de
PyNEC declara `GPL-3.0-only` en su metadata. Adoptar GPL-2.0-only para
YAAS habría sido innecesariamente restrictivo (impediría acogerse a
mejoras de la versión 3, como su lenguaje de compatibilidad de
patentes más explícito) sin ninguna obligación real que lo exigiera.

El texto canónico completo de la licencia está en `LICENSE`, obtenido
verbatim de una fuente oficial de la Free Software Foundation, sin
modificaciones ni texto generado. El aviso de copyright del código
propio (Copyright (C) 2026 Federico Tomasczik) se documenta en
`README.md` y en la metadata de `pyproject.toml`, no dentro del propio
`LICENSE`.

Antes de realizar la primera distribución pública se incorporaron:

- Un archivo `LICENSE` (texto canónico de GPL-3.0-only).
- Metadata de licencia en `pyproject.toml`
  (`license = "GPL-3.0-only"`, `license-files = ["LICENSE"]`).
- `THIRD_PARTY_NOTICES.md`, con el inventario de dependencias de
  ejecución, herramientas de build/desarrollo y componentes
  transitivos incorporados específicamente al generar el ejecutable
  PyInstaller.
- `docs/packaging/windows-release-compliance.md`, que documenta qué
  deberá incluir una futura release binaria (fuentes de PyNEC,
  licencias aplicables, avisos de copyright, checksums) sin, todavía,
  publicar ningún ejecutable descargable.

## Publicación de fuente frente a distribución binaria

Esta decisión distingue explícitamente dos escenarios, con
obligaciones distintas:

- **Publicación del repositorio fuente** (la primera prevista): no
  distribuye ningún binario de PyNEC/NEC2++; cada usuario instala
  PyNEC por su cuenta desde PyPI. Las obligaciones de la GPL sobre el
  código fuente propio de YAAS (ofrecer el texto de la licencia,
  mantener los avisos de copyright, no imponer restricciones
  adicionales) ya quedan cubiertas por `LICENSE` y este ADR.
- **Distribución binaria** (`dist\yaas.exe` generado con
  `scripts\build_windows.ps1`): incorpora físicamente PyNEC/NEC2++
  (GPL-2.0-or-later), Eigen (MPL-2.0) y el bootloader de PyInstaller
  (GPL-2.0-or-later WITH Bootloader-exception). Esto exige ofrecer el
  código fuente correspondiente de esos componentes, no solo el
  propio. **El ejecutable no se publicará como descarga pública hasta
  completar un paquete de cumplimiento reproducible** (ver
  `docs/packaging/windows-release-compliance.md`); por ahora,
  `scripts\build_windows.ps1` sigue usándose para desarrollo y
  verificación local, no para distribución.

## Obligaciones previstas

Al distribuir la aplicación se deberá:

- Proporcionar el texto de la licencia.
- Mantener los avisos de copyright.
- Informar las modificaciones realizadas.
- Ofrecer el código fuente correspondiente.
- Proporcionar instrucciones reproducibles de compilación.
- No imponer restricciones incompatibles con la GPL.

## Dependencias futuras

Antes de incorporar una dependencia nueva se revisará:

- Su licencia.
- Su compatibilidad con GPL-3.0-only.
- Sus requisitos de atribución.
- Sus condiciones de redistribución.
- Si incluye bibliotecas nativas adicionales.

Esta revisión se aplicará especialmente a:

- PySide6 y Qt.
- Bibliotecas de gráficos.
- Lectores de Touchstone.
- Componentes para visualización 3D.
- Recursos gráficos, iconos y tipografías.

## Consecuencias

### Positivas

- Compatibilidad inicial con la licencia declarada por PyNEC.
- Transparencia para usuarios y colaboradores.
- Posibilidad de auditoría y mejora comunitaria.
- Coherencia con la preferencia por software abierto.

### Negativas

- La distribución debe cumplir las obligaciones de la GPL.
- Una distribución cerrada o propietaria requeriría revisar la
  arquitectura y las licencias.
- Las dependencias futuras deberán evaluarse antes de incorporarlas.

## Nota

Este documento registra una decisión técnica del proyecto, basada en
evidencia local verificable (metadata instalada y encabezados de
código fuente), y no constituye asesoramiento jurídico profesional.

La elección de GPL-3.0-only para el código fuente propio se considera
definitiva. La distribución binaria (`yaas.exe`) queda sujeta,
además, al paquete de cumplimiento descrito en
`docs/packaging/windows-release-compliance.md`, todavía pendiente de
completarse. Cualquier uso comercial o distribución cerrada debería
revisarse por separado, con asesoramiento apropiado.