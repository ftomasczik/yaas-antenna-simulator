# ADR 0001: Usar Python 3.13

- Estado: Aceptada
- Fecha: 2026-09-20

## Contexto

El proyecto necesita una base que permita desarrollar:

- Una interfaz gráfica de escritorio.
- Una interfaz de línea de comandos.
- Integración con NEC2++.
- Procesamiento numérico.
- Importación de mediciones de NanoVNA.
- Gráficos bidimensionales y tridimensionales.
- Distribución como aplicación para Windows.

También se busca reducir la complejidad inicial y evitar el desarrollo
prematuro de componentes propios en C++.

## Decisión

Se utilizará Python 3.13 de 64 bits como lenguaje y entorno principal.

La versión inicialmente validada es Python 3.13.15.

El proyecto declarará temporalmente el siguiente rango:

    requires-python = ">=3.13,<3.14"

El rango podrá ampliarse a versiones posteriores cuando las pruebas
automáticas confirmen la compatibilidad de todas las dependencias.

Se utilizará un entorno virtual local llamado `.venv`.

La configuración del proyecto y sus dependencias se mantendrá en
`pyproject.toml`.

## Motivos

Python permite:

- Integrar PyNEC y NEC2++.
- Utilizar PySide6 para la futura interfaz gráfica.
- Procesar datos mediante NumPy.
- Crear gráficos con Matplotlib.
- Implementar una CLI sin duplicar la lógica.
- Ejecutar pruebas automáticas con pytest.
- Generar ejecutables mediante PyInstaller.

Python 3.13 ofrece un equilibrio entre soporte futuro y compatibilidad
con las bibliotecas seleccionadas.

## Consecuencias

### Positivas

- Desarrollo inicial más rápido.
- Menor cantidad de código nativo propio.
- Amplio ecosistema científico y gráfico.
- Código compartido entre GUI y CLI.
- Pruebas sencillas de automatizar.
- Posibilidad de distribuir un ejecutable para Windows.

### Negativas

- Algunas dependencias contienen extensiones nativas.
- PyNEC puede requerir compilación durante el desarrollo.
- El empaquetado necesita incluir Python y sus bibliotecas.
- El ejecutable generado será más grande que uno nativo mínimo.

## Validación

Se comprobó en Windows x64:

- Python 3.13.15.
- Creación de un entorno virtual.
- Instalación editable del proyecto.
- Ejecución de pruebas con pytest.
- Generación de un ejecutable mediante PyInstaller.