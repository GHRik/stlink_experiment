#include <ESP8266WiFi.h>

void setup()
{
    // Force the radio into modem sleep. This API also sets Wi-Fi to WIFI_OFF.
    WiFi.forceSleepBegin();
    delay(1);
}

void loop()
{
}
