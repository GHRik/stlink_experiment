#include <ESP8266WiFi.h>

constexpr uint8_t LED_PIN = 2; // GPIO2 / D4, active-low built-in LED.

constexpr uint32_t LED_ON_MS = 2000;
constexpr uint32_t WAIT_MS = 8000;

void prepareBoard()
{
  WiFi.persistent(false);
  WiFi.mode(WIFI_OFF);
  WiFi.forceSleepBegin();
  delay(1);
  Serial.end();
  Serial1.end();
  // Configure GPIO2 after UART1 releases its TX pin.
  digitalWrite(LED_PIN, HIGH);
  pinMode(LED_PIN, OUTPUT);
}

void ledTask()
{
  digitalWrite(LED_PIN, LOW);
  delay(LED_ON_MS);
  digitalWrite(LED_PIN, HIGH);
}

void setup()
{
  prepareBoard();
  ledTask();
  // Timed wake requires D0 (GPIO16) connected to RST.
  ESP.deepSleep(WAIT_MS * 1000ULL, WAKE_RF_DISABLED);
}

void loop() {}

