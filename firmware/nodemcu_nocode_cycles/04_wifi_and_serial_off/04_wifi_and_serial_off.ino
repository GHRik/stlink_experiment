#include <ESP8266WiFi.h>

void setup()
{
    // Disable Wi-Fi without requesting forced modem sleep.
    WiFi.persistent(false);
    WiFi.mode(WIFI_OFF);

    // Disable both hardware UART interfaces.
    Serial.end();
    Serial1.end();
}

void loop()
{
}
