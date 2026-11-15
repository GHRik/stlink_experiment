#include <ESP8266WiFi.h>

constexpr uint8_t LED_PIN = 2; // GPIO2 / D4, active-low built-in LED.

void setup()
{
    // Disable Wi-Fi and the radio.
    WiFi.persistent(false);
    WiFi.mode(WIFI_OFF);
    WiFi.forceSleepBegin();
    delay(1);

    // Disable both hardware UART interfaces.
    Serial.end();
    Serial1.end();

    // Turn off the LED after UART1 releases GPIO2.
    digitalWrite(LED_PIN, HIGH);
    pinMode(LED_PIN, OUTPUT);
}

void loop()
{
}
