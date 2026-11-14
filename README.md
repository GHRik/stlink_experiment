# Ile prądu kosztuje jedna linijka kodu?

Kod i materiały do praktycznego eksperymentu przygotowywanego na potrzeby
artykułu do „Programisty”. Sprawdzamy, jak sposób oczekiwania na kolejne
zadanie wpływa na pobór prądu i energię całego cyklu pracy mikrokontrolera.
Liczba linii kodu i sam czas wykonania nie opisują tego kosztu.

## Stan projektu

Obecnie dostępne są szkice **NodeMCU / ESP8266** oraz narzędzie Python do
zbierania i analizy danych z **STLINK-V3PWR**. NodeMCU służy do uruchomienia
stanowiska. Raspberry Pi Pico 2 jest platformą docelową; jego kodu i pomiarów
jeszcze nie ma w repozytorium.

Istniejące szkice porównują modem sleep, light sleep i deep sleep na ESP8266.
Nie stanowią jeszcze docelowego porównania aktywnej pętli, opóźnień i usypiania
na Pico 2. Wyników różnych płytek nie należy traktować jako wpływu samego kodu.

## Zawartość

| Ścieżka | Przeznaczenie |
| --- | --- |
| `nodemcu_led_cycles/` | Trzy osobno wgrywane szkice ESP8266 i opis konfiguracji |
| `stlink_measure.py` | Polecenia `ports`, `capture`, `analyze`, `demo` |
| `stlink_protocol.py` | Komunikacja z miernikiem i dekodowanie próbek |
| `results.py` | Obliczenia, statystyki i wykresy |
| `options.py`, `storage.py` | Argumenty CLI i zapis danych |
| `test_stlink_measure.py` | Testy bez sprzętu |
| [docs/measurements.md](docs/measurements.md) | Podłączenie, pomiary, analiza i ograniczenia |
| [docs/experiment-plan.md](docs/experiment-plan.md) | Plan eksperymentu i artykułu |

## Uruchomienie w Windows

Python 3.10 lub nowszy. W PowerShell, w katalogu repozytorium:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v test_stlink_measure.py
.\.venv\Scripts\python.exe stlink_measure.py demo
```

`demo` zapisuje **dane syntetyczne**, a nie wyniki sprzętowe. Zależności mają
określone zakresy wersji, nie są zamrożone do dokładnego odtworzenia środowiska.

Przed pomiarem wgraj szkic i wykonaj instrukcję podłączenia z
[przewodnika pomiarowego](docs/measurements.md). Następnie znajdź port SMU:

```powershell
.\.venv\Scripts\python.exe stlink_measure.py ports
.\.venv\Scripts\python.exe stlink_measure.py capture --port COM18 --name modem --repeats 1 --seconds 15 --out test_results
```

`COM18` to przykład. Skrypt zasila płytkę przez OUT miernika; domyślne 3,3 V
i opis warunków dotyczą NodeMCU. Nie przenoś instrukcji zasilania na Pico 2
bez ustalenia właściwego połączenia i parametrów.

## Dane i odtwarzalność

`results/`, `test_results/` i `demo_results/` są lokalnymi katalogami ignorowanymi
przez Git. Zachowuj kopie surowych danych poza repozytorium. Dane przeznaczone
do artykułu zostaną później wybrane i opisane oddzielnie wraz z wersją kodu,
warunkami pomiaru i zakresem analizy. Na razie repozytorium nie zawiera
zweryfikowanego zestawu wyników do publikacji.

Pomiar obejmuje całą zasilaną płytkę, w tym jej układy pomocnicze. Energia jest
szacowana z próbek prądu i ustawionego napięcia. Obecne narzędzie nie oblicza
automatycznie energii zadania ani czasu pracy baterii.

Licencja: [MIT](LICENSE.txt). Autor: Damian Panasiuk.
