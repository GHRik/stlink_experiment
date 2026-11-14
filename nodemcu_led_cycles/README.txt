NodeMCU 1.0 (ESP-12E Module), ESP8266 Arduino Core 3.1.2, CPU 80 MHz.
Three separate sketches. Flash each separately.
Each repeats LED ON for 2 s, LED OFF/wait for approximately 8 s.
Runs continuously: select 10 full cycles in recorded data.
01: forced modem sleep; CPU remains active during wait.
02: timed forced light sleep; resumes without reset.
03: deep sleep; restarts setup after each wake. Connect D0 to RST.
For deep sleep a Schottky diode is preferable if using the physical reset
button: anode at RST, cathode (stripe) at D0, per upstream LowPowerDemo.
Disconnect D0-RST if it interferes with uploading.
Power measurement: OUT -> 3V3, GND -> GND, 3300 mV, no NodeMCU USB.
USB flashing: disconnect STLINK output wiring first.
Keep sampling frequency identical. Record 120 s to capture >=10 cycles.
The deep-sleep cycle includes startup overhead and is longer than 10 s.
Use the actual cycle duration from measured data.
These sketches have not been compiled or hardware-tested here.
Light sleep uses SDK timer_list internals, as in upstream LowPowerDemo.
Verify ~8 s low-current plateau and automatic repeat before collecting data.
If LED pulses occur twice as far apart or current does not drop, do not
label the result light sleep; check Core version and the implementation.
Source: https://github.com/esp8266/Arduino/tree/master/libraries/esp8266/examples/LowPowerDemo
