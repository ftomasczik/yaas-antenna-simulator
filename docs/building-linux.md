# Build local de YAAS en Linux

Esta guía describe cómo construir y probar manualmente el ejecutable
experimental de YAAS para Linux, usando `scripts/build_linux.sh`. Es
el mismo script que ejecuta el job `build-linux` de
`.github/workflows/tests.yml`, así que seguir estos pasos reproduce
localmente lo que corre en CI.

## 1. Plataformas verificadas

- **Ubuntu 24.04 LTS**, como plataforma principal de este build
  experimental (job `build-linux`, `runs-on: ubuntu-24.04`).
- **Ubuntu 22.04**, como compatibilidad de CI: la suite completa de
  pruebas corre ahí también (job `test-ubuntu`), pero el ejecutable
  experimental solo se genera y prueba sobre Ubuntu 24.04.

Ver `.github/workflows/tests.yml` para el detalle exacto de ambos
jobs.

## 2. Requisitos

- Arquitectura x86-64.
- Git.
- `curl`.
- Acceso a Internet (para clonar el repositorio, instalar `uv` y
  resolver las dependencias de PyPI, incluido el wheel de PyNEC).
- Python 3.13, administrado mediante [`uv`](https://docs.astral.sh/uv/).

En la configuración verificada —Ubuntu 24.04 x86-64 y Python
3.13— no hizo falta instalar ninguna dependencia nativa adicional
(compilador, bibliotecas de sistema): `pip`/`uv` resolvieron
directamente el wheel binario `manylinux` que PyNEC 2.3.4 publica
para CPython 3.13, sin compilar nada. Esto no es una garantía general
para cualquier otra arquitectura, distribución o versión de Python:
si en un entorno distinto no hay un wheel compatible, `pip` intentará
compilar PyNEC desde su sdist, lo que sí puede requerir herramientas
de compilación adicionales.

## 3. Procedimiento completo

```bash
# 1. Instalar Git y curl (si no están ya presentes).
sudo apt-get update
sudo apt-get install -y git curl

# 2. Instalar uv.
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"

# 3. Clonar el repositorio.
git clone https://github.com/ftomasczik/yaas-antenna-simulator.git
cd yaas-antenna-simulator

# 4. Crear el entorno virtual con Python 3.13.
uv venv --python 3.13 .venv
source .venv/bin/activate

# 5. Instalar el proyecto en modo editable, con dependencias de desarrollo.
uv pip install -e ".[dev]"

# 6. Ejecutar el build experimental de Linux.
bash scripts/build_linux.sh

# 7. Verificar que el ejecutable se generó.
ls -l dist/yaas
```

`scripts/build_linux.sh` ya ejecuta `python3 -m pytest`, limpia los
resultados de un build anterior de YAAS (`dist/yaas`, `build/yaas`,
`yaas.spec`), genera `dist/yaas` con PyInstaller y valida los tres
proyectos de ejemplo (ver sección 4). Si el script termina sin
errores, `dist/yaas` es un ejecutable independiente, listo para
probarse manualmente.

## 4. Pruebas manuales

Además de lo que ya verifica `scripts/build_linux.sh`, podés
ejecutar manualmente:

```bash
# Versión.
./dist/yaas --version

# Diagnóstico del entorno.
./dist/yaas doctor

# Ayuda en español.
./dist/yaas --language es --help

# Simulación de los tres proyectos de ejemplo.
./dist/yaas simulate examples/dipole-20m.yaas
./dist/yaas simulate examples/monopole-20m-perfect-ground.yaas
./dist/yaas simulate examples/dipole-20m-real-ground.yaas
```

`--version` debe informar `yaas 0.3.0`; `doctor` debe reportar
`PyNEC: OK` y `Environment: OK`; la ayuda en español debe mostrar el
texto traducido del dominio gettext `yaas` (por ejemplo, "Simulador
de antenas basado en NEC2++."); las tres simulaciones deben coincidir
con los valores ya documentados en `docs/releases/0.3.0.md`
(impedancia y ROE de cada proyecto).

## 5. Instalación opcional en `~/.local/bin`

Para tener `yaas` disponible como comando en la sesión de shell, sin
instalarlo como paquete del sistema:

```bash
mkdir -p ~/.local/bin
cp dist/yaas ~/.local/bin/yaas
chmod +x ~/.local/bin/yaas

# Asegurate de que ~/.local/bin esté en el PATH.
yaas --version
```

Esto es completamente opcional y solo afecta a la cuenta de usuario
actual; no reemplaza ni interfiere con la instalación editable del
proyecto (`.venv`).

## 6. Aclaraciones importantes

- Este ejecutable es **local y experimental**: se genera para
  verificar que YAAS funciona sobre Linux, no como un producto
  terminado.
- **No debe adjuntarse a la release `v0.3.0`** ni a ninguna otra
  release de GitHub todavía: el job `build-linux` no publica ningún
  artefacto (no usa `actions/upload-artifact`) y esta guía tampoco lo
  hace.
- La rama `main` puede contener commits posteriores al tag `v0.3.0`
  (por ejemplo, la integración continua y este mismo build
  experimental de Linux). El tag `v0.3.0` sigue señalando el commit de
  esa release específica; construir el ejecutable de Linux desde
  `main` no implica que esos cambios formen parte de la versión
  0.3.0 publicada.
- **Todavía no existe un paquete binario oficial para Linux**: a
  diferencia de `dist\yaas.exe` en Windows (que tampoco se publica
  aún como descarga pública, ver
  `docs/packaging/windows-release-compliance.md`), no hay ninguna
  política de cumplimiento ni paquete de distribución binaria
  definido todavía para Linux. `THIRD_PARTY_NOTICES.md` sigue
  aplicando igual: si en el futuro se distribuye un binario de Linux,
  va a incorporar los mismos componentes de terceros (PyNEC/NEC2++,
  Eigen) y las mismas obligaciones de código fuente correspondiente.

## 7. Solución de problemas

- **Confirmá que estás usando Python 3.13**: `python3 --version`
  (o `python --version` dentro del entorno virtual activado). YAAS
  requiere `>=3.13,<3.14` (ver `pyproject.toml`).
- **Confirmá que `PyNEC: OK` aparece en `doctor`**: si en cambio ves
  `PyNEC: ERROR - ...`, generalmente significa que el wheel de PyNEC
  no se instaló correctamente para tu versión de Python/arquitectura;
  revisá la salida de `uv pip install -e ".[dev]"` en busca de
  errores de instalación antes de intentar nada más.
- **Si el build falla a mitad de camino**, eliminá los resultados de
  un intento anterior antes de reintentar (las mismas rutas que
  limpia el propio script, por si quedaron en un estado inconsistente):

  ```bash
  rm -f dist/yaas
  rm -rf build/yaas
  rm -f yaas.spec
  ```

- **Volvé a ejecutar el script**: `bash scripts/build_linux.sh`. Si
  vuelve a fallar, el mensaje de error indica en qué paso ocurrió
  (pruebas, generación del ejecutable, o alguna de las validaciones
  de los proyectos de ejemplo).
