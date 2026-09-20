# ADR 0002: Usar NEC2++ mediante PyNEC

- Estado: Aceptada
- Fecha: 2026-09-20

## Contexto

El simulador necesita resolver modelos electromagnéticos de antenas
construidas mediante conductores segmentados.

Desarrollar un solver propio implicaría implementar, verificar y
mantener componentes matemáticos complejos relacionados con el método
de los momentos.

Ese esfuerzo no forma parte del objetivo inicial del proyecto, cuyo
foco principal es ofrecer una interfaz moderna, una arquitectura clara
y herramientas para comparar simulaciones con mediciones reales.

## Decisión

Se utilizará NEC2++ como motor electromagnético mediante la interfaz
Python PyNEC.

El núcleo de NEC2++ se utilizará sin modificaciones.

La aplicación no accederá directamente a PyNEC desde la GUI, la CLI ni
los formatos de archivo. El acceso se realizará mediante un adaptador
propio denominado `PyNecEngine`.

La versión inicialmente validada pertenece a la serie PyNEC 2.3.

## Motivos

NEC2++ proporciona:

- Un motor basado en NEC2.
- Modelado de estructuras formadas por conductores.
- Cálculo de impedancia.
- Barridos de frecuencia.
- Patrones de radiación.
- Diferentes modelos de tierra.
- Una base conocida dentro del ámbito de antenas.

PyNEC permite utilizar NEC2++ desde Python sin crear inicialmente una
interfaz propia en C++.

## Alternativas consideradas

### Implementar un solver propio

Rechazada para las primeras versiones debido a su complejidad,
necesidad de validación científica y elevado costo de mantenimiento.

### Integrar directamente la API C de `necpp`

Posible, pero no seleccionada inicialmente porque PyNEC ofrece una
interfaz de más alto nivel y más cómoda para Python.

### Ejecutar otro simulador como proceso externo

No seleccionado como motor principal porque agregaría dependencias
externas y complicaría la distribución. Podría incorporarse en el
futuro mediante otro adaptador.

## Consecuencias

### Positivas

- Se reutiliza un motor existente.
- El proyecto puede concentrarse en la experiencia de usuario.
- Es posible validar resultados contra otros programas NEC.
- Se mantiene abierta la posibilidad de incorporar otros motores.

### Negativas

- PyNEC contiene código nativo.
- El empaquetado para Windows necesita incluir PyNEC y NumPy.
- Las limitaciones inherentes a NEC2 también afectarán al simulador.
- Deben respetarse las condiciones de licencia del motor.

## Validación

Se realizó una simulación en Windows de un dipolo en espacio libre:

- Frecuencia: 14,150 MHz.
- Longitud total: 10,060 m.
- Segmentos: 101.
- Impedancia: 67,43 − j31,25 ohm.
- ROE respecto de 50 ohm: 1,83.

La misma simulación se ejecutó correctamente desde:

- Un script Python.
- `PyNecEngine`.
- La CLI.
- Un ejecutable generado mediante PyInstaller.