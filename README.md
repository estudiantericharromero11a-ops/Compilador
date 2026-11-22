# Luma: compilador educativo para ESP32

Luma es un lenguaje de instrucciones en español que se compila mediante etapas reales —lexer, parser con AST, análisis semántico y generador— a MicroPython para ESP32, Arduino C++ para Arduino Mega y un módulo de ensamblador GNU Xtensa LX6. La interfaz Tkinter edita y compila programas, detecta puertos serie y puede ejecutar el código MicroPython en un ESP32 mediante USB/Serial.

Luma también permite leer grupos de cuatro entradas o botones individuales, controlar un display de siete segmentos o una LCD 16×2, mover servomotores y crear máquinas de estados con variables enteras. La conexión HTTP/Wi‑Fi del ejemplo externo no forma parte del lenguaje ni se genera.

Consulta el [Manual de usuario de Luma](./MANUAL_USUARIO.md) para ver el diccionario de instrucciones, la sintaxis, los límites del lenguaje y ejemplos de uso.

## Decisiones y arquitectura

- **MicroPython como destino inicial:** no requiere compilar un firmware Arduino; el programa generado se ejecuta en el Raw REPL de MicroPython. El firmware MicroPython debe estar instalado previamente en la placa.
- **Arduino C++ para Wokwi:** el destino `arduino` valida pines de Arduino Mega y genera `sketch.ino` con las bibliotecas estándar `Servo` y `LiquidCrystal` cuando se necesitan.
- **Python 3.10+ y Tkinter:** pyserial habilita el ESP32 físico y pyautogui automatiza el editor web de Wokwi en Windows. Tkinter suele venir con Python.
- `src/luma/lexer.py`: tokens, palabras clave, caracteres inválidos y ubicación.
- `src/luma/parser.py` y `ast.py`: gramática, errores de sintaxis y árbol.
- `src/luma/semantic.py`: rangos de GPIO, declaraciones de dispositivos, variables, LCD, duración y repeticiones.
- `src/luma/codegen.py`: traducción independiente del transporte a MicroPython.
- `src/luma/arduino_codegen.py`: generación de sketches Arduino Mega.
- `src/luma/assembly_codegen.py`: backend de ensamblador Xtensa LX6 con llamadas a rutinas de hardware externas.
- `src/luma/transport.py`: enumeración de puertos y protocolo MicroPython Raw REPL.
- `src/luma/gui.py`: editor con resaltado, archivos, compilación y ejecución.

El análisis semántico valida pines según el destino: ESP32 clásico excluye GPIO 6–11 (flash) y GPIO 34–39 (solo entrada); Arduino Mega admite sus pines digitales 0–69. Verifica siempre el pinout de la placa seleccionada.

### Patrón de presentación con siete LEDs

El ejemplo [examples/presentacion_leds.luma](./examples/presentacion_leds.luma) anima siete LEDs rojos con un rebote y alternancia. El switch 1 activa el patrón y, al apagarlo, los LEDs se apagan al terminar el ciclo actual. Conecta ese switch a GPIO 32; conecta los LEDs, de arriba hacia abajo, a GPIO 13, 14, 18, 19, 21, 22 y 23. Como los componentes de la imagen están conectados a salidas de puertas lógicas y el circuito no muestra un ESP32, hay que añadir el ESP32 y conectar cada LED a su GPIO mediante una resistencia; conecta los cátodos a GND y comparte GND con el ESP32. Desconecta las salidas de las puertas de esos LEDs para evitar conectar dos salidas al mismo nodo.

## Gramática inicial

Las palabras clave no distinguen mayúsculas de minúsculas. Se permite indentación y comentarios desde `#`; cada instrucción debe estar en su propia línea.

```ebnf
programa      = INICIAR, nueva_linea, { sentencia }, FINALIZAR, nueva_linea ;
sentencia     = instruccion_led | espera | repeticion | botones | display7 |
                boton | leer_boton | asignar | lcd16x2 | limpiar_lcd |
                cursor_lcd | escribir_lcd | servomotor | mover_servo |
                leer | mostrar | limpiar | condicional | continuo ;
instruccion_led = LED, entero, (ENCENDER | APAGAR), nueva_linea ;
espera        = ESPERAR, entero, nueva_linea ;
repeticion    = REPETIR, entero, nueva_linea, { sentencia },
                FIN_REPETIR, nueva_linea ;
botones       = BOTONES, entero, entero, entero, entero, [ ACTIVO_BAJO ],
                COMO, identificador ;
boton         = BOTON, entero, [ ACTIVO_BAJO ], COMO, identificador ;
leer_boton    = LEER_BOTON, identificador, COMO, identificador ;
asignar       = ASIGNAR, identificador, "=", entero ;
display7      = DISPLAY7, entero, entero, entero, entero, entero, entero, entero,
                ACTIVO_BAJO, COMO, identificador ;
lcd16x2       = LCD16X2, entero, entero, entero, entero, entero, entero,
                COMO, identificador ;
limpiar_lcd   = LIMPIAR_LCD, identificador ;
cursor_lcd    = CURSOR_LCD, identificador, entero, entero ;
escribir_lcd  = ESCRIBIR_LCD, identificador, cadena ;
servomotor    = SERVOMOTOR, entero, COMO, identificador ;
mover_servo   = MOVER, identificador, ANGULO, entero ;
leer          = LEER_BINARIO, identificador, COMO, identificador ;
mostrar       = MOSTRAR, identificador, EN, identificador ;
limpiar       = LIMPIAR, identificador ;
condicional   = SI, identificador, operador_comparacion, entero, nueva_linea,
                { sentencia }, [ SINO, nueva_linea, { sentencia } ], FIN_SI ;
continuo      = REPETIR_SIEMPRE, nueva_linea, { sentencia }, FIN_REPETIR_SIEMPRE ;
operador_comparacion = "<" | "<=" | ">" | ">=" | "==" | "!=" ;
cadena              = '"', { carácter_ASCII_imprimible | '\"' | '\\' }, '"' ;
```

`ASIGNAR` recibe un entero de 0 a 65535. Una cadena LCD va entre comillas y admite caracteres ASCII imprimibles, `\"` y `\\`.

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

Los nombres de botones y display se declaran con `COMO`. En ESP32, `BOTONES` configura entradas con resistencia `PULL_DOWN` por defecto; al agregar `ACTIVO_BAJO` usa `PULL_UP` y considera presionado un botón conectado a GND. En Arduino Mega, sin `ACTIVO_BAJO` las entradas usan `INPUT` y requieren resistencias externas; con `ACTIVO_BAJO` usan `INPUT_PULLUP`. `DISPLAY7 ... ACTIVO_BAJO` corresponde a segmentos activos en bajo, como en el display de ánodo común del circuito Wokwi enlazado. Verifica los requisitos eléctricos y el pinout de tu placa antes de conectarla.

### Ejemplo: puerta con servomotor

[examples/servo_door.luma](./examples/servo_door.luma) reproduce el circuito Wokwi Arduino Mega: servo en el pin 9, botones activos en bajo en los pines 2/3 y LEDs en 6/7. El botón 1 abre a 0° y enciende el LED verde; el botón 2 cierra a 90° y enciende el rojo. Si se presionan ambos, abrir tiene prioridad como en el sketch original. Al soltar los botones, ambos LEDs se apagan y el servo mantiene su posición. `ACTIVO_BAJO` conserva `INPUT_PULLUP`: conecta los botones entre sus pines y GND. Los pines 12/13 son entradas auxiliares con pull-up interno, sin conectar. En hardware real, alimenta el servo desde una fuente adecuada y comparte GND con el Mega.

### Ejemplo: máquina expendedora

[examples/maquina_bebidas.luma](./examples/maquina_bebidas.luma) implementa la máquina de bebidas con una LCD 16×2, seis botones activos en bajo, cuatro LEDs de selección, un LED indicador y un servomotor. Utiliza Arduino Mega: botones A0–A5 corresponden a pines digitales 54–59; la LCD usa RS=12, E=11 y D4–D7=5,4,3,2; el servo usa el pin 10; los LEDs usan 6–9 y 13. El pin 13 se configura como salida para el indicador de reposo y el estado de selección espera correctamente una bebida antes de dispensarla.

Compila el programa como Arduino y envíalo a un proyecto Wokwi configurado como **Arduino Mega**, con `sketch.ino` abierto. La salida Xtensa `.S` es un módulo de referencia para otro backend, depende de rutinas de hardware externas y no puede ejecutarse en Wokwi; la GUI permite guardarla localmente con **Guardar Xtensa .S**.

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

Compila un programa y muestra o guarda el MicroPython generado por defecto:

```powershell
python -m luma examples\parpadeo.luma
python -m luma examples\parpadeo.luma --output parpadeo.py
python -m luma examples\switch_display.luma
python -m luma examples\switch_display.luma --output switch_display.py
```

Para generar Arduino C++ compatible con `sketch.ino`:

```powershell
python -m luma examples\servo_door.luma --target arduino
python -m luma examples\servo_door.luma --target arduino --output sketch.ino
python -m luma examples\maquina_bebidas.luma --target arduino --output sketch.ino
```

Para exportar directamente a una copia local de un proyecto Wokwi (debe incluir `diagram.json`), elige el destino adecuado:

```powershell
python -m luma examples\servo_door.luma --target arduino --wokwi-dir "C:\ruta\al\proyecto-wokwi" --force
python -m luma examples\maquina_bebidas.luma --target arduino --wokwi-dir "C:\ruta\al\proyecto-wokwi" --force
python -m luma examples\switch_display.luma --target micropython --wokwi-dir "C:\ruta\al\proyecto-wokwi" --force
```

El destino Arduino escribe `sketch.ino`. En la GUI, elige **Arduino Mega** o **MicroPython** en el selector **Destino Wokwi** antes de exportar.

Para reemplazar código en Wokwi abierto en Chrome, selecciona el destino correcto, deja visible el archivo correspondiente (`sketch.ino` para Arduino o `main.py` para MicroPython) y pulsa **Enviar a Wokwi**. Luma pedirá confirmación, pegará el destino y reiniciará la simulación. Para este proyecto Mega no hace falta agregar bibliotecas externas.

Para abrir el ejemplo en la interfaz, ejecuta `luma-gui`, pulsa **Abrir** y selecciona un archivo `.luma`. **Compilar** genera las salidas Arduino Mega, MicroPython y Xtensa; elige el destino que corresponda a tu proyecto o firmware.

Genera la salida de ensamblador Xtensa:

```powershell
python -m luma examples\parpadeo.luma --target xtensa
python -m luma examples\parpadeo.luma --target xtensa --output parpadeo_xtensa.S
```

La pestaña **Ensamblador Xtensa** de la GUI muestra esta salida adicional y **Guardar Xtensa .S** la exporta como archivo local. Este backend está dirigido al ESP32 clásico (Xtensa LX6); otros modelos ESP32 pueden usar Xtensa LX7 o RISC-V y requieren un backend diferente. La salida llama a rutinas externas (`luma_read_buttons`, `luma_display_show`, `luma_lcd_write`, entre otras) que aún requieren un runtime de hardware; no es, por sí sola, un programa ejecutable ni se carga con **Ejecutar en ESP32**. Para la máquina expendedora usa `sketch.ino` en Arduino Mega, no su salida Xtensa.

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

Las pruebas cubren lexer, AST/parser, análisis semántico y las salidas de código. La ejecución sobre hardware requiere una placa ESP32 física con firmware compatible; las pruebas locales no simulan esa validación.

## Extensiones

El AST separa el significado de las instrucciones del generador y del transporte. Nuevos comandos pueden añadirse como nodos y validaciones, y nuevos backends pueden consumir el mismo AST sin cambiar el protocolo serial.
# Compilador
