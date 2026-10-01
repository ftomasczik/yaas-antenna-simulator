# Política de cumplimiento para una release binaria de Windows

Este documento define qué deberá contener una futura release pública
que incluya `dist\yaas.exe` como archivo descargable. No constituye
asesoramiento legal profesional (ver
`docs/decisions/0004-project-license.md`).

## Por qué hace falta un paquete de cumplimiento

`scripts\build_windows.ps1` genera un ejecutable funcional de YAAS con
PyInstaller, y hoy se usa para desarrollo y verificación local. Ese
ejecutable **no constituye, por sí solo, un paquete público completo
de cumplimiento**: incorpora físicamente PyNEC/NEC2++
(GPL-2.0-or-later), Eigen (MPL-2.0) y el bootloader de PyInstaller
(GPL-2.0-or-later WITH Bootloader-exception) — ver
`THIRD_PARTY_NOTICES.md` para el detalle y la evidencia de cada
componente. Distribuir únicamente `yaas.exe`, sin más, dejaría sin
cumplir la obligación de ofrecer el código fuente correspondiente de
esos componentes de terceros.

Por esta razón, **YAAS no publicará todavía `yaas.exe` como asset
descargable** en ninguna release de GitHub hasta que exista un paquete
de cumplimiento reproducible como el que describe este documento.

## Assets que deberá contener una futura release binaria

Cada release que incluya un ejecutable de Windows deberá adjuntar,
como assets de esa misma release de GitHub:

1. `yaas.exe` — el ejecutable generado por
   `scripts\build_windows.ps1`.
2. El código fuente exacto de YAAS correspondiente al tag de esa
   release (GitHub genera automáticamente el archivo de código fuente
   por tag, pero conviene enlazarlo explícitamente en las notas de la
   release).
3. `LICENSE` — la licencia propia de YAAS (GPL-3.0-only).
4. `THIRD_PARTY_NOTICES.md` — el inventario de componentes de
   terceros y sus licencias.
5. **El código fuente correspondiente de PyNEC 2.3.4**, preferentemente
   el sdist exacto utilizado para construir ese ejecutable
   (`pynec-2.3.4.tar.gz`), adjunto como asset de la misma release y
   verificado por su SHA-256, en vez de depender únicamente de un
   enlace externo a PyPI. Un enlace externo aislado no garantiza por
   sí solo que el código fuente correspondiente siga disponible o sea
   exactamente el mismo que se usó para compilar ese ejecutable en
   particular; adjuntar el sdist exacto a la release evita esa
   dependencia externa.
6. Los textos completos de las licencias aplicables:
   - GPL-3.0 (la de `LICENSE`, ya cubre YAAS).
   - GPL-2.0 (NEC2++ y el bootloader de PyInstaller).
   - MPL-2.0 (Eigen).
7. Los avisos de copyright de NEC2++ (Timothy C. A. Molteno) y de
   Eigen, tal como aparecen en sus fuentes originales.
8. El disclaimer histórico de NEC2/LLNL, preservado sin reformular.
9. Las instrucciones y scripts necesarios para reproducir la build
   (`scripts\build_windows.ps1` y los pasos de
   `AGENTS.md`/`README.md` para instalar el entorno de desarrollo),
   de modo que un tercero pueda reconstruir un ejecutable equivalente
   a partir del código fuente adjunto.
10. Checksums (SHA-256) de todos los assets de la release, incluidos
    `yaas.exe` y el sdist de PyNEC adjunto.

## Qué no cubre este documento todavía

- No define un proceso automatizado de release (firma, CI, publicación
  de assets): describe únicamente el contenido mínimo esperado.
- No resuelve la inconsistencia de metadata de PyNEC descrita en
  `docs/decisions/0004-project-license.md` (metadata `GPL-3.0-only`
  frente a un `LICENCE.txt` con plantilla de GPLv2 sin completar en su
  sdist): esa inconsistencia se documenta, no se corrige aquí, y el
  paquete de cumplimiento debe reflejarla tal como es.
- No incluye, en este repositorio, ninguna fuente de terceros
  (`pynec-2.3.4.tar.gz` u otra): este documento solo describe el
  proceso futuro; el sdist se adjuntará como asset de la release
  correspondiente cuando esta política se ejecute, no antes.

## Estado actual

Este documento cubre el ejecutable de la CLI (`dist\yaas.exe`). El
ejecutable experimental de la GUI (`dist\yaas-gui.exe`) incorpora
además Qt y PySide6 y tiene su propia política en
`docs/packaging/gui-release-compliance.md`.

Ninguna release binaria se ha publicado todavía. La primera
publicación pública prevista de YAAS es del **repositorio fuente**,
sin ningún asset ejecutable adjunto, hasta completar el paquete
descrito en este documento.
