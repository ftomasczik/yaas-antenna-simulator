# ADR 0004: Adoptar una licencia compatible con PyNEC

- Estado: Aceptada provisionalmente
- Fecha: 2026-09-20

## Contexto

El proyecto incorpora PyNEC y NEC2++ como componentes fundamentales
del motor de simulación.

PyNEC se distribuye actualmente en PyPI bajo la licencia
GPL-3.0-only.

La aplicación se distribuirá junto con PyNEC y con las bibliotecas
necesarias para ejecutar NEC2++.

Por lo tanto, la licencia del proyecto debe ser compatible con las
obligaciones de esos componentes.

## Decisión

El proyecto se desarrollará como software de código abierto.

La licencia propuesta para el código del simulador es:

    GNU General Public License v3.0 only

Antes de realizar la primera distribución pública se incorporarán:

- Un archivo `LICENSE`.
- Avisos de copyright.
- Referencias a las licencias de las dependencias.
- Instrucciones para obtener el código fuente correspondiente.
- Documentación del proceso de construcción.

La decisión se considera provisional hasta revisar nuevamente las
licencias de todas las dependencias incluidas en el primer instalador.

## Obligaciones previstas

Al distribuir la aplicación se deberá:

- Proporcionar el texto de la licencia.
- Mantener los avisos de copyright.
- Informar las modificaciones realizadas.
- Ofrecer el código fuente correspondiente.
- Proporcionar instrucciones reproducibles de compilación.
- No imponer restricciones incompatibles con la GPL.

## Dependencias futuras

Antes de incorporar una dependencia nueva se revisará:

- Su licencia.
- Su compatibilidad con GPL-3.0-only.
- Sus requisitos de atribución.
- Sus condiciones de redistribución.
- Si incluye bibliotecas nativas adicionales.

Esta revisión se aplicará especialmente a:

- PySide6 y Qt.
- Bibliotecas de gráficos.
- Lectores de Touchstone.
- Componentes para visualización 3D.
- Recursos gráficos, iconos y tipografías.

## Consecuencias

### Positivas

- Compatibilidad inicial con la licencia declarada por PyNEC.
- Transparencia para usuarios y colaboradores.
- Posibilidad de auditoría y mejora comunitaria.
- Coherencia con la preferencia por software abierto.

### Negativas

- La distribución debe cumplir las obligaciones de la GPL.
- Una distribución cerrada o propietaria requeriría revisar la
  arquitectura y las licencias.
- Las dependencias futuras deberán evaluarse antes de incorporarlas.

## Nota

Este documento registra una decisión técnica del proyecto y no
constituye asesoramiento jurídico.

La compatibilidad definitiva deberá revisarse antes de publicar una
versión distribuible o utilizar el programa con fines comerciales.