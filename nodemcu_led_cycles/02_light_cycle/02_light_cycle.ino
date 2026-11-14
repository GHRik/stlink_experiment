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

#include <coredecls.h>
extern "C" {
#include <user_interface.h>
}

// SDK internals: this sketch targets ESP8266 Arduino Core 3.1.2.
extern os_timer_t* timer_list;
volatile bool lightSleepFinished = false;

void onLightWake()
{
  lightSleepFinished = true;
  esp_schedule();
}

void setup() { prepareBoard(); }

void loop()
{
  ledTask();

  // Switch from forced modem sleep to forced timed light sleep.
  wifi_fpm_do_wakeup();
  wifi_fpm_close();
  wifi_fpm_set_sleep_type(LIGHT_SLEEP_T);
  wifi_fpm_set_wakeup_cb(onLightWake);
  wifi_fpm_open();

  // Pending SDK timers can prevent light sleep.
  os_timer_t* savedTimers = timer_list;
  timer_list = nullptr;
  lightSleepFinished = false;
  const int8_t result = wifi_fpm_do_sleep(WAIT_MS * 1000UL);
  if (result == 0) {
    // Yield to SDK; wake callback cancels the remaining delay.
    esp_delay(WAIT_MS + 1, []() { return !lightSleepFinished; });
  }
  timer_list = savedTimers;
  wifi_fpm_do_wakeup();
  wifi_fpm_close();

  // Restore the same radio-off active phase as the other sketches.
  WiFi.forceSleepBegin();
  delay(1);
}

