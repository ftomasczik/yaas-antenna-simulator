# Fase 3 — Exportación NEC

## Estado

Completada.

## Objetivo

Permitir que los modelos creados en AntSim puedan utilizarse en
programas compatibles con NEC, sin acoplar el dominio interno a un programa externo específico.

## Capacidades implementadas

- Conversión de `SimulationRequest` a tarjetas NEC.
- Conversión de `SweepRequest` a tarjetas NEC.
- Exportación de frecuencia única.
- Exportación de barrido lineal.
- Comando `antsim export-nec`.
- Opción `antsim export-nec --sweep`.
- Mensajes en español e inglés.
- Soporte dentro del ejecutable Windows.
- Pruebas unitarias, de CLI y de construcción.

## Tarjetas generadas

- `CM`: comentario.
- `CE`: fin de comentarios.
- `GW`: conductor recto.
- `GE 0`: fin de geometría en espacio libre.
- `EX 0`: fuente de tensión.
- `FR`: frecuencia única o barrido lineal.
- `EN`: fin del archivo.

## Interoperabilidad

La exportación de frecuencia única fue validada con 4nec2 5.9.3.

A 14.150 MHz:

| Motor | Impedancia | ROE |
|---|---:|---:|
| AntSim / PyNEC | 67.43 - j31.25 ohm | 1.83 |
| 4nec2 | 67.4 - j31.3 ohm | 1.84 |

El archivo fue abierto y calculado en 4nec2 sin modificaciones.

## Limitaciones

- No se importan archivos NEC.
- Solo se exportan conductores rectos.
- Se exporta una única fuente de tensión.
- El entorno es espacio libre.
- No se generan tarjetas de suelo, cargas o patrón de radiación.
- Los comentarios se limitan a una línea.
- La impedancia de referencia no forma parte del archivo NEC.

## Resultado

AntSim puede intercambiar sus modelos actuales con herramientas NEC externas mediante archivos de texto estándar.

La exportación permanece separada del motor PyNEC y utiliza solamente los modelos públicos del dominio.
