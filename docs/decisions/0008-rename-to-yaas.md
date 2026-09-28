# ADR 0008: Renombrar el proyecto de AntSim a YAAS

- Estado: Aceptada
- Fecha: 2026-09-27

## Contexto

El proyecto se venía desarrollando bajo el nombre **AntSim**, elegido
al comienzo sin una revisión detenida de otros usos del nombre.
Durante la preparación de la primera publicación externa se
identificaron dos problemas prácticos con ese nombre:

- **"AntSim" es ambiguo**: en una búsqueda rápida se confunde con
  facilidad con simuladores de colonias de hormigas ("ant
  simulator"), que son mucho más numerosos y populares que cualquier
  herramienta de electromagnetismo.
- **"AntennaSim" (y variantes muy similares) ya identifican otros
  simuladores basados en NEC2** existentes en la comunidad de
  radioaficionados, lo que agrava la posibilidad de confusión con un
  nombre tan cercano como "AntSim".

En el momento de tomar esta decisión, el proyecto **todavía no tenía
repositorio remoto, ningún paquete publicado en un índice como PyPI,
ni usuarios externos conocidos**. No existía ningún compromiso con el
nombre "AntSim" fuera de este propio repositorio local. Por eso este
era el momento correcto para hacer un cambio completo de identidad:
después de la primera publicación pública, un cambio de nombre habría
sido mucho más costoso (enlaces rotos, paquetes duplicados en índices
públicos, usuarios con proyectos `.antsim` ya guardados, etc.).

## Decisión

Renombrar el proyecto por completo, de punta a punta, a:

- **Marca**: YAAS
- **Nombre completo**: Yet Another Antenna Simulator
- **Distribución Python**: `yet-another-antenna-simulator`
- **Módulo importable**: `yaas`
- **Comando CLI**: `yaas`
- **Ejecutable**: `yaas.exe`
- **Dominio gettext**: `yaas`
- **Variable de entorno**: `YAAS_LANGUAGE`
- **Extensión de proyecto**: `.yaas`
- **Repositorio futuro**: `yaas-antenna-simulator`

No se mantienen alias `antsim` ni compatibilidad con la extensión
`.antsim`: como se explicó en la sección anterior, el cambio ocurre
**antes** de la primera publicación externa, así que no hay ningún
usuario, paquete publicado ni enlace externo que preservar. Mantener
un alias habría sido complejidad permanente para un problema que, en
este momento, no existe.

`schema_version` (1, 2 y 3) **no cambia** con este renombre: el
contrato interno de los esquemas `.yaas` sigue siendo exactamente el
mismo que ya tenían los archivos `.antsim` (los mismos campos, las
mismas reglas de migración, los mismos `kind` de `environment`). La
extensión de archivo y la marca del producto son independientes del
contenido y el significado del formato JSON que contienen.

## Consecuencias

### Positivas

- Un nombre más distintivo y con menos colisiones directas conocidas
  en el espacio de simuladores de antenas y NEC2.
- Identidad técnica coherente de punta a punta (distribución, módulo,
  CLI, ejecutable, traducciones, extensión) desde la primera
  publicación, en vez de arrastrar un nombre elegido apresuradamente.
- Al hacerse antes de cualquier publicación, el costo del cambio fue
  puramente interno (código, pruebas, documentación viva), sin
  necesidad de gestionar compatibilidad hacia atrás con usuarios
  reales.

### Negativas

- Todo el trabajo de las fases 1 a 7B (commits, documentos de fase,
  investigaciones, validaciones, notas de las versiones 0.1.0, 0.1.1
  y 0.2.0) quedó registrado bajo el nombre anterior, AntSim. Ese
  historial no se reescribe (ver "Compatibilidad").
- Cualquier referencia futura a esos documentos necesita el
  recordatorio de que describen un momento en el que el proyecto se
  llamaba distinto, lo que agrega una pequeña carga de contexto para
  quien los lea por primera vez.

## Compatibilidad

- Los tres proyectos de ejemplo históricos de esquema (v1, v2 y v3)
  ahora usan la extensión `.yaas` (`examples/dipole-20m.yaas`,
  `examples/monopole-20m-perfect-ground.yaas`,
  `examples/dipole-20m-real-ground.yaas`), con su contenido JSON
  preservado byte a byte respecto de sus versiones `.antsim`
  anteriores.
- El significado de los esquemas 1, 2 y 3 **no se reescribe**: siguen
  siendo exactamente las mismas reglas de migración y los mismos
  `kind` de entorno ya documentados antes de este cambio.
- Los documentos y tags anteriores a este cambio (`v0.1.0`, `v0.1.1`,
  `v0.2.0`, y el propio historial de commits de las fases 1-7B) pueden
  conservar "AntSim" como nombre histórico sin modificarse: describen
  con precisión lo que existía en ese momento.

## Estado del tag `v0.3.0`

El tag anotado local `v0.3.0` todavía apunta, en este momento, al
commit de la preparación de la versión 0.3.0 **previa** a este cambio
de nombre. Este ADR no afirma que el tag ya haya sido movido: será
recreado localmente sobre el commit final de la preparación de YAAS
0.3.0, una vez que la identidad técnica quede completamente
actualizada, y antes de que esa versión se publique externamente.

## Alternativas consideradas

- **Conservar "AntSim"**: descartada por la ambigüedad y las
  colisiones de nombre ya descritas en el contexto, aprovechando que
  todavía no había ningún costo externo por cambiarlo.
- **"JAAS"**: descartada de inmediato por la colisión evidente con
  *Java Authentication and Authorization Service*, una tecnología
  ampliamente conocida y completamente ajena a este proyecto.
- **Nombres en mapuzugun**: se consideraron nombres en esa lengua
  como alternativa con identidad propia, pero se descartaron por
  colisiones con otros usos ya existentes de esos términos o por
  dificultad práctica de pronunciación/escritura para la mayoría de
  los usuarios previstos (radioaficionados hispanohablantes y
  angloparlantes). Esta evaluación fue informal, no una búsqueda
  lingüística ni legal exhaustiva.
- **Cambiar solo la marca visible, sin tocar módulo/CLI/extensión**:
  descartada porque habría dejado una incoherencia interna permanente
  (un producto "YAAS" ejecutándose como `antsim`, guardando archivos
  `.antsim`), sin ningún beneficio real dado que no había compatibilidad
  externa que proteger.

## Nota

Este documento registra una decisión de identidad y nomenclatura del
proyecto. No es una búsqueda de marcas registradas ni un análisis
legal exhaustivo de disponibilidad del nombre "YAAS"; si el proyecto
avanza hacia una publicación con intención comercial, esa revisión
debería hacerse por separado, con asesoramiento apropiado.
