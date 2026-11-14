# Pomiary NodeMCU przez STLINK-V3PWR

Skrypt steruje miernikiem, zapisuje wszystkie zarejestrowane próbki do CSV,
rysuje wykresy PNG/SVG i liczy statystyki między niezależnymi pomiarami.
Każdy szkic Arduino wgrywasz osobno. Skrypt nie programuje NodeMCU.

## Jak czytać kod

Zacznij od stlink_measure.py. Funkcja run_experiment opisuje cały przebieg
w kolejności wykonania: sprawdzenie ustawień, połączenie, konfiguracja,
pętla pomiarów, zamknięcie miernika i wspólny raport.

Pozostałe pliki zawierają szczegóły:

- stlink_protocol.py: komendy urządzenia, dekodowanie i odbiór próbek.
- results.py: statystyki, analiza zapisanych danych i wykresy.
- options.py: argumenty terminala i ich wartości domyślne.
- storage.py: zapis JSON i CSV.

Trzymaj wszystkie pliki w jednym katalogu. Dotychczasowe polecenia działają
bez zmian. Parser obsługuje również prompt firmware stlp > przed ACK,
metadanymi i próbkami. Parser ma testy odpowiedzi firmware V4.J7.B3.P6. Każde stanowisko wymaga osobnego sprawdzenia na sprzęcie.

## Pierwsze uruchomienie w Windows

1. Zainstaluj Python 3.10 lub nowszy. Rozpakuj cały katalog.
2. Otwórz terminal w tym katalogu i wykonaj:

```powershell
py -m pip install -r requirements.txt
py stlink_measure.py ports
```

3. W CubeMonitor-Power kliknij RELEASE CONTROL i zamknij program. Zamknij
   też terminal szeregowy używający portu STLINK.
4. Wybierz port pomiarowy SMU, np. COM18, który widziałeś w CubeMonitor-Power.
   STLINK ma również inny port do UART debug: to nie ten.
5. NodeMCU: OUT do 3V3, GND do GND. USB NodeMCU odłączone.
   Skrypt domyślnie ustawia 3,3 V. Dla deep sleep potrzebne D0-RST.
6. Najpierw zrób JEDEN krótki test komunikacji:

```powershell
py stlink_measure.py capture --port COM18 --name test --repeats 1 --seconds 15 --out test_results
```

Jeżeli test się powiedzie i LED pracuje zgodnie z programem, uruchom serię.
Zmień COM18 na swój port. Wgrywanie po USB rób przy odłączonych przewodach
zasilających ze STLINK, potem odłącz USB i wróć do połączenia pomiarowego.

## Trzy konfiguracje

Po wgraniu 01_modem_cycle:

```powershell
py stlink_measure.py capture --port COM18 --name modem --repeats 10 --seconds 120 --hz 1000
```

Po wgraniu 02_light_cycle:

```powershell
py stlink_measure.py capture --port COM18 --name light --repeats 10 --seconds 120 --hz 1000
```

Po wgraniu 03_deep_cycle i podłączeniu D0-RST:

```powershell
py stlink_measure.py capture --port COM18 --name deep --repeats 10 --seconds 120 --hz 1000
```

To 10 oddzielnych rejestracji po 120 s na konfigurację. Każda obejmuje
około 12 cykli LED. Powtórzeniem statystycznym jest cała rejestracja,
a nie pojedyncza próbka ani każdy cykl w tej samej rejestracji.
Każda seria potrwa nieco ponad 20 minut.

Wszystkie polecenia zapisują do wspólnego results. Nazwy sesji zawierają
datę i czas, więc nowe pomiary nie zastępują poprzednich.
Opcja --out pozwala rozdzielić eksperymenty. --notes zapisuje opis wersji
programu, płytki i warunków; używaj tego samego opisu dla tych samych warunków.

## Co dzieje się w jednym powtórzeniu

1. Skrypt odłącza zasilanie OUT i AUX na 1 s.
2. Uzbraja automatyczne włączenie OUT razem ze startem pomiaru.
3. Uruchamia rejestrację, więc NodeMCU zaczyna od startu zasilania.
4. Pobiera próbki przez zadany czas według zegara próbkowania urządzenia.
5. Wysyła stop i wyłącza zasilanie, zapisuje dane oraz wykres.
6. Powtarza procedurę.

To odpowiednik resetowania zasilaniem, wykonany PRZED każdym pomiarem.
Skrypt używa pwr off / pwr vout auto / start zamiast wysyłania targrst
w trwającym strumieniu. Pozwala to uniknąć niepewnego wyrównywania wykresu
do czasu wysłania komendy z komputera. AUX pozostaje wyłączone.

Oś czasu zaczyna się od pierwszego okresu próbkowania. Nie jest to
niezależny pomiar chwili narastania napięcia. Przy 1000 Hz rozdzielczość
czasowa próbek wynosi 1 ms. Fizyczne narastanie napięcia i rozruch mają
skończony czas. To nie jest pomiar opóźnień z dokładnością oscyloskopu.

120 s realizowane jest przez rejestrację ciągłą i zatrzymanie po wymaganej
liczbie próbek, bo ograniczona akwizycja firmware ma maksimum 100 s.
Nadmiar końcowych danych pozostaje w stream.bin; CSV zawiera dokładnie
zadany zakres. Przerwanie Ctrl+C uruchamia próbę stop/wyłączenia wyjść.
Po zerwaniu USB nie można zagwarantować wykonania tych komend.

## Pliki wynikowe

W katalogu każdego powtórzenia:

- samples.csv: wszystkie próbki, bez redukcji. Indeks, czas [s], prąd [µA],
  ustawione napięcie [V], obliczona moc [mW], skumulowana szacowana energia [J].
- stream.bin: oryginalny odebrany strumień ASCII (mimo rozszerzenia bin),
  w tym metadane, błędy i odpowiedzi. Pozwala sprawdzić dekodowanie.
- metadata.json: ustawienia, firmware, ID miernika, opis i ważność pomiaru.
- commands.json: dziennik komend hosta. Czas hosta nie zastępuje czasu próbek.
- analysis.json: wyniki dla aktualnie wybranego przedziału.
- current.png oraz current.svg: przebieg prądu.

W katalogu głównym results:

- runs_summary.csv: jeden wiersz na niezależny pomiar.
- statistics.csv: średnia, SD między pomiarami i 95% przedział ufności średniej.
- comparison.png/svg: pierwszy poprawny przebieg każdej serii na wspólnych osiach.
- statistics.png/svg: osobne punkty pomiarowe oraz średnia +/- SD.
- excluded_runs.json: pomiary wyłączone z analizy z podaniem powodu.

CSV używa średnika i kropki dziesiętnej. Excel: Dane -> Z tekstu/pliku CSV,
separator średnik. Jeśli liczby są tekstem, ustaw lokalizację konwersji
liczb na English (United States) w Power Query. CSV jest pełnym eksportem;
skrypt nie tworzy pliku XLSX.

Wykresy są uproszczone wyłącznie wizualnie: w przedziałach zachowane są
minimum i maksimum. Obliczenia zawsze korzystają ze wszystkich próbek CSV.

## Analiza bez ponawiania pomiarów

Przelicz cały wspólny katalog:

```powershell
py stlink_measure.py analyze --root results
```

Porównaj dokładnie pierwsze 100 s:

```powershell
py stlink_measure.py analyze --root results --from-s 0 --to-s 100
```

Porównaj wybrany fragment oczekiwania pierwszego cyklu, np. 4-8 s:

```powershell
py stlink_measure.py analyze --root results --from-s 4 --to-s 8
```

NAJPIERW potwierdź na wykresie, że w tym zakresie wszystkie konfiguracje
rzeczywiście czekają. Ten skrypt nie rozpoznaje automatycznie faz LED ani
uśpienia. Nie wycina automatycznie 10 pełnych cykli, nie oblicza też energii
pojedynczego cyklu. Analizuje jawnie zadany przedział czasu.
Pełne 120 s mogą zawierać różną liczbę cykli i niepełny ostatni cykl:
nie opisuj ich jako 10 jednakowych zadań. Porównanie energii na zadanie
wymaga osobnego oznaczenia granic pełnych cykli.

Ponowna analiza zastępuje wyłącznie raporty i wykresy, nigdy CSV próbek.
Jeśli chcesz zachować kilka analiz, skopiuj raporty przed kolejną analizą.

## Co znaczą liczby

- mean_current_mA: średni prąd w wybranym przedziale.
- within_run_sd_mA: zmienność prądu WEWNĄTRZ jednej rejestracji.
- energy_estimate_J: szacowana energia w wybranym przedziale przy założeniu
  stałego napięcia równego ustawieniu STLINK. Napięcie nie jest osobno próbkowane.
  Użyto sumy prądów pomnożonej przez okres próbki i ustawione napięcie.
  To oszacowanie z próbek prądu, nie sprzętowy tryb output energy.
- between_run_sd: odchylenie standardowe PRÓBY między wynikami rejestracji.
- ci95_low/high: przedział ufności średniej oparty na rozkładzie t-Studenta.
  Przy pojedynczym pomiarze SD i przedział pozostają puste.

Niska wartość SD nie dowodzi dokładności miernika. Przedział ufności nie
obejmuje błędu systematycznego miernika ani błędu założonego napięcia.
Statystyki są grupowane osobno według konfiguracji, napięcia, próbkowania,
przedziału analizy, opisu warunków i identyfikacji miernika/firmware.
Jeśli katalog zawiera różne napięcia, Hz lub zakresy czasu, skrypt zapisze
tabele CSV, ale pominie wspólne wykresy, aby nie porównywać różnych warunków.

## Brakujące dane i problemy

Wartości prądu są dekodowane zgodnie z UM3291, np. 6409-07 = 640,9 µA.
Próbki nie mają znaczników czasu: czas wynika z indeksu i ustawionego Hz.
Jeżeli firmware zgłosi RecID (kalibracja/przepełnienie), skrypt
konserwatywnie oznacza cały pomiar invalid. Nie wypełnia braków i nie
liczy z takiego przebiegu energii. Dane i komunikat zostają zachowane,
a seria zatrzymuje się do wyjaśnienia problemu.
Do pierwszych testów użyj 1000 Hz. Szybsze próbkowanie, np. --hz 10000,
lepiej pokazuje krótkie impulsy, lecz wymaga sprawnego odbioru danych.
Wszystkie porównywane konfiguracje mierz z tym samym próbkowaniem.

Brak ACK: sprawdź właściwy port SMU, zamknięty CubeMonitor-Power,
sterownik i firmware. Wyślij do analizy metadata.json, commands.json
i stream.bin z nieudanego testu. Przy błędzie przed pierwszym pomiarem
zapisuje się last_commands.json. Skrypt nie aktualizuje firmware.

## Sprawdzenie bez sprzętu

```powershell
py stlink_measure.py demo
py -m unittest -v test_stlink_measure.py
```

DEMO tworzy oznaczone dane syntetyczne i przykładowe wykresy.
Nie są to przewidywane ani zmierzone wartości NodeMCU.

Sprawdzono lokalnie dekodowanie, obliczenia, generowanie raportów i
symulowaną sesję transmisji. Testy automatyczne nie potwierdzają poprawności fizycznego stanowiska.
Pierwszy 15-sekundowy test jest konieczny przed długą serią.

Źródło protokołu: ST UM3291, API 1, rozdziały 1, 2.1 i 2.4.1:
https://www.st.com/resource/en/user_manual/um3291-getting-started-with-stlinkv3pwr-firmware-stmicroelectronics.pdf
