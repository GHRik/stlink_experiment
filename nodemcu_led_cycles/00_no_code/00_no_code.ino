#include <ESP8266WiFi.h>

void setup()
{
    // Turn off the built-in LED.
    digitalWrite(LED_BUILTIN, HIGH);
    pinMode(LED_BUILTIN, OUTPUT);

    // Disable Wi-Fi and the radio.
    WiFi.persistent(false);
    WiFi.mode(WIFI_OFF);
    WiFi.forceSleepBegin();
    delay(1);

    // Disable the serial interfaces.
    Serial.end();
    Serial1.end();
}

void loop()
{
}
