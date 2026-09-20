# ADR 0003: Separar el dominio del motor de simulación

- Estado: Aceptada
- Fecha: 2026-09-20

## Contexto

El proyecto tendrá varias formas de entrada y salida:

- Interfaz gráfica.
- Interfaz de línea de comandos.
- Archivos internos del proyecto.
- Archivos NEC.
- Mediciones NanoVNA.
- Archivos Touchstone.
- Posibles integraciones futuras.

Si estos componentes acceden directamente a PyNEC, la lógica del
programa quedaría acoplada al motor y sería difícil de probar,
reutilizar o sustituir.

## Decisión

Se mantendrá un modelo interno independiente de PyNEC.

Los conceptos fundamentales se definirán en `antsim.domain`.

El dominio incluirá inicialmente:

- `Point3D`.
- `Wire`.
- `VoltageSource`.
- `SimulationRequest`.
- `SimulationResult`.
- Cálculos independientes como la ROE.

Los motores implementarán el contrato `SimulationEngine`.

La primera implementación concreta será `PyNecEngine`.

La GUI y la CLI utilizarán el modelo interno y los servicios de la
aplicación. No llamarán directamente a PyNEC.

## Flujo

    Entrada
       |
       v
    Modelo interno
       |
       v
    SimulationEngine
       |
       v
    PyNecEngine
       |
       v
    PyNEC / NEC2++
       |
       v
    SimulationResult
       |
       +--> CLI
       +--> GUI
       +--> Exportadores
       +--> Comparaciones con NanoVNA

## Formatos de archivo

Los formatos no serán el modelo interno de la aplicación.

Cada formato tendrá sus propios importadores y exportadores:

- `NecImporter` y `NecExporter` para archivos `.nec`.
- Importadores para CSV y Touchstone `.s1p`.
- Serialización del formato interno `.antsim`.

La lectura de un archivo producirá objetos del dominio. La escritura
convertirá esos objetos al formato correspondiente.

## Motivos

Esta separación permite:

- Compartir lógica entre GUI y CLI.
- Probar el dominio sin ejecutar NEC2++.
- Probar el adaptador NEC independientemente.
- Incorporar otros motores en el futuro.
- Comparar simulaciones con mediciones.
- Evitar que el formato `.nec` limite el diseño interno.

## Consecuencias

### Positivas

- Menor acoplamiento.
- Pruebas más claras.
- Reutilización de la lógica.
- Sustitución posible del motor.
- Evolución independiente de la interfaz.
- Importación y exportación desacopladas.

### Negativas

- Se necesita código de conversión.
- Existen más módulos y clases.
- Algunas funciones de PyNEC deberán normalizarse.
- El modelo interno deberá evolucionar cuidadosamente.

## Validación

Se implementó `PyNecEngine`, que recibe un `SimulationRequest` y
devuelve un `SimulationResult`.

La prueba de integración verifica el flujo completo sin que el test
importe o manipule directamente objetos internos de PyNEC.