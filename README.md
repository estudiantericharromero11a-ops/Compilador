# Luma: compilador educativo para ESP32

Luma es un lenguaje de instrucciones en español que se compila mediante etapas reales —lexer, parser con AST, análisis semántico y generador— a MicroPython y a un módulo de ensamblador GNU Xtensa LX6. La interfaz Tkinter edita y compila programas, detecta puertos serie y ejecuta el código MicroPython en un ESP32 mediante USB/Serial.

La versión actual también permite leer cuatro entradas digitales, calcular su valor binario y controlar un display de siete segmentos de cátodo común. La conexión HTTP/Wi‑Fi del ejemplo externo no forma parte del lenguaje ni se genera.

## Decisiones y arquitectura

- **MicroPython como destino inicial:** no requiere compilar un firmware Arduino; el programa generado se ejecuta en el Raw REPL de MicroPython. El firmware MicroPython debe estar instalado previamente en la placa.
- **Python 3.10+ y Tkinter:** el núcleo usa la biblioteca estándar; pyserial es la única dependencia externa y Tkinter suele venir con Python.
- `src/luma/lexer.py`: tokens, palabras clave, caracteres inválidos y ubicación.
- `src/luma/parser.py` y `ast.py`: gramática, errores de sintaxis y árbol.
- `src/luma/semantic.py`: rangos de GPIO, duración y repeticiones.
- `src/luma/codegen.py`: traducción independiente del transporte a MicroPython.
- `src/luma/assembly_codegen.py`: backend de ensamblador Xtensa LX6 con llamadas a rutinas de hardware externas.
- `src/luma/transport.py`: enumeración de puertos y protocolo MicroPython Raw REPL.
- `src/luma/gui.py`: editor con resaltado, archivos, compilación y ejecución.

El análisis semántico solo acepta GPIO de salida comunes del ESP32 clásico y excluye GPIO 6–11 (flash) y GPIO 34–39 (solo entrada). Los pines con funciones de arranque/UART y el LED integrado dependen del modelo; verifica siempre el pinout de tu placa.

## Gramática inicial

Las palabras clave no distinguen mayúsculas de minúsculas. Se permite indentación y comentarios desde `#`; cada instrucción debe estar en su propia línea.

```ebnf
programa      = INICIAR, nueva_linea, { sentencia }, FINALIZAR, nueva_linea ;
sentencia     = instruccion_led | espera | repeticion | botones | display7 |
                leer | mostrar | limpiar | condicional | continuo ;
instruccion_led = LED, entero, (ENCENDER | APAGAR), nueva_linea ;
espera        = ESPERAR, entero, nueva_linea ;
repeticion    = REPETIR, entero, nueva_linea, { sentencia },
                FIN_REPETIR, nueva_linea ;
botones       = BOTONES, entero, entero, entero, entero, COMO, identificador ;
display7      = DISPLAY7, entero, entero, entero, entero, entero, entero, entero,
                ACTIVO_BAJO, COMO, identificador ;
leer          = LEER_BINARIO, identificador, COMO, identificador ;
mostrar       = MOSTRAR, identificador, EN, identificador ;
limpiar       = LIMPIAR, identificador ;
condicional   = SI, identificador, operador_comparacion, entero, nueva_linea,
                { sentencia }, [ SINO, nueva_linea, { sentencia } ], FIN_SI ;
continuo      = REPETIR_SIEMPRE, nueva_linea, { sentencia }, FIN_REPETIR_SIEMPRE ;
operador_comparacion = "<" | "<=" | ">" | ">=" | "==" | "!=" ;
```

### Ejemplo: botones y display de siete segmentos

Este programa lee cuatro botones como un valor binario y muestra los dígitos del 0 al 9. Para valores del 10 al 15, apaga los segmentos:

```text
INICIAR

BOTONES 13 12 14 27 COMO switches
DISPLAY7 15 2 4 5 18 19 21 ACTIVO_BAJO COMO display

REPETIR_SIEMPRE
    LEER_BINARIO switches COMO numero

    SI numero <= 9
        MOSTRAR numero EN display
    SINO
        LIMPIAR display
    FIN_SI

    ESPERAR 50
FIN_REPETIR_SIEMPRE

FINALIZAR
```

El ejemplo completo se encuentra en [examples/switch_display.luma](./examples/switch_display.luma). `LEER_BINARIO` interpreta los pines de izquierda a derecha como bits de más a menos significativo. `MOSTRAR` usa una tabla de dígitos 0–9 y `LIMPIAR` apaga el display (nivel alto para segmentos activos en bajo). `SI` admite comparaciones entre una variable entera y un literal; las variables reciben su valor al ejecutar `LEER_BINARIO`.

Este ejemplo conserva la lectura local de botones y el display del programa original. No incluye las solicitudes Wi‑Fi/HTTP a ngrok ni la comunicación con el backend.

Los nombres de botones y display se declaran con `COMO`. `BOTONES` configura entradas con resistencia `PULL_DOWN`; `DISPLAY7 ... ACTIVO_BAJO` corresponde a un display de cátodo común. Verifica los requisitos eléctricos y el pinout de tu placa antes de conectarla.

## Instalación y uso

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Abre el editor gráfico:

```powershell
luma-gui
# o
python -m luma --gui
```

Compila un programa y muestra o guarda el MicroPython generado:

```powershell
python -m luma examples\parpadeo.luma
python -m luma examples\parpadeo.luma --output parpadeo.py
python -m luma examples\switch_display.luma
python -m luma examples\switch_display.luma --output switch_display.py
```

Para abrir el ejemplo en la interfaz, ejecuta `luma-gui`, pulsa **Abrir** y selecciona `examples\switch_display.luma`. Pulsa **Compilar** para ver el código generado. Para ejecutarlo en la placa, conecta un ESP32 con MicroPython y usa **Conectar** y **Ejecutar en ESP32**.

Genera la salida de ensamblador Xtensa:

```powershell
python -m luma examples\parpadeo.luma --target xtensa
python -m luma examples\parpadeo.luma --target xtensa --output parpadeo_xtensa.S
```

La pestaña **Ensamblador Xtensa** de la GUI muestra esta salida adicional. Este backend está dirigido al ESP32 clásico (Xtensa LX6); otros modelos ESP32 pueden usar Xtensa LX7 o RISC-V y requieren un backend diferente. La salida llama a rutinas externas (`luma_read_buttons`, `luma_display_show`, entre otras) que aún requieren un runtime de hardware; no es, por sí sola, un programa ejecutable ni se carga con **Ejecutar en ESP32**.

## Ejecutar en hardware real

1. Instala el firmware MicroPython apropiado para tu modelo ESP32 y confirma que el puerto serie aparece en el sistema.
2. Instala Luma y conecta la placa por USB. Cierra otros monitores serie que estén usando el puerto.
3. En la aplicación, actualiza la lista de puertos, selecciona el ESP32 y pulsa **Conectar**.
4. Compila/ejecuta el ejemplo. El programa se traduce primero a MicroPython y ese código se envía al Raw REPL; no se envían comandos Luma predefinidos.

La conexión a 115200 baudios puede reiniciar algunas placas. Al ejecutar se envía Ctrl-C para detener un programa anterior y Ctrl-A para solicitar Raw REPL; el firmware debe ofrecer ese protocolo estándar. La aplicación no instala firmware ni simula una placa. Se necesita comprobar el comportamiento eléctrico con el LED y resistencia adecuados y verificar el GPIO integrado de la placa.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

Las pruebas cubren lexer, AST/parser, análisis semántico y ambas salidas de código. La ejecución sobre hardware requiere una placa ESP32 física con firmware MicroPython; las pruebas locales no simulan esa validación.

## Extensiones

El AST separa el significado de las instrucciones del generador y del transporte. Nuevos comandos pueden añadirse como nodos y validaciones, y nuevos backends pueden consumir el mismo AST sin cambiar el protocolo serial.
# Compilador
