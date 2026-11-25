#include <ESP8266WiFi.h>

void setup()
{
    // Request automatic modem sleep; this does not force the radio off.
    WiFi.setSleepMode(WIFI_MODEM_SLEEP);
}

void loop()
{
    delay(5000);
}
