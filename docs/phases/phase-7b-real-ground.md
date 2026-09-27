# Fase 7B — Tierra real homogénea (Sommerfeld-Norton)

## Estado

Completada.

## 1. Objetivo

Agregar un tercer entorno de simulación a AntSim, tierra real
homogénea (con pérdidas) mediante el método Sommerfeld-Norton,
propagado de punta a punta: dominio, esquema de proyecto `.antsim`
(nueva versión 3), motor PyNEC/NEC2++ (incluida una estrategia de
barrido dedicada), exportación NEC, un proyecto de ejemplo real,
validación cruzada contra 4nec2 y cobertura en el ejecutable de
Windows — siguiendo la misma disciplina de investigación previa,
implementación y validación externa ya usada en la fase 7A.

## 2. Alcance implementado

- **`RealGroundModel`** (`src/antsim/domain/models.py`): un `Enum` que
  hereda también de `str` (`class RealGroundModel(str, Enum)`), con un
  único valor por ahora, `SOMMERFELD_NORTON = "sommerfeld_norton"`. El
  método rápido por coeficiente de reflexión (Fresnel) queda
  deliberadamente fuera: la investigación previa encontró resultados
  sin sentido físico para conductores cercanos al plano de tierra con
  ese método (ver `docs/research/nec-real-ground.md`).
- **`RealGroundEnvironment`** (dataclass inmutable, agregada al alias
  `Environment`): campos `relative_permittivity: float`,
  `conductivity_s_per_m: float` y `model: RealGroundModel =
  RealGroundModel.SOMMERFELD_NORTON`.
- **Validación de conductores respecto de z=0**: reutilizada sin
  cambios. `_validate_wires_against_ground` solo trata distinto a
  `FreeSpaceEnvironment`; como `RealGroundEnvironment` no lo es, la
  misma restricción de la fase 7A (ningún extremo en `z < 0`, ningún
  conductor contenido por completo en `z = 0`) se aplica
  automáticamente, sin duplicar lógica.
- **Validación de permitividad, conductividad y modelo**
  (`RealGroundEnvironment.__post_init__`):
  - `relative_permittivity` debe ser finita y estrictamente positiva
    (rechaza `0`, negativos, `NaN` e `Inf`);
  - `conductivity_s_per_m` debe ser finita y mayor o igual a cero
    (rechaza negativos, `NaN` e `Inf`; **`0.0` se admite
    explícitamente**, como un dieléctrico homogéneo sin pérdidas, un
    caso límite válido de la formulación física — distinto de "no hay
    tierra", que se expresa con `FreeSpaceEnvironment`);
  - `model` debe ser una instancia real de `RealGroundModel`: un
    string igual a `"sommerfeld_norton"`, un entero o cualquier otro
    objeto se rechazan sin conversión silenciosa.
- **`PyNecEngine` con Sommerfeld-Norton**: para simulación puntual,
  ```python
  geometry_complete(1)
  gn_card(2, 0, relative_permittivity, conductivity_s_per_m, 0, 0, 0, 0)
  ```
  (mismo orden ya usado por espacio libre y tierra perfecta: primero
  los conductores, luego `GE`, luego `GN`). Un `RealGroundModel` no
  reconocido (hoy, imposible de construir a través del dominio, pero
  probado inyectándolo directamente) produce un `ValueError`
  explícito, nunca una caída silenciosa a tierra perfecta.
- **Estrategia de barrido dedicada**: espacio libre y tierra perfecta
  conservan la estrategia histórica (`_simulate_sweep_single_context`,
  un único contexto NEC2++ reutilizado con `fr_card` multipunto).
  Tierra real usa `_simulate_sweep_per_frequency`: crea un contexto
  NEC2++ completamente nuevo por cada frecuencia, reconstruyendo
  geometría, `GE`/`GN` y fuente, sin compartir ningún estado ni tabla
  de Sommerfeld-Norton entre puntos. Ver sección 3 para la
  justificación.
- **Diferencia entre la API de PyNEC y la tarjeta NEC de texto**:
  `gn_card()` de PyNEC recibe **8 argumentos posicionales**
  (`ground_type, rad_wire_count, F1, F2, F3, F4, F5, F6`); la tarjeta
  `GN` de texto tiene siempre **4 campos enteros (I1-I4) seguidos de 6
  campos flotantes (F1-F6)** — **10 valores**, con I3/I4 reservados en
  blanco (que `gn_card()` ni siquiera expone). Copiar literalmente la
  cantidad de argumentos de `gn_card()` a la tarjeta de texto produce
  un archivo mal formado (los valores se desplazan un campo); esto se
  detectó y corrigió durante esta fase (commit `9a25d4c`) antes de
  escribir el exportador.
- **Exportación NEC**: para `RealGroundEnvironment`,
  ```text
  GE 1
  GN 2 0 0 0 relative_permittivity conductivity_s_per_m 0 0 0 0
  ```
  siempre después de la última `GW` y antes de `EX`/`FR`; el barrido
  de tierra real exporta una única `GE`/`GN` y una única `FR`
  multipunto (aunque `PyNecEngine` internamente use un contexto por
  frecuencia): esto ya fue validado manualmente con 4nec2. Verificado
  estructuralmente (no solo por subcadena): token inicial `GN`,
  exactamente 10 campos, `I1..I4 == 2,0,0,0`, `F1`/`F2` iguales a
  permitividad/conductividad, `F3..F6 == 0`.
- **`.antsim` schema version 3**: ver sección 4 para el contrato
  completo.
- **Ejemplo real**: `examples/dipole-20m-real-ground.antsim` — ver
  sección 6.
- **Validación cruzada con 4nec2**: ver sección 5.
- **Smoke tests del ejecutable Windows** (`scripts/build_windows.ps1`):
  ver sección 7.

## 3. Razón para un contexto NEC independiente por frecuencia

La investigación empírica (`docs/research/nec-real-ground.md`)
encontró que, para un monopolo alimentado en la base (tocando z=0), un
barrido de Sommerfeld-Norton en un único contexto NEC2++ reutilizado
no coincide exactamente con el resultado de cada frecuencia calculada
de forma independiente: la discrepancia fue sistemática y no
despreciable (~0.6-0.9 Ω). Para el dipolo elevado usado como modelo de
referencia de esta fase, la misma comparación mostró en cambio una
discrepancia de apenas ~1e-7 a 1e-8 Ω (ruido de punto flotante) —
es decir, la magnitud del efecto depende de la geometría, no es un
problema uniforme.

**Decisión:** `PyNecEngine.simulate_sweep` crea un contexto nuevo por
frecuencia para tierra real **siempre**, no solo para geometrías
cercanas al plano de tierra. Es una decisión deliberadamente
conservadora: AntSim no puede garantizar que todo conductor con tierra
real quedará siempre lejos del plano de tierra (un monopolo alimentado
en la base es un caso de uso legítimo y esperado), así que la
estrategia más segura se aplica de forma general. Esta decisión no
tiene costo de rendimiento medible: crear un contexto nuevo por
frecuencia no resultó más lento que reutilizar uno solo (ver sección
6.2), porque el tiempo está dominado por el cálculo de
Sommerfeld-Norton en sí (~40 ms/punto), no por la creación del
contexto.

Ver `docs/validation/real-ground-dipole-4nec2.md`, secciones 9-11,
para el detalle completo de esta decisión y su respaldo numérico.

## 4. Contrato de `schema_version` y migraciones

- **v1**: sin `simulation.environment` (se rechaza si aparece); se
  interpreta siempre como `FreeSpaceEnvironment`; un objeto leído de
  v1 conserva `schema_version == 1` en memoria.
- **v2**: `simulation.environment` obligatorio; admite únicamente
  `{"kind": "free_space"}` o `{"kind": "perfect_ground"}`;
  `{"kind": "real_ground"}` se rechaza explícitamente bajo v2 (mensaje
  de error mencionando `kind`, igual que cualquier otro valor
  desconocido); un objeto leído de v2 conserva `schema_version == 2`.
- **v3** (nueva en esta fase): `simulation.environment` obligatorio;
  admite `free_space`, `perfect_ground` o, ahora, `real_ground`:
  ```json
  "environment": {
    "kind": "real_ground",
    "model": "sommerfeld_norton",
    "relative_permittivity": 13.0,
    "conductivity_s_per_m": 0.005
  }
  ```
  sin claves adicionales ni faltantes; `model` debe ser exactamente el
  string `"sommerfeld_norton"` (no se acepta ningún otro valor);
  `relative_permittivity`/`conductivity_s_per_m` deben ser números
  JSON válidos y finitos (se rechaza `bool`, `null`, listas, objetos y
  strings numéricos sin convertir); los rangos de dominio (permitividad
  ≤ 0, conductividad negativa) se delegan en
  `RealGroundEnvironment.__post_init__`, cuyo `ValueError` el lector
  traduce a `ProjectFormatError` mediante el mismo mecanismo ya usado
  para el resto de las validaciones de dominio.
  `CURRENT_SCHEMA_VERSION = 3`, `SUPPORTED_SCHEMA_VERSIONS = (1, 2, 3)`.
- **Migración**: `project_to_dict`/`save_project` siempre escriben
  `schema_version: 3`, sin importar el `schema_version` del objeto en
  memoria. Guardar un proyecto leído de v1 o v2 lo migra
  automáticamente a v3; la función no muta el objeto `AntennaProject`
  recibido (dataclass inmutable). Verificado explícitamente: v1 →
  guardar → v3/`free_space`; v2/`free_space` y v2/`perfect_ground`
  (fixtures históricos independientes del escritor actual) → guardar →
  v3, mismo entorno; v3/`real_ground` → guardar → v3/`real_ground` sin
  cambios.

## 5. Compatibilidad histórica de los esquemas v1 y v2

- `examples/dipole-20m.antsim` (v1) y
  `examples/monopole-20m-perfect-ground.antsim` (v2) **no se
  modificaron** en esta fase y continúan cargando exactamente igual
  que antes.
- Un lector v2 que reciba `real_ground` lo rechaza como `kind` no
  soportado — no lo ignora en silencio ni lo interpreta como espacio
  libre o tierra perfecta.
- El objeto `AntennaProject` recién leído conserva el
  `schema_version` con el que fue leído (1, 2 o 3) mientras esté en
  memoria; solo al guardarlo se reescribe como 3.
- Guardar un proyecto (`project_to_dict`/`save_project`) no muta el
  objeto `AntennaProject` recibido, verificado también para un
  proyecto recién cargado de un archivo v2 histórico.

## 6. Ejemplo y resultados

### 6.1 Ejemplo

`examples/dipole-20m-real-ground.antsim` (schema 3, generado con
`save_project` para garantizar formato idéntico al escritor actual):

- Dipolo horizontal, de (-5.03, 0, 10) a (5.03, 0, 10) m — elevado
  10 m sobre el plano de tierra (a diferencia del monopolo de la fase
  7A, que toca z=0).
- Radio 0.001 m, 101 segmentos, fuente en el segmento 51.
- Frecuencia principal 14.15 MHz, impedancia de referencia 50 Ω.
- `environment`: `real_ground`, `sommerfeld_norton`, permitividad
  relativa 13.0, conductividad 0.005 S/m.
- Barrido 13.5-15.5 MHz, 81 puntos, límite de ROE 2.0.

### 6.2 Resultados AntSim/PyNEC y 4nec2

A 14.150 MHz (`docs/validation/real-ground-dipole-4nec2.md`,
sección 7):

| Motor | Impedancia | ROE (50 ohm) |
|---|---:|---:|
| AntSim / PyNEC | 66.57 - j41.36 ohm | 2.13 |
| 4nec2 V5.9.3 | 66.6 - j41.4 ohm | 2.13 |

Diferencia AntSim - 4nec2: ~0.04 Ω, dentro de la resolución de
redondeo con que 4nec2 reporta sus resultados.

Barrido, tres frecuencias (misma referencia, sección 8):

| Frecuencia | AntSim / PyNEC | 4nec2 V5.9.3 | Diferencia |
|---:|---:|---:|---:|
| 13.5 MHz | 60.30 - j106.76 ohm, ROE 5.64 | 60.2981 - j106.78 ohm, ROE 5.64002 | ≤ 0.016 Ω |
| 14.5 MHz | 69.96 - j6.05 ohm, ROE 1.42 | 69.9534 - j6.0735 ohm, ROE 1.4203 | ≤ 0.021 Ω |
| 15.5 MHz | 81.80 + j97.18 ohm, ROE 4.33 | 81.7964 + j97.1602 ohm, ROE 4.32414 | ≤ 0.024 Ω |

Todas las diferencias son consistentes con la resolución de redondeo
de 4nec2 y con las diferencias normales esperables entre dos
implementaciones independientes de NEC2 (PyNEC/necpp frente al motor
usado por 4nec2).

### 6.3 Rendimiento medido para barridos

Dipolo de referencia, 13.5-15.5 MHz
(`docs/validation/real-ground-dipole-4nec2.md`, sección 9):

| Puntos | Contexto único | Contexto nuevo por frecuencia |
|---:|---:|---:|
| 11 | ~505-511 ms | ~449-462 ms |
| 81 | ~3360-3456 ms | ~3381-3494 ms |
| 201 | ~8517-8637 ms | ~8333-8454 ms |

Aproximadamente 42 ms por punto en promedio, sin importar la
estrategia; el ejecutable PyInstaller real (`scripts/build_windows.ps1`,
incluye arranque de proceso) midió ~5.17 s para el barrido de 81
puntos del ejemplo, consistente con esa cifra.

## 7. Cobertura del build de Windows

`scripts/build_windows.ps1` ejercita el ejecutable PyInstaller real
para los tres esquemas:

- **v1** (espacio libre): `GE 0`, sin ninguna tarjeta `GN` — sin
  cambios respecto de la fase 7A.
- **v2** (tierra perfecta): `GE 1`, `GN 1 0 0 0 0 0 0 0` — sin
  cambios respecto de la fase 7A.
- **v3** (tierra real, nuevo en esta fase): valida esquema 3,
  simula (66.57 -41.36j ohm, ROE 2.13), ejecuta el barrido de 81
  puntos (resonancia 14.550 MHz, ROE mínima 1.41, ancho de banda
  700.0 kHz / 4.81 %, sin truncamiento) y exporta NEC puntual y de
  barrido, verificando el orden `GW < GE < GN < EX < FR < EN` y la
  tarjeta `GN` **campo por campo** (no solo por subcadena) mediante un
  nuevo helper reutilizable, `Assert-GnCardFields`.

## 8. Límites

- Solo se implementó Sommerfeld-Norton; el método rápido por
  coeficiente de reflexión (Fresnel) queda pospuesto (ver
  `docs/research/nec-real-ground.md` para la razón: resultados sin
  sentido físico para conductores cercanos al plano de tierra).
- La importación MMANA-GAL sigue rechazando cualquier entorno que no
  sea espacio libre, incluidas tierra perfecta y tierra real.
- No hay radiales ni pantallas de tierra, para ningún tipo de tierra.
- No hay conductores enterrados (bajo el plano de tierra); esa
  geometría sigue rechazándose explícitamente.
- Esta fase no valida patrones de radiación ni ganancia: solo
  impedancia de entrada.
- Los barridos con tierra real no ofrecen progreso ni cancelación:
  un barrido de 81 puntos puede tardar varios segundos.
- La interfaz gráfica queda fuera de alcance, como en todas las fases
  anteriores.

## 9. Commits de la fase

Obtenidos de `git log`, en orden cronológico:

```text
1e4c2cf research: characterize NEC real ground
9a25d4c docs: correct real-ground GN card layout
970b697 docs: validate Sommerfeld ground with 4nec2
e213014 feat: add real-ground domain model
ba2fc30 feat: support Sommerfeld real ground in PyNecEngine
4949343 feat: add real ground to project schema v3
98ae0ca feat: export Sommerfeld real ground to NEC
d6ac7dd feat: add real-ground dipole example
341a398 build: test real-ground executable
```

## 10. Criterios de aceptación

| Criterio | Estado |
|---|---|
| `RealGroundModel`/`RealGroundEnvironment` en el dominio | Cumplido |
| Validación de permitividad/conductividad/modelo | Cumplido |
| Validación de conductores contra z=0 (reutilizada, sin duplicar) | Cumplido |
| `PyNecEngine` con Sommerfeld-Norton (simulación puntual) | Cumplido |
| Estrategia de barrido de contexto nuevo por frecuencia | Cumplido |
| Esquema `.antsim` v3, con lectura compatible de v1 y v2 | Cumplido |
| Escritura siempre en v3, sin mutar el objeto en memoria | Cumplido |
| Exportación NEC de tierra real, tarjeta `GN` de 10 campos correcta | Cumplido |
| Proyecto de ejemplo v3 | Cumplido |
| Validación cruzada contra 4nec2 (puntual y barrido) | Cumplido |
| Smoke tests del ejecutable Windows (v1, v2 y v3) | Cumplido |
| Suite de pruebas completa en verde | Cumplido (628 pruebas) |

## Deuda documental detectada

La fase 7A ya había anotado que no existe un documento de referencia
vivo del formato `.antsim` (`docs/phases/phase-2-projects.md` es un
cierre de fase histórico, no una referencia que se mantenga
actualizada) y sugirió crearlo "si el formato vuelve a crecer... en la
fase 7B". El formato efectivamente creció (schema 3, `real_ground`),
pero ese documento de referencia todavía no se creó: el contrato
completo de los esquemas 1, 2 y 3 sigue disperso entre
`docs/phases/phase-7a-perfect-ground.md` (sección 4) y este documento
(sección 4). Se recomienda crearlo antes de que el formato vuelva a
crecer una tercera vez.

## Documentos relacionados

- `docs/research/nec-real-ground.md` — investigación empírica de
  Sommerfeld-Norton en PyNEC/NEC2++ previa a esta fase, incluida la
  corrección del formato de la tarjeta `GN` (4 enteros + 6 flotantes).
- `docs/validation/real-ground-dipole-4nec2.md` — validación cruzada
  completa (PyNEC, 4nec2, rendimiento de barrido, decisión de
  arquitectura sobre el contexto por frecuencia).
- `examples/dipole-20m-real-ground.antsim` — proyecto de ejemplo v3
  usado en la validación.
- `docs/phases/phase-7a-perfect-ground.md` — fase anterior (espacio
  libre y tierra perfecta), cuya sección 8 ya anticipaba el alcance de
  esta fase.

## Resultado

AntSim puede representar, en el dominio, en el esquema de proyecto, en
el motor de simulación y en la exportación NEC, tierra real homogénea
mediante Sommerfeld-Norton, además de espacio libre y tierra
perfectamente conductora, con un ejemplo real validado de forma
independiente contra 4nec2 y cobertura completa en el ejecutable de
Windows para los tres esquemas de proyecto (v1, v2 y v3).
