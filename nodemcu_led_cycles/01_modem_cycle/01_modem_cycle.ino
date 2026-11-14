#include <ESP8266WiFi.h>

constexpr uint32_t LED_ON_MS = 2000;
constexpr uint32_t WAIT_MS = 8000;

void prepareBoard()
{
  digitalWrite(LED_BUILTIN, HIGH);
  pinMode(LED_BUILTIN, OUTPUT);
  WiFi.persistent(false);
  WiFi.mode(WIFI_OFF);
  WiFi.forceSleepBegin();
  delay(1);
  Serial.end();
  Serial1.end();
}

void ledTask()
{
  digitalWrite(LED_BUILTIN, LOW);
  delay(LED_ON_MS);
  digitalWrite(LED_BUILTIN, HIGH);
}

void setup() { prepareBoard(); }

void loop()
{
  ledTask();
  delay(WAIT_MS); // Radio off, CPU remains active.
}

