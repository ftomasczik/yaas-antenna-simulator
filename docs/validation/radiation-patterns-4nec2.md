# Validación cruzada: patrones de radiación (PyNEC y 4nec2)

Fecha: 2026-09-29

## 1. Objetivo y alcance

Esta validación aporta evidencia suficiente para cerrar dos de las
"Preguntas abiertas" de
[`docs/research/nec-radiation-patterns.md`](../research/nec-radiation-patterns.md):
el punto 4 (comparación externa con 4nec2) y el punto 6 (sentido
creciente de `phi`). Ese documento de investigación no se modifica
aquí: sus preguntas siguen redactadas como abiertas y este documento
solo registra la evidencia que permite cerrarlas. Compara los
patrones de radiación calculados
con PyNEC/NEC2++ contra los calculados por 4nec2 para los mismos
modelos, y confirma:

- el cálculo de **ganancia total** (dBi, ganancia de potencia, sin
  normalización);
- las **convenciones angulares** `theta`/`phi`, incluido el sentido de
  recorrido de `phi`;
- la **orientación de los arrays** devueltos por PyNEC (qué índice
  corresponde a `theta` y cuál a `phi`);
- **simetrías, máximos y nulos** esperables para cada geometría;
- el comportamiento con **espacio libre, tierra perfecta y tierra real
  Sommerfeld-Norton**;
- la **concordancia numérica** entre PyNEC y 4nec2, dentro de la
  precisión que reporta cada herramienta.

Al igual que
[`real-ground-dipole-4nec2.md`](real-ground-dipole-4nec2.md) en su
momento, esta validación es **preparatoria**: YAAS **no implementa
todavía ninguna API de patrones de radiación** (ni modelo de dominio,
ni método de `PyNecEngine`, ni exportación, ni comando CLI). No se
modificó código, pruebas, ejemplos, esquema ni CLI. Las decisiones de
la sección 11 son requisitos para una implementación futura, no
funcionalidad existente.

## 2. Herramientas y procedencia de los datos

- PyNEC 2.3.4 (NEC2++), el mismo instalado en `.venv` y usado por
  `src/yaas/engines/pynec.py`, ejecutado mediante script.
- 4nec2 V5.9.3, Windows x64.
- Frecuencia de todos los modelos: 14.15 MHz
  (lambda = 21.186746 m; lambda/4 = 5.296687 m).

Procedencia de cada tipo de dato, para no mezclar niveles de
evidencia:

- **Valores de PyNEC**: calculados por script, con `get_gain()` y
  `rp_card()` sobre las mismas geometrías y los mismos parámetros de
  las tarjetas `RP` de la sección 4, y registrados en el informe
  experimental externo generado por ese mismo script (sección 13).
  Los valores de PyNEC con cuatro decimales (por ejemplo, -31.9684,
  -29.5103 o -12.4232 dBi) y las shapes de `get_gain()` de la sección
  9 provienen de ese informe; **no** son valores copiados de 4nec2.
  Donde existe un valor 4nec2 correspondiente, se muestra por
  separado, con sus dos decimales.
- **Valores de 4nec2**: tablas copiadas manualmente de la salida de
  4nec2 por Federico Tomasczik tras ejecutar los seis archivos `.nec`
  de la sección 13; la lectura de 4nec2 no se automatizó.
- **Orientación física del lóbulo del array asimétrico**: confirmada
  manualmente en la visualización del patrón de 4nec2 (sección 8).
  Este documento no se basa en capturas de pantalla ni incorpora
  ninguna.

## 3. Convenciones angulares confirmadas

### Observación

- El dipolo horizontal sobre X presenta sus nulos exactos en
  `theta=90°, phi=0°/180°/360°` y sus máximos en `phi=90°/270°`
  (sección 5), tanto en PyNEC como en 4nec2.
- El dipolo en espacio libre presenta su máximo en `theta=0°` y
  `theta=180°`, y su nulo en `theta=90°`, sobre el meridiano `phi=0°`
  (sección 5).
- El monopolo vertical sobre tierra perfecta presenta un nulo en
  `theta=0°` y su máximo en `theta=90°` (sección 6).
- El array asimétrico, cuyo lóbulo principal apunta físicamente hacia
  +Y según la visualización de 4nec2, presenta su máximo en `phi=90°`
  tanto en PyNEC como en 4nec2 (sección 8).

### Resultado experimental definitivo

- `theta` se mide desde el eje +Z:
  - `theta=0°` = +Z (cenit);
  - `theta=90°` = plano XY (horizonte);
  - `theta=180°` = -Z (nadir).
- `phi` se mide en el plano XY desde el eje +X.
- `phi` **aumenta en sentido antihorario visto desde +Z** (regla de la
  mano derecha alrededor de +Z):
  - `phi=0°` = +X;
  - `phi=90°` = +Y;
  - `phi=180°` = -X;
  - `phi=270°` = -Y;
  - `phi=360°` = +X.
- `phi=0°` y `phi=360°` representan la misma dirección (cuando ambos
  se solicitan, PyNEC los devuelve como dos muestras separadas con
  valores idénticos, ver `docs/research/nec-radiation-patterns.md`,
  §1.7).

### Interpretación: sentido de `phi` y convención fasorial

El origen de `phi` (+X) ya estaba establecido por la investigación con
el dipolo horizontal, pero ese modelo es simétrico respecto de +Y/-Y y
no podía distinguir el sentido de recorrido. **El sentido quedó
resuelto mediante el array asimétrico de la sección 8.**

- **Convención geométrica de `phi` (confirmada inequívocamente)**: la
  visualización de 4nec2 identifica físicamente el semieje +Y (junto
  con la geometría del modelo) y muestra el lóbulo máximo apuntando
  hacia allí; tanto 4nec2 como PyNEC sitúan ese máximo en `phi=90°`.
  Por lo tanto `phi=90°` es +Y, y `phi` crece de +X hacia +Y, es
  decir, en sentido antihorario visto desde +Z.
- **Convención temporal/fasorial (no demostrada)**: el experimento no
  demuestra por sí solo cuál es la convención interna (`e^{jωt}` o
  `e^{-jωt}`) con la que NEC2 interpreta una excitación compleja de
  +90° (`0 + j1`), es decir, si el elemento 2 adelanta o atrasa en el
  tiempo respecto del elemento 1. Esa es una cuestión separada, que
  sigue pendiente de contrastar con una fuente primaria.

## 4. Tarjetas RP

### Tarjetas exactas usadas

| Modelo | Corte | Tarjeta |
|---|---|---|
| Dipolo en espacio libre | azimut (`theta=90°`) | `RP 0 1 361 0000 90 0 0 1 0 0` |
| Dipolo en espacio libre | vertical (`phi=0°`) | `RP 0 181 1 0000 0 0 1 0 0 0` |
| Monopolo sobre tierra perfecta | vertical (`phi=0°`) | `RP 0 91 1 0000 0 0 1 0 0 0` |
| Dipolo sobre tierra real | azimut (`theta=90°`) | `RP 0 1 361 0000 90 0 0 1 0 0` |
| Dipolo sobre tierra real | vertical (`phi=0°`) | `RP 0 91 1 0000 0 0 1 0 0 0` |
| Array asimétrico | azimut (`theta=90°`) | `RP 0 1 361 0000 90 0 0 1 0 0` |

Lectura de los campos (`RP I1 I2 I3 I4 F1 F2 F3 F4 F5 F6`):

- `I1=0`: modo normal (onda espacial).
- `I2`/`I3`: cantidad de valores de `theta` / `phi`.
- `I4=0000` (`XNDA`): `X=0` (salida de ejes mayor/menor), `N=0` (sin
  normalización), `D=0` (ganancia de potencia), `A=0` (sin promedio
  de potencia).
- `F1`/`F2`: `theta` y `phi` iniciales, en grados.
- `F3`/`F4`: paso de `theta` y de `phi`, en grados.
- `F5=0`: sin distancia radial (campo lejano relativo).
- `F6=0`: sin factor de normalización.

Así, los cortes de azimut recorren `phi` de 0° a 360° en pasos de 1°
(361 muestras, con 0° y 360° incluidos) a `theta=90°`; el corte
vertical en espacio libre recorre `theta` de 0° a 180° (181 muestras)
y los cortes verticales con plano de tierra recorren `theta` de 0° a
90° (91 muestras), en ambos casos a `phi=0°`.

Las llamadas PyNEC equivalentes usan los mismos valores, con `I4`
desempaquetado en cuatro argumentos separados
(`output_format, normalization, D, A`), por ejemplo
`rp_card(0, 1, 361, 0, 0, 0, 0, 90.0, 0.0, 0.0, 1.0, 0, 0)` para el
corte de azimut (ver `docs/research/nec-radiation-patterns.md`,
§1.1).

### Orden de tarjetas de los archivos externos

Los seis archivos `.nec` usaron el orden textual:

```text
CM* -> CE -> GW* -> GE -> GN (cuando corresponde) -> EX* -> FR -> RP -> EN
```

con `EX` antes de `FR`, igual que el exportador NEC existente
(`src/yaas/exporters/nec.py`), y `RP` inmediatamente después de `FR`.
4nec2 calculó los patrones de las secciones 5-8 a partir de esos
archivos.

Esto **no** equivale a afirmar que el orden interno de llamadas de la
API de PyNEC (`fr_card -> ex_card -> rp_card`, verificado en
`docs/research/nec-radiation-patterns.md`, §1.4, punto 1) sea un orden
universal obligatorio para todo archivo NEC: son dos preguntas
distintas. Lo único que esta validación registra es que el orden
textual indicado arriba funcionó con 4nec2 V5.9.3 para estos seis
archivos.

## 5. Dipolo horizontal en espacio libre

### Modelo

- Conductor único a lo largo del eje X, de (-5.03, 0, 0) a
  (5.03, 0, 0) m.
- Radio: 0.001 m. Segmentos: 101.
- Fuente: conductor 1, segmento 51 (centro), 1 + j0 V.
- Entorno: espacio libre (`GE 0`, sin `GN`).

### Corte vertical en `phi=0°` (plano XZ, contiene el conductor)

| theta | PyNEC / 4nec2 |
|---:|---:|
| 0° | 2.12 dBi |
| 30° | 0.40 dBi |
| 60° | -5.34 dBi |
| 89° | -34.98 dBi |
| 90° | -999.99 |
| 91° | -34.98 dBi |
| 120° | -5.34 dBi |
| 150° | 0.40 dBi |
| 180° | 2.12 dBi |

PyNEC y 4nec2 coinciden en cada fila con la resolución de dos
decimales que muestra 4nec2.

- Valor teórico aproximado de un dipolo de media onda ideal:
  **2.15 dBi**.
- Resultado del modelo discretizado (PyNEC): **2.1233 dBi**
  aproximadamente.
- `-999.99` es el **valor centinela** de NEC2 para una ganancia nula o
  no representable (aquí, la dirección del propio eje del conductor);
  no es una ganancia física de -999.99 dBi.

El patrón es simétrico respecto de `theta=90°` (valores idénticos en
`theta` y `180° - theta`), como exige un conductor en espacio libre
contenido en el plano XY.

### Corte de azimut en `theta=90°` (plano XY)

| phi | Ganancia 4nec2 |
|---:|---:|
| 0° | -999.99 |
| 45° | -1.84 dBi |
| 90° | 2.12 dBi |
| 135° | -1.84 dBi |
| 180° | -999.99 |
| 225° | -1.84 dBi |
| 270° | 2.12 dBi |
| 315° | -1.84 dBi |
| 360° | -999.99 |

Para este corte, el informe experimental externo registra en PyNEC un
máximo de 2.1233 dBi en `phi=90°` y nulos exactos (`-999.99`)
únicamente en `phi=0°/180°/360°`.

Coincide con la simetría esperada de un dipolo orientado sobre X:
**nulos a lo largo de ±X** (`phi=0°/180°/360°`) y **máximos hacia ±Y**
(`phi=90°/270°`), con simetría respecto de ambos ejes. Este corte no
permite, por sí solo, distinguir +Y de -Y (ver sección 8).

## 6. Monopolo sobre tierra perfecta

### Modelo

- Conductor vertical de (0, 0, 0) a (0, 0, 5.03) m.
- Radio: 0.001 m. Segmentos: 38.
- Fuente: conductor 1, segmento 1 (base), 1 + j0 V.
- Entorno: tierra perfecta (`GE 1`, `GN 1 0 0 0 0 0 0 0`).
- Corte vertical en `phi=0°` (arbitrario por la simetría de
  revolución), `theta` de 0° a 90°.

### Tabla 4nec2

| theta | Ganancia |
|---:|---:|
| 0° | -999.99 |
| 1° | -31.97 dBi |
| 30° | -2.33 dBi |
| 60° | 3.41 dBi |
| 89° | 5.13 dBi |
| 90° | 5.13 dBi |

### Comparación con PyNEC

- Máximo observado en PyNEC: **5.1334 dBi** aproximadamente, en
  `theta=90°`.
- Máximo teórico aproximado de un monopolo cuarto de onda ideal sobre
  tierra perfecta: **5.15 dBi**.
- Máximo **en el horizonte** (`theta=90°`) en ambas herramientas.
- **Nulo sobre el eje vertical** (`theta=0°`, `-999.99`) en ambas
  herramientas.
- Mínimo finito en `theta=1°`:
  - PyNEC (informe experimental externo): -31.9684 dBi;
  - 4nec2: -31.97 dBi.
- Concordancia dentro del redondeo mostrado por 4nec2.

## 7. Dipolo sobre tierra real

### Modelo

- Geometría: dipolo horizontal elevado a 10 m, de (-5.03, 0, 10) a
  (5.03, 0, 10) m; radio 0.001 m; 101 segmentos; fuente en el
  segmento 51, 1 + j0 V (la misma geometría que
  `examples/dipole-20m-real-ground.yaas`).
- Entorno:
  - Sommerfeld-Norton (`GE 1`, `GN 2 0 0 0 13 0.005 0 0 0 0`);
  - permitividad relativa: 13.0;
  - conductividad: 0.005 S/m.
- Corte vertical en `phi=0°`, `theta` de 0° a 90°; corte de azimut en
  `theta=90°`.

### Tabla 4nec2 (corte vertical, `phi=0°`)

| theta | Ganancia |
|---:|---:|
| 0° | -4.96 dBi |
| 1° | -4.95 dBi |
| 30° | -1.08 dBi |
| 43° | 0.09 dBi |
| 60° | -2.80 dBi |
| 89° | -29.51 dBi |
| 90° | -999.99 |

### Comparación con PyNEC

- Máximo en PyNEC: **0.0944 dBi**, en `theta=43°`; 4nec2 muestra
  0.09 dBi en el mismo ángulo.
- Mínimo finito registrado en `theta=89°`:
  - PyNEC (informe experimental externo): -29.5103 dBi;
  - 4nec2: -29.51 dBi.
- **Nulo exacto en el horizonte**, `theta=90°` (`-999.99`), en ambas
  herramientas.
- En el corte de azimut en `theta=90°`, **los 361 valores de `phi`
  fueron `-999.99`**: el nulo en el horizonte no depende de la
  dirección azimutal para este modelo.

### Alcance del nulo en el horizonte

Ese nulo exacto en `theta=90°` fue observado **para este modelo
Sommerfeld-Norton específico** (dipolo horizontal a 10 m, permitividad
relativa 13.0, conductividad 0.005 S/m) y **no debe generalizarse
todavía a todas las geometrías sobre tierra real**. La investigación
lo interpreta como consistente con un nulo conocido en incidencia
rasante (el ángulo del horizonte) sobre tierra real, pero esa
interpretación no se confirmó con una fuente primaria dedicada, y no
se probaron otras alturas, orientaciones ni parámetros de suelo
(`docs/research/nec-radiation-patterns.md`, §2.3 y §6, punto 8).

## 8. Array asimétrico y sentido de `phi`

### Modelo

- Dos elementos:
  - **Elemento 1** en y=+2.6483 m, fase 0°, excitación **1 + j0**.
  - **Elemento 2** en y=-2.6483 m, fase +90°, excitación **0 + j1**.
- Entorno: espacio libre (`GE 0`).

Geometría adicional, tomada de las tarjetas `GW`/`EX` del archivo
experimental externo `phased-array-phi-direction.nec` (sección 13):

- ambos elementos son dipolos verticales (paralelos a Z), de
  z=-5.03 m a z=5.03 m, en x=0, con radio 0.001 m;
- ambos tienen 101 segmentos (`GW 1 101 ...` y `GW 2 101 ...`), con
  la fuente en el segmento 51 (centro) de cada uno;
- separación total entre elementos, a lo largo del eje Y: 5.2967 m,
  aproximadamente lambda/4 a 14.15 MHz.
- Corte de azimut en `theta=90°`. En ese plano cada dipolo vertical
  está en su propio máximo, de modo que la dependencia de `phi`
  proviene casi por completo del factor de array.

El modelo es deliberadamente asimétrico respecto de +Y/-Y: a
diferencia del dipolo de la sección 5, su patrón distingue ambas
direcciones.

### Tabla 4nec2 (`theta=90°`)

| phi | Ganancia |
|---:|---:|
| 0° | -4.19 dBi |
| 45° | 5.06 dBi |
| 90° | 6.63 dBi |
| 135° | 5.06 dBi |
| 180° | -4.19 dBi |
| 225° | -1.51 dBi |
| 270° | 2.60 dBi |
| 315° | -1.51 dBi |
| 360° | -4.19 dBi |

### Comparación con PyNEC

- Máximo PyNEC: **6.6311 dBi** aproximadamente, en `phi=90°`.
- Máximo 4nec2: **6.63 dBi**, en `phi=90°`.
- Mínimo PyNEC (informe experimental externo): **-12.4232 dBi**
  aproximadamente. El informe registra expresamente su ángulo:
  `theta=90°`, `phi=343°`.
- Mínimo 4nec2: **-12.44 dBi**; `phi=343°` es el ángulo informado para
  el mínimo de 4nec2.
- La inspección manual del patrón en la visualización de 4nec2
  confirmó que **el lóbulo máximo apunta físicamente hacia +Y**.

La tabla es simétrica respecto de `phi=90°`/`phi=270°` (por ejemplo,
45° y 135° coinciden), como corresponde a un array cuyo eje de
separación es Y, y es claramente asimétrica entre `phi=90°` (6.63 dBi)
y `phi=270°` (2.60 dBi).

Interpretación: la diferencia de ~0.02 dB en el mínimo es coherente
con que, cerca de un mínimo profundo, diferencias numéricas pequeñas
entre dos implementaciones de NEC2 se reflejan con más peso en dB que
cerca del máximo; no se investigó su origen. No afecta ninguna
conclusión de este documento.

### Conclusión

Esto **resuelve experimentalmente el sentido de `phi`**
(`phi=90°` = +Y, antihorario visto desde +Z). El razonamiento completo,
y la distinción entre esta convención geométrica y la convención
fasorial, que sigue sin demostrar, están en la sección 3.

## 9. Estructura de arrays de PyNEC

Confirmado por la investigación
(`docs/research/nec-radiation-patterns.md`, §1.2) y coherente con
todos los cortes de esta validación:

- `get_gain()` devuelve una matriz 2D con shape **`(n_theta, n_phi)`**:
  - el **primer índice** corresponde a `theta`;
  - el **segundo índice** corresponde a `phi`.

  Shapes registradas por PyNEC en el informe experimental externo para
  los seis cortes de esta validación: `(1, 361)` para los tres cortes
  de azimut, `(181, 1)` para el corte vertical en espacio libre y
  `(91, 1)` para los dos cortes verticales con plano de tierra.
- En los arrays **planos** (`get_gain_tot()` y equivalentes), `theta`
  **varía más rápido** que `phi` (orden columna-mayor):
  `indice_plano = phi_idx * n_theta + theta_idx`.
- La investigación lo verificó con una **grilla no cuadrada de 19×37**
  (`n_theta=19`, `n_phi=37`), para que ambos ejes no pudieran
  confundirse: `get_gain().shape == (19, 37)`, y `get_gain_tot()`
  reordenado con `order='F'` coincidió elemento a elemento con
  `get_gain()`.
- La futura implementación debería **consumir preferentemente
  `get_gain()`** en lugar de reconstruir manualmente la matriz desde
  `get_gain_tot()`.

## 10. Resumen PyNEC frente a 4nec2

| Modelo | Magnitud | PyNEC | 4nec2 |
|---|---|---:|---:|
| Dipolo en espacio libre | máximo | 2.1233 dBi | 2.12 dBi |
| Monopolo sobre tierra perfecta | máximo (`theta=90°`) | 5.1334 dBi | 5.13 dBi |
| Dipolo sobre tierra real | máximo (`theta=43°`) | 0.0944 dBi | 0.09 dBi |
| Array asimétrico | máximo (`phi=90°`) | 6.6311 dBi | 6.63 dBi |
| Array asimétrico | mínimo (`phi=343°` en ambos) | -12.4232 dBi | -12.44 dBi |

Cada valor se expresa con la precisión que informa la herramienta
correspondiente: PyNEC, con cuatro decimales, según el informe
experimental externo; 4nec2, con los dos decimales que muestra. No se
afirma más precisión que esa para la comparación. Los máximos
coinciden dentro del redondeo de 4nec2; el mínimo del array difiere
en ~0.02 dB
(sección 8). Todos los nulos exactos (`-999.99`) aparecen en las
mismas direcciones en ambas herramientas.

## 11. Decisiones para la futura implementación

Registradas como requisitos; **nada de esto se implementa en esta
tarea**:

- **Validar conteos angulares positivos** (`n_theta > 0`, `n_phi > 0`)
  en el dominio, antes de llamar a PyNEC: conteos negativos provocan
  un `segmentation fault` del proceso
  (`docs/research/nec-radiation-patterns.md`, §1.6).
- **Validar el rango de `theta` según el entorno**, también antes de
  llamar a PyNEC (dominio angular seguro):
  - espacio libre: `0° <= theta <= 180°`;
  - cualquier plano de tierra (perfecta o real): `0° <= theta <= 90°`.

  Con tierra, `theta > 90°` produjo en PyNEC valores subnormales no
  reproducibles entre llamadas idénticas. La evidencia es compatible
  con lectura de estado nativo no inicializado, pero **la causa interna
  no fue confirmada**. Todos los cortes con tierra de esta validación
  se detuvieron en `theta=90°` inclusive, dentro de ese dominio.
- **Crear un contexto NEC2++ independiente por frecuencia para tierra
  real**, igual que ya hace `PyNecEngine` para impedancia
  (`docs/research/nec-radiation-patterns.md`, §2.3).
- **Representar `-999.99` como un nulo/centinela claramente
  identificado**, no como una ganancia física ordinaria (por ejemplo,
  no promediarlo, no graficarlo como -999.99 dB, no usarlo como mínimo
  "real" del patrón).
- **Usar la convención angular confirmada** (sección 3): `theta` desde
  +Z; `phi` desde +X, antihorario visto desde +Z.
- **Preservar el orden `(theta, phi)` de la matriz** devuelta por
  `get_gain()` (sección 9), sin reordenar implícitamente.
- **No definir orientación geográfica** (Norte/Sur/Este/Oeste): los
  ejes son cartesianos +X/+Y; cualquier mapeo geográfico sería una
  decisión posterior, explícita y separada.

## 12. Limitaciones

- Patrones validados **solamente a una frecuencia por modelo**
  (14.15 MHz); no se validaron barridos de patrón en frecuencia.
- Solo cortes principales (un corte vertical y/o uno de azimut por
  modelo); no se comparó una grilla 3D completa contra 4nec2.
- No se validaron **polarizaciones circular/elíptica** (LHCP/RHCP,
  relación axial, inclinación, sentido).
- No se validaron las componentes **`E_theta`/`E_phi`** como API
  pública.
- No se validaron **normalizaciones alternativas** (`N != 0`); la
  forma de recuperar ganancia normalizada desde PyNEC sigue siendo una
  pregunta abierta de la investigación.
- Solo ganancia de potencia (`D=0`) de conductores sin pérdidas; no se
  validaron cargas ni conductividad finita de conductores.
- No se verificó todavía una **amplia variedad de geometrías sobre
  tierra real**: solo el dipolo horizontal a 10 m con un único par de
  parámetros de suelo; en particular, el nulo exacto en el horizonte
  no se generaliza.
- No se determinó la **causa nativa de los valores inválidos con
  `theta > 90°` y tierra**.
- La convención temporal/fasorial interna (`e^{jωt}` o `e^{-jωt}`)
  con la que NEC2 interpreta una excitación compleja de +90° no se
  demostró ni se contrastó con una fuente primaria; esta validación
  solo confirma la convención geométrica de `phi` (sección 3).
- No se validó el orden textual de tarjetas más allá de los seis
  archivos usados (sección 4).
- No se diseñó ni implementó todavía la **API pública de YAAS** para
  patrones de radiación.

## 13. Reproducibilidad

Archivos `.nec` externos utilizados (generados y ejecutados **fuera
del repositorio**; no forman parte de YAAS, igual que sus CSV, el
script generador y el informe asociado):

- `dipole-free-space-azimuth.nec`
- `dipole-free-space-vertical.nec`
- `monopole-perfect-ground-vertical.nec`
- `dipole-real-ground-azimuth.nec`
- `dipole-real-ground-vertical.nec`
- `phased-array-phi-direction.nec`

Para reproducir la comparación sin esos archivos, las geometrías de
las secciones 5-8, las tarjetas `GE`/`GN` indicadas en cada una, la
fuente (`EX 0 <tag> <segmento> 0 <real> <imag>`), la frecuencia
(`FR 0 1 0 0 14.15 0`) y las tarjetas `RP` de la sección 4, en el
orden textual de esa misma sección, son suficientes para reconstruir
cada modelo en 4nec2 o en cualquier herramienta NEC2 compatible:

1. Abrir el archivo `.nec` en 4nec2 V5.9.3 (**File -> Open**).
2. Calcular el patrón de campo lejano indicado por la tarjeta `RP`.
3. Leer la ganancia total en dBi en los ángulos de las tablas de las
   secciones 5-8.
4. Para el array asimétrico, inspeccionar además la visualización del
   patrón junto con la geometría, para confirmar hacia qué semieje
   (+Y o -Y) apunta el lóbulo máximo.
