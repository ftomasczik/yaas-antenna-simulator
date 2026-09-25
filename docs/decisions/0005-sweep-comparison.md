# ADR 0005: Contrato inicial de comparación de barridos

- Estado: Aceptada
- Fecha: 2026-09-25

## Z₀ común

`compare_sweeps` exige `reference_impedance` como argumento nombrado,
resistivo, positivo y finito, sin valor por defecto. Convierte S11 usando
la referencia original de la medición y recalcula ambas ROE desde Z con
la referencia común. No utiliza la ROE almacenada en `SweepResult` ni
necesita inferir su referencia perdida. No modifica los barridos originales.

## Frecuencias

La grilla de salida es la de la medición restringida al rango simulado,
incluidos sus extremos. Las frecuencias se expresan en MHz. Una coincidencia
exacta usa la muestra simulada; en otro caso se interpolan linealmente R y X
entre puntos adyacentes. Se calcula ROE después de interpolar Z.

No se extrapola ni se aplica tolerancia implícita. Se informa la cantidad de
mediciones excluidas por rango. Si no queda ninguna muestra medida se lanza
`ValueError`, incluso si los intervalos se solapan entre muestras. Una sola
muestra común es válida. La grilla simulada debe ser positiva, finita y
estrictamente creciente; la medición ya exige esas propiedades en su modelo.

## Valores no finitos

La política inicial es estricta: se rechaza toda impedancia no finita de
entrada, incluso fuera del solapamiento, y toda impedancia interpolada,
ROE recalculada o diferencia no finita. No se descartan singularidades
silenciosamente ni se interpola a través de ellas. Un abierto o una ROE
infinita requieren un tratamiento futuro explícito antes de compararse.
La ROE previamente almacenada no se valida porque no es una entrada al cálculo.

## Salida y límites

Cada punto contiene frecuencia, ambas impedancias, ambas ROE y un indicador
de interpolación. Las diferencias son medición menos simulación. La salida
conserva Z₀ común y el número de muestras excluidas.

La interpolación no añade precisión física: barridos poco densos pueden
ocultar resonancias. Esta API no compara resonancias ni anchos de banda,
no corrige calibración/cables y no añade comandos de CLI. Los diagnósticos
previos de resonancia de los modelos permanecen fuera de este contrato.
