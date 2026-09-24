# Fase 4 — Importación Touchstone S1P

## Estado

Completada.

## Objetivo

Importar barridos S11 provenientes de NanoVNA y otras herramientas
compatibles con Touchstone.

## Capacidades implementadas

- Lectura de archivos `.s1p`.
- Formatos `RI`, `MA` y `DB`.
- Unidades Hz, kHz, MHz y GHz.
- Impedancia de referencia configurable.
- Comentarios completos y comentarios al final de línea.
- Lectura de UTF-8 con o sin BOM.
- Conversión de S11 a impedancia compleja.
- Cálculo de ROE.
- Detección de resonancia aproximada.
- Detección de ROE mínima.
- Detección de cruce de reactancia por cero.
- Advertencia de mínimos ubicados en extremos del barrido.
- Comando `antsim inspect-s1p`.
- Mensajes en español e inglés.
- Compatibilidad con el ejecutable Windows.

## Modelos incorporados

- `MeasurementPoint`
- `MeasurementSweep`

## Validaciones

El importador rechaza:

- Encabezados inválidos.
- Parámetros distintos de S.
- Formatos no compatibles.
- Unidades desconocidas.
- Valores no numéricos o no finitos.
- Frecuencias no crecientes.
- Barridos sin puntos.
- Múltiples encabezados.

## Limitaciones

- Solo se admiten archivos de un puerto.
- No se importan parámetros S multipuerto.
- No se interpolan frecuencias.
- No se comparan todavía mediciones con simulaciones.
- La resonancia se aproxima usando el punto de menor reactancia
  absoluta.

## Resultado

AntSim puede inspeccionar mediciones S11 y convertirlas al mismo tipo
de magnitudes eléctricas utilizadas por el simulador: frecuencia,
impedancia y ROE.

Esto establece la base para comparar resultados de PyNEC con
mediciones reales.