# Validación de exportación NEC con 4nec2

Fecha: 2026-09-24

## Objetivo

Comprobar que un archivo `.nec` generado por AntSim puede abrirse y calcularse correctamente en una implementación externa.

## Herramientas

- AntSim 0.0.1
- PyNEC / NEC2++
- 4nec2 5.9.3
- Windows x64

## Modelo

Dipolo recto en espacio libre:

- Frecuencia: 14.150 MHz
- Longitud total: 10.06 m
- Radio del conductor: 0.001 m
- Segmentos: 101
- Fuente: conductor 1, segmento 51
- Impedancia de referencia: 50 ohm

## Resultados

| Magnitud | AntSim/PyNEC | 4nec2 |
|---|---:|---:|
| Impedancia | 67.43 - j31.25 ohm | 67.4 - j31.3 ohm |
| ROE | 1.83 | 1.84 |
| Segmentos | 101 | 101 |

## Diferencias

- Resistencia: 0.03 ohm.
- Reactancia: 0.05 ohm.
- ROE: 0.01.

Las diferencias observadas corresponden al redondeo presentado por las interfaces y no representan una diferencia significativa de cálculo.

## Tarjetas verificadas

- `CM`: comentario.
- `CE`: fin de comentarios.
- `GW`: conductor recto.
- `GE 0`: fin de geometría en espacio libre.
- `EX 0`: fuente de tensión.
- `FR`: frecuencia.
- `EN`: fin del archivo.

## Conclusión

4nec2 abrió y calculó el archivo generado por AntSim sin requerir modificaciones.

La impedancia y la ROE coinciden con los resultados obtenidos mediante PyNEC. La exportación NEC de frecuencia única queda validada para el subconjunto de tarjetas actualmente soportado.
