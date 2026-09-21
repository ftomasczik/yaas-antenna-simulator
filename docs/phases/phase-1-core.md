# Cierre de la Fase 1: núcleo básico de simulación

- Estado: Completada
- Fecha: 2026-09-21
- Versión del proyecto: 0.0.1
- Plataforma validada: Windows x64
- Python validado: 3.13.15

## Objetivo

El objetivo de la Fase 1 fue consolidar un núcleo de simulación
independiente de la interfaz gráfica, capaz de validar modelos,
ejecutar barridos de frecuencia, analizar sus resultados y exportarlos.

La GUI, la importación de mediciones y la interoperabilidad con
archivos NEC quedaron deliberadamente fuera de esta fase.

## Capacidades implementadas

### Modelo interno

El dominio permite representar:

- Puntos tridimensionales.
- Conductores rectos segmentados.
- Fuentes de tensión.
- Solicitudes de frecuencia única.
- Solicitudes de barrido lineal.
- Resultados de frecuencia única.
- Resultados multipunto.
- Intervalos de ancho de banda.

Los modelos internos no dependen directamente de PyNEC.

### Validación

Se incorporaron validaciones para detectar:

- Coordenadas no finitas.
- Conductores de longitud nula.
- Radios de conductor inválidos.
- Cantidades de segmentos inválidas.
- Frecuencias no positivas.
- Intervalos de frecuencia invertidos.
- Barridos con menos de dos puntos.
- Etiquetas de conductor repetidas.
- Fuentes asociadas a conductores inexistentes.
- Fuentes asociadas a segmentos inexistentes.
- Impedancias de referencia inválidas.
- Límites de ROE inválidos.

Estas validaciones se ejecutan antes de enviar datos a NEC2++.

### Motor de simulación

`PyNecEngine` implementa:

- Simulación de una frecuencia.
- Barrido lineal multipunto.
- Creación de geometrías con uno o más conductores.
- Excitación mediante una fuente de tensión.
- Simulación en espacio libre.
- Normalización de impedancias devueltas por PyNEC.
- Cálculo de ROE respecto de una impedancia de referencia.

Los barridos utilizan una única ejecución multipunto de NEC2++.

### Análisis de resultados

`SweepResult` permite obtener:

- Punto de resonancia aproximado.
- Punto de ROE mínima.
- Intervalo muestreado que cumple un límite de ROE.
- Frecuencia inferior del intervalo.
- Frecuencia superior del intervalo.
- Ancho de banda en MHz y kHz.
- Frecuencia central.
- Ancho de banda porcentual.

La resonancia se define como el punto cuya reactancia está más cerca de cero.

La ROE mínima se calcula independientemente de la resonancia.

### Interfaz de línea de comandos

La CLI ofrece:

    antsim --version
    antsim doctor
    antsim simulate-dipole
    antsim sweep-dipole

El comando de barrido admite:

    --start
    --stop
    --points
    --swr-limit
    --output

Ejemplo:

    antsim sweep-dipole \
        --start 13.5 \
        --stop 15.5 \
        --points 81 \
        --swr-limit 2 \
        --output resultados.csv

### Exportación CSV

Los barridos pueden exportarse con las columnas:

- `frequency_mhz`
- `resistance_ohm`
- `reactance_ohm`
- `impedance_magnitude_ohm`
- `swr`

El exportador es independiente de la CLI y podrá ser utilizado por la futura GUI.

### Pruebas automáticas

El proyecto cuenta con pruebas para:

- Metadatos del paquete.
- Cálculo de ROE.
- Validación del dominio.
- Modelos de barrido.
- Cálculo de ancho de banda.
- Exportación CSV.
- Comandos de la CLI.
- Simulación real mediante PyNEC.
- Barridos multipunto mediante NEC2++.

Al cierre de la fase se ejecutan 29 pruebas automáticas.

### Distribución para Windows

PyInstaller genera:

    dist\antsim.exe

El ejecutable incluye:

- Python.
- El paquete `antsim`.
- NumPy.
- PyNEC.
- NEC2++.
- La interfaz de línea de comandos.

El script `scripts/build_windows.ps1` verifica automáticamente:

1. Las pruebas.
2. La generación del ejecutable.
3. El diagnóstico del entorno.
4. La simulación de frecuencia única.
5. El barrido multipunto.
6. La generación de un CSV.
7. La cantidad esperada de filas exportadas.

El ejecutable fue probado sin el entorno virtual activo.

## Resultado de referencia

Para un dipolo de 10,06 m, radio de 1 mm y 101 segmentos, se obtuvo
en un barrido de 13,5 a 15,5 MHz con 81 puntos:

- Resolución: 25 kHz.
- Resonancia aproximada: 14,450 MHz.
- Impedancia en resonancia: 71,97 − j0,66 ohm.
- ROE en resonancia: 1,44.
- Frecuencia de ROE mínima: 14,425 MHz.
- Impedancia en la ROE mínima: 71,58 − j3,21 ohm.
- ROE mínima: 1,44.
- Intervalo muestreado con ROE menor o igual a 2:
  14,100 a 14,775 MHz.
- Ancho de banda muestreado: 675 kHz.
- Ancho de banda porcentual: 4,68 %.

## Limitaciones conocidas

### Modelo electromagnético

Actualmente sólo se configuró:

- Espacio libre.
- Conductores rectos.
- Una fuente de tensión.
- Una impedancia de referencia resistiva.
- Barridos lineales.

Todavía no se implementaron:

- Tierra perfecta o real.
- Radiales.
- Cargas.
- Redes de adaptación.
- Múltiples fuentes.
- Conductores curvos.
- Parches o superficies.
- Patrones de radiación.
- Campos cercanos.
- Corrientes por segmento.
- Ganancia y eficiencia.

### Resolución del barrido

La resonancia, la ROE mínima y los límites de ancho de banda se buscan entre los puntos calculados.

No existe todavía interpolación entre frecuencias consecutivas.

Por este motivo, la precisión depende de la cantidad y separación de los puntos del barrido.

### Ancho de banda

El intervalo de ROE se calcula alrededor de la ROE mínima.

La implementación actual no representa múltiples intervalos
independientes, como podrían aparecer en una antena multibanda.

Si todo el intervalo calculado cumple el límite, el programa todavía no informa que el ancho de banda podría extenderse fuera del barrido.

### Interfaz de línea de comandos

La CLI sólo simula un dipolo de referencia incorporado en el código.

Todavía no permite definir una geometría completa mediante parámetros o cargarla desde un archivo.

### Archivos e interoperabilidad

Todavía no se implementaron:

- Formato interno `.antsim`.
- Lectura de archivos `.nec`.
- Escritura de archivos `.nec`.
- Importación Touchstone `.s1p`.
- Importación CSV de NanoVNA.
- Comparación entre simulación y medición.

### Interfaz gráfica

No existe todavía una GUI.

PySide6, la visualización 2D/3D y los gráficos interactivos se
incorporarán en fases posteriores.

### Distribución

Se genera un ejecutable autónomo, pero todavía no existe:

- Instalador para Windows.
- Icono definitivo.
- Metadatos comerciales.
- Firma digital.
- Actualización automática.
- Compilación automática mediante integración continua.

## Decisiones que se mantienen

- Python continuará siendo el lenguaje principal.
- NEC2++ continuará utilizándose sin modificar su núcleo.
- PyNEC permanecerá aislado detrás de `PyNecEngine`.
- La CLI y la futura GUI compartirán el mismo dominio.
- Los formatos externos se convertirán al modelo interno.
- El proyecto mantendrá pruebas unitarias y de integración.
- La compatibilidad de licencias se revisará antes de la primera
  distribución pública.

## Conclusión

La Fase 1 demuestra que el núcleo puede representar, validar, simular, analizar y exportar un barrido básico de una antena.

La arquitectura está preparada para avanzar sin acoplar la futura GUI directamente a PyNEC.

La próxima fase deberá elegir entre dos líneas de trabajo:

1. Incorporar un formato de proyecto y geometrías configurables.
2. Crear una primera GUI que consuma las capacidades ya implementadas.

La opción recomendada es implementar primero el formato interno y una geometría configurable mínima, porque proporcionará una base estable tanto para la CLI como para la GUI.