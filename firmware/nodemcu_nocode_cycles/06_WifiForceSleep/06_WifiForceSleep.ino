#include <ESP8266WiFi.h>

void setup()
{
    WiFi.forceSleepBegin();
    delay(1); // Allow Wi-Fi sleep to take effect.
}

void loop()
{
}
