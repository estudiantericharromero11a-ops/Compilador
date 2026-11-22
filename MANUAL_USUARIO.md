# Manual de usuario de Luma

Luma es un lenguaje de instrucciones en español para describir programas sencillos de LEDs, botones, displays de siete segmentos y servomotores. El compilador analiza cada programa y genera MicroPython para ESP32, Arduino C++ para Arduino Mega y una salida de ensamblador Xtensa LX6.

Este manual describe la sintaxis que acepta el compilador. No es un lenguaje Python ni C++: escribe los comandos Luma en un archivo `.luma` y compílalo para el destino elegido.

## Primer programa

```text
INICIAR

REPETIR 5
    LED 2 ENCENDER
    ESPERAR 500
    LED 2 APAGAR
    ESPERAR 500
FIN_REPETIR

FINALIZAR
```

El programa hace parpadear el GPIO 2 cinco veces, con una espera de 500 milisegundos entre cambios. El programa completo debe comenzar con `INICIAR` y terminar con `FINALIZAR`.

## Reglas generales

- Las palabras reservadas aceptan mayúsculas o minúsculas. Por ejemplo, `iniciar` y `INICIAR` son equivalentes.
- Los nombres que declares tú, como `switches` o `puerta`, distinguen mayúsculas de minúsculas.
- Un nombre comienza con una letra ASCII o `_`; después puede contener letras ASCII, números y `_`. No uses tildes ni espacios en los nombres.
- Escribe una instrucción por línea. La indentación facilita la lectura de los bloques, pero no determina su alcance.
- `#` inicia un comentario que continúa hasta el final de la línea. Puede usarse en una línea aparte o después de una instrucción.
- Se permiten líneas vacías.
- Declara `BOTONES`, `DISPLAY7` y `SERVOMOTOR` fuera de ciclos y condicionales, antes de utilizarlos.
- Los programas solo pueden usar las instrucciones documentadas aquí; no admiten expresiones aritméticas ni asignaciones libres. Las variables reciben valores mediante `LEER_BINARIO`.

## Diccionario de palabras reservadas

| Palabra | Uso |
| --- | --- |
| `INICIAR` | Abre el programa. Debe ser la primera instrucción. |
| `FINALIZAR` | Cierra el programa. Debe aparecer al final. |
| `LED` | Selecciona un GPIO de salida, junto con `ENCENDER` o `APAGAR`. |
| `ENCENDER` | Pone el LED o GPIO en nivel alto. |
| `APAGAR` | Pone el LED o GPIO en nivel bajo. |
| `ESPERAR` | Pausa la ejecución por una cantidad de milisegundos. |
| `REPETIR` | Inicia un ciclo con cantidad fija de repeticiones. |
| `FIN_REPETIR` | Cierra un ciclo `REPETIR`. |
| `REPETIR_SIEMPRE` | Inicia un ciclo que se repite indefinidamente. |
| `FIN_REPETIR_SIEMPRE` | Cierra un ciclo `REPETIR_SIEMPRE`. |
| `BOTONES` | Declara cuatro pines de entrada como un grupo de switches o botones. |
| `ACTIVO_BAJO` | Configura botones activos en bajo; también es obligatorio para declarar un display de segmentos activos en bajo. |
| `COMO` | Asigna un nombre a una declaración o al resultado de `LEER_BINARIO`. |
| `LEER_BINARIO` | Lee los cuatro pines de una declaración `BOTONES` y guarda un número de 0 a 15. |
| `SI` | Inicia una condición que compara una variable con un número. |
| `SINO` | Inicia la alternativa de un bloque `SI`; es opcional. |
| `FIN_SI` | Cierra un bloque `SI`. |
| `DISPLAY7` | Declara siete pines de salida para los segmentos A, B, C, D, E, F y G, en ese orden. |
| `MOSTRAR` | Muestra en un display el valor de una variable, si está entre 0 y 9. |
| `EN` | Separa el valor y el display en `MOSTRAR`. |
| `LIMPIAR` | Apaga los siete segmentos del display. |
| `SERVOMOTOR` | Declara el pin de señal de un servomotor y le asigna un nombre. |
| `MOVER` | Ordena mover un servomotor declarado. |
| `ANGULO` | Introduce el ángulo en una instrucción `MOVER`. |

### Operadores de comparación

`SI` admite únicamente estos operadores:

| Operador | Significado |
| --- | --- |
| `<` | Menor que |
| `<=` | Menor o igual que |
| `>` | Mayor que |
| `>=` | Mayor o igual que |
| `==` | Igual a |
| `!=` | Distinto de |

La forma de la condición es `SI nombre_variable operador número`. No se admiten comparaciones entre dos variables ni condiciones compuestas con `Y` u `O`.

## Instrucciones y ejemplos

### LEDs y esperas

```text
LED 13 ENCENDER
ESPERAR 250
LED 13 APAGAR
```

`LED` recibe un número de pin y una acción. `ESPERAR` recibe milisegundos. El intervalo permitido es de 0 a 86.400.000 ms.

### Ciclo con cantidad fija

```text
REPETIR 3
    LED 13 ENCENDER
    ESPERAR 200
    LED 13 APAGAR
    ESPERAR 200
FIN_REPETIR
```

La cantidad debe estar entre 1 y 10.000. Los ciclos y bloques `SI` pueden anidarse hasta 32 niveles.

### Ciclo continuo

```text
REPETIR_SIEMPRE
    LED 13 ENCENDER
    ESPERAR 300
    LED 13 APAGAR
    ESPERAR 300
FIN_REPETIR_SIEMPRE
```

El bloque continúa hasta detener el programa o reiniciar la placa o simulación.

### Leer cuatro botones o switches

```text
BOTONES 13 12 14 27 COMO switches
LEER_BINARIO switches COMO numero
```

`BOTONES` necesita exactamente cuatro pines. El primero es el bit más significativo y el cuarto es el menos significativo: el resultado va de 0 a 15.

Sin `ACTIVO_BAJO`, el nivel eléctrico alto se interpreta como bit 1. En MicroPython para ESP32 se configura `PULL_DOWN`; en Arduino Mega se configura `INPUT`, por lo que se requiere una resistencia externa que establezca el nivel cuando el botón está suelto.

Con `ACTIVO_BAJO`, el nivel bajo se interpreta como botón presionado y bit 1. En ESP32 se configura `PULL_UP`; en Arduino Mega se configura `INPUT_PULLUP`. En ambos casos conecta el botón entre el pin y GND.

```text
BOTONES 2 3 12 13 ACTIVO_BAJO COMO controles
```

### Condiciones

```text
LEER_BINARIO switches COMO numero
SI numero <= 9
    MOSTRAR numero EN display
SINO
    LIMPIAR display
FIN_SI
```

La variable de una condición debe haber recibido un valor mediante `LEER_BINARIO` antes de usarse. El compilador también verifica que esté definida en todas las rutas posibles antes de su uso posterior. Los números de comparación deben estar entre 0 y 15.

### Display de siete segmentos

```text
DISPLAY7 15 2 4 5 18 19 21 ACTIVO_BAJO COMO display
MOSTRAR numero EN display
LIMPIAR display
```

`DISPLAY7` recibe siete pines en el orden A, B, C, D, E, F, G y requiere `ACTIVO_BAJO`. El generador interpreta nivel bajo como segmento encendido y nivel alto como apagado (típico de un display de ánodo común). `MOSTRAR` representa los dígitos del 0 al 9; para otros valores limpia el display. `LIMPIAR` pone todos los segmentos en nivel alto.

Usa una resistencia limitadora adecuada para cada segmento y verifica el tipo y pinout del display antes de conectarlo.

### Servomotor

```text
SERVOMOTOR 9 COMO puerta
MOVER puerta ANGULO 90
```

El ángulo debe estar entre 0 y 180 grados. El compilador genera control PWM para MicroPython y usa la biblioteca `Servo` de Arduino para el destino Arduino Mega.

## Destinos y pines

El compilador valida los pines de acuerdo con la placa seleccionada:

- **ESP32 clásico:** admite como GPIO de entrada o salida `0–5`, `12–19`, `21–23`, `25–27` y `32–33`. Excluye GPIO 6–11, reservados para la memoria flash, y GPIO 34–39, que son solo de entrada y no están habilitados por el compilador.
- **Arduino Mega:** admite los pines digitales 0–69.

No uses un mismo pin para dispositivos distintos. El compilador detecta pines repetidos en una declaración y conflictos entre dispositivos. Consulta el pinout de tu placa: algunos pines tienen funciones especiales, como arranque, UART o comunicación periférica, aunque estén dentro de un rango aceptado.

## Compilar y ejecutar

Instala el proyecto desde la raíz del repositorio y activa el entorno virtual:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Compila un archivo `.luma` desde la terminal:

```powershell
python -m luma examples\parpadeo.luma
python -m luma examples\servo_door.luma --target arduino
python -m luma examples\parpadeo.luma --target xtensa
```

El destino predeterminado es `micropython`. También puedes guardar la salida con `--output archivo`:

```powershell
python -m luma examples\parpadeo.luma --output parpadeo.py
python -m luma examples\servo_door.luma --target arduino --output sketch.ino
```

En Windows, abre la interfaz con `luma-gui` o `python -m luma --gui`. Abre un archivo `.luma` y pulsa **Compilar**. El selector **Destino Wokwi** elige la placa para la validación y la pestaña de salida correspondiente.

Para ejecutar MicroPython en un ESP32 físico, instala antes firmware MicroPython compatible, conecta la placa por USB, selecciona el puerto COM y pulsa **Conectar** y **Ejecutar en ESP32**. La ejecución serial no carga firmware y requiere que ningún otro programa esté usando el puerto.

Para exportar a una carpeta local de Wokwi, el proyecto debe contener `diagram.json`:

```powershell
python -m luma examples\switch_display.luma --target micropython --wokwi-dir "C:\ruta\al\proyecto" --force
python -m luma examples\servo_door.luma --target arduino --wokwi-dir "C:\ruta\al\proyecto" --force
```

El primer comando escribe `main.py`; el segundo escribe `sketch.ino`. `--force` permite reemplazar el archivo si ya existe.

También puedes usar **Enviar a Wokwi** en la interfaz para reemplazar el editor de una simulación abierta en Google Chrome. Selecciona el destino correcto y asegúrate de tener abierto el proyecto y archivo adecuados: `main.py` para MicroPython o `sketch.ino` para Arduino Mega. La salida Xtensa es un módulo de ensamblador con llamadas a rutinas de hardware externas; no es un firmware ejecutable por sí solo ni se envía con **Ejecutar en ESP32**.

## Errores comunes

- **Falta `INICIAR`, `FINALIZAR` o un cierre:** cada bloque debe tener su palabra de cierre correspondiente.
- **Instrucciones en la misma línea:** separa cada instrucción con un salto de línea.
- **Variable sin valor:** ejecuta `LEER_BINARIO ... COMO variable` antes de comparar o mostrar esa variable.
- **Nombre de dispositivo no declarado:** declara el grupo con `BOTONES`, el display con `DISPLAY7` o el servo con `SERVOMOTOR` antes de usarlo.
- **Pin ocupado o no disponible:** verifica el destino elegido y evita compartir el pin entre dispositivos.
- **Entrada que cambia sola:** en Arduino, las entradas `BOTONES` sin `ACTIVO_BAJO` necesitan resistencias externas; en ESP32 se usa `PULL_DOWN` por defecto.
- **La simulación no coincide con la placa:** selecciona `Arduino Mega` para `sketch.ino` y `MicroPython` para `main.py`.

Los ejemplos completos están en [examples/](./examples/). Para las pruebas del compilador, ejecuta `python -m unittest discover -s tests -v`.
