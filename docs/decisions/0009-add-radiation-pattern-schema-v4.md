# ADR 0009: Agregar patrones de radiación mediante el esquema `.yaas` v4

- Estado: Aceptada
- Fecha: 2026-09-29

## Contexto

El formato de proyecto `.yaas` evolucionó en versiones explícitas,
cada una con un contrato cerrado:

- **v1**: sin `simulation.environment`; el entorno es siempre espacio
  libre, de forma implícita.
- **v2**: `simulation.environment` pasa a ser obligatorio, con
  `free_space` o `perfect_ground`
  ([fase 7A](../phases/phase-7a-perfect-ground.md)).
- **v3**: agrega `real_ground` (Sommerfeld-Norton)
  ([fase 7B](../phases/phase-7b-real-ground.md)).

YAAS ya puede representar y calcular patrones de radiación, fuera
del formato de proyecto:

- el dominio define `AngularSweep`, `RadiationPatternRequest`,
  `RadiationPatternSample` y `RadiationPatternResult`, con la
  convención angular y el dominio seguro de `theta` confirmados en la
  [investigación](../research/nec-radiation-patterns.md) y en la
  [validación con 4nec2](../validation/radiation-patterns-4nec2.md);
- `PyNecEngine.simulate_radiation_pattern` calcula un patrón a una
  única frecuencia.

Para que un proyecto reproduzca un patrón hace falta persistir sus
ejes angulares, `theta` y `phi`. Agregar esa clave a v1, v2 o v3
alteraría retrospectivamente contratos históricos ya cerrados: un
archivo válido de esas versiones significaría algo distinto según qué
versión de YAAS lo leyera. Al mismo tiempo, el formato debe seguir
leyendo todos los archivos existentes y migrarlos de forma segura,
como ya se hizo en v2 y v3.

## Decisión

Crear el esquema versión 4:

- `CURRENT_SCHEMA_VERSION = 4`.
- `SUPPORTED_SCHEMA_VERSIONS = (1, 2, 3, 4)`.
- El lector conserva en memoria la versión original del archivo
  (`schema_version` 1, 2, 3 o 4).
- El escritor siempre emite `schema_version: 4`.
- `simulation.environment` sigue siendo obligatorio en v4, con los
  mismos tres entornos que v3.
- `simulation.radiation_pattern` es **opcional** en v4.
- v1, v2 y v3 **rechazan** `simulation.radiation_pattern`.
- Los proyectos históricos siguen cargando, sin patrón
  (`radiation_pattern is None`).
- Al guardarlos se migran a v4. La migración no es destructiva (no se
  pierde ningún dato) y no muta el objeto `AntennaProject` original.

Forma exacta, dentro de `simulation`:

```json
"radiation_pattern": {
  "theta": {
    "start_deg": 0.0,
    "count": 181,
    "step_deg": 1.0
  },
  "phi": {
    "start_deg": 0.0,
    "count": 1,
    "step_deg": 0.0
  }
}
```

Reglas del contrato:

- Los ángulos se expresan en grados.
- `count` es un entero JSON positivo (nunca `bool` ni un número con
  decimales); `start_deg` y `step_deg` son números JSON finitos.
- Cada eje contiene exactamente `start_deg`, `count` y `step_deg`, y
  el patrón contiene exactamente `theta` y `phi`: no se admiten claves
  faltantes ni adicionales.
- `stop_deg` es derivado (`start_deg + (count - 1) * step_deg`) y no
  se persiste.
- La frecuencia y el entorno se toman de `simulation`
  (`frequency_mhz` y `environment`); el patrón no tiene los suyos.
- Las reglas numéricas de cada eje las valida `AngularSweep`, y las
  que dependen del entorno (en particular `theta <= 90` con cualquier
  plano de tierra) `RadiationPatternRequest`. Ambas se aplican al
  cargar el archivo, no recién al simular.
- No se persisten opciones específicas de `rp_card()`, ni
  normalización, distancia radial o componentes de campo.
- No se usan nombres como `azimuth`/`elevation`: el contrato usa
  `theta`/`phi` cartesianos, con la convención ya validada (`theta`
  desde +Z; `phi` desde +X, antihorario visto desde +Z).

En el modelo de proyecto, esto se representa como
`RadiationPatternSettings(theta: AngularSweep, phi: AngularSweep)` y el
campo `AntennaProject.radiation_pattern` (`None` por defecto), que
`AntennaProject.to_radiation_pattern_request()` convierte en un
`RadiationPatternRequest`.

## Compatibilidad

| Versión | `environment` | Entornos admitidos | `radiation_pattern` | Al guardar |
|---|---|---|---|---|
| v1 | no admitido (espacio libre implícito) | — | rechazado | v4, `free_space`, sin patrón |
| v2 | obligatorio | `free_space`, `perfect_ground` | rechazado | v4, mismo entorno, sin patrón |
| v3 | obligatorio | `free_space`, `perfect_ground`, `real_ground` | rechazado | v4, mismo entorno, sin patrón |
| v4 | obligatorio | `free_space`, `perfect_ground`, `real_ground` | opcional | v4, sin cambios |

- Los tres ejemplos históricos (`examples/dipole-20m.yaas`,
  `examples/monopole-20m-perfect-ground.yaas` y
  `examples/dipole-20m-real-ground.yaas`) permanecen byte a byte sin
  modificar y siguen cargando como v1, v2 y v3 respectivamente.
- Guardar cualquiera de ellos produce un archivo v4.
- Una clave `radiation_pattern` en un archivo v1, v2 o v3 se rechaza
  con un error que menciona la versión, en vez de ignorarse en
  silencio. Antes de esta decisión, esa clave desconocida se ignoraba.
  Esto endurece la validación de entradas que ya eran inválidas para
  esas versiones, pero no rompe ningún archivo válido de v1, v2 o v3.

## Alternativas consideradas

1. **Extender v3 con `radiation_pattern` opcional.** Rechazada:
   cambiaría retrospectivamente el contrato de v3, y un archivo "v3"
   con patrón sería ilegible para herramientas que implementaron v3
   tal como se definió.
2. **Crear siempre un patrón por defecto.** Rechazada: no todos los
   proyectos necesitan calcular un patrón, y un valor por defecto
   inventado se confundiría con una configuración elegida.
3. **Guardar únicamente un tipo de corte** (por ejemplo, "vertical" o
   "azimut"). Rechazada: perdería la generalidad de una grilla
   `theta` × `phi` arbitraria, que ya admiten el dominio y el motor.
4. **Persistir todas las opciones de la tarjeta RP.** Pospuesta: la
   primera API solo necesita ganancia total sobre una grilla angular
   regular; normalización, distancia radial y polarización pueden
   agregarse cuando exista un caso de uso validado.
5. **Mantener el patrón fuera del archivo `.yaas`.** Rechazada:
   impediría reproducir completamente la simulación configurada a
   partir del proyecto.

## Consecuencias

### Positivas

- Reproducibilidad: el proyecto contiene todo lo necesario para
  recalcular el mismo patrón.
- Contrato explícito, con claves y tipos exactos.
- Migración segura y automática al guardar, sin mutar el original.
- Compatibilidad de lectura con todos los archivos históricos.
- Validación completa al cargar, antes de llegar a PyNEC (conteos
  angulares positivos y `theta <= 90` con tierra, dos condiciones que
  en PyNEC producen un fallo nativo o resultados no reproducibles).
- Base para una futura CLI y una futura GUI de patrones.

### Negativas

- Una nueva versión de esquema que mantener.
- Más validación y más pruebas en el lector y el escritor.
- Herramientas que solo entiendan hasta v3 no podrán leer archivos
  nuevos, aunque no declaren ningún patrón.
- El escritor migra a v4 aunque el proyecto no tenga
  `radiation_pattern`.
- Futuras opciones de patrón podrían exigir otro cambio compatible
  dentro de v4 (una clave opcional nueva) o una versión posterior.

## Alcance

Esta decisión cubre solo la persistencia y la conversión a
`RadiationPatternRequest`. No incorpora todavía:

- comandos de CLI para patrones;
- exportación NEC con tarjetas `RP`;
- exportación CSV de patrones;
- gráficos;
- GUI;
- barridos de patrón por frecuencia;
- polarización ni componentes `E_theta`/`E_phi`.

## Evidencia

- [`docs/research/nec-radiation-patterns.md`](../research/nec-radiation-patterns.md):
  API de PyNEC, orientación `(n_theta, n_phi)`, fallos nativos con
  conteos negativos y resultados no reproducibles con `theta > 90` y
  tierra.
- [`docs/validation/radiation-patterns-4nec2.md`](../validation/radiation-patterns-4nec2.md):
  convención angular, sentido de `phi` y concordancia con 4nec2.
- [`docs/phases/phase-7a-perfect-ground.md`](../phases/phase-7a-perfect-ground.md)
  y [`docs/phases/phase-7b-real-ground.md`](../phases/phase-7b-real-ground.md):
  precedentes de v2 y v3 (versión explícita en vez de extender un
  esquema existente, lectura compatible, migración al guardar).
- [ADR 0008](0008-rename-to-yaas.md): el cambio de nombre a YAAS no
  alteró el contrato de los esquemas 1, 2 y 3.
