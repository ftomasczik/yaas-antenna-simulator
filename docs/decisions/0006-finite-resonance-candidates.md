# ADR 0006: Candidatos finitos para resonancia aproximada

- Estado: Aceptada
- Fecha: 2026-09-25

`SweepResult.resonance_point` y `MeasurementSweep.resonance_point` sólo
consideran puntos cuya resistencia y reactancia sean ambas finitas.
Se excluyen infinitos y NaN. Entre los candidatos se selecciona el de
menor reactancia absoluta; en un empate se conserva el primero.

Un abierto representado como `inf + j0` no es candidato. Un punto finito
con reactancia cero sí lo es. La estimación sigue siendo muestreada y
no garantiza que exista un cruce de reactancia por cero.

Cuando no hay candidatos, la propiedad devuelve `None`. Los consumidores
deben comprobarlo antes de acceder a sus campos. La CLI informa que la
resonancia no está disponible porque no hay impedancias finitas, en el
idioma seleccionado, y conserva el resto del informe y el código de
éxito: la ausencia de una estimación no invalida por sí sola el archivo.

Esta decisión no cambia la ROE mínima, el diagnóstico de cruce por cero,
el formato `.antsim` ni el contrato de comparación del ADR 0005.
