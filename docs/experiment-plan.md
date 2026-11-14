# Plan eksperymentu i artykułu

Roboczy tytuł: „Ile prądu kosztuje jedna linijka kodu?”.
Odbiorcy: programiści, również bez doświadczenia w embedded.

## Etapy

| Termin (2026) | Zakres | Kryterium zakończenia |
| --- | --- | --- |
| 14–15 listopada | Uruchomienie STLINK-V3PWR na NodeMCU | Powtarzalny zapis próbek i poprawne raporty |
| Od 17 listopada, po dostawie | Przygotowanie Pico 2 | Wgranie kodu i sprawdzenie zasilania oraz wybudzania |
| 18 listopada | Ocena gotowości stanowiska | Decyzja o potwierdzeniu terminu redakcji |
| Do 27 listopada, warunkowo | Pomiary docelowe i tekst | Artykuł, wykresy, kod i opis danych |

To plan, a nie potwierdzenie wykonania pomiarów ani uzgodniony termin publikacji.

## Porównanie na Pico 2

Ustalić jedno powtarzalne zadanie, jego okres i jednakowy efekt zewnętrzny.
Przygotować warianty: aktywne oczekiwanie, oczekiwanie przez funkcję opóźnienia
oraz uśpienie z wybudzaniem. Sprawdzić zachowanie wybranej biblioteki: sama
nazwa funkcji opóźnienia nie przesądza, czy CPU pozostaje aktywny.

Przed każdą serią zapisać płytkę, wersję SDK i kompilatora, opcje kompilacji,
zegar, zasilanie, firmware miernika, częstotliwość próbkowania, połączenia
i identyfikator commita. Opisać stan LED, interfejsów i drugiego rdzenia.
Trzymać te warunki stałe między wariantami.

Zebrać kilka niezależnych rejestracji dla każdego wariantu. Jawnie ustalić,
czy porównujemy rozruch, stan ustalony, czy pełne cykle z wybudzaniem.
Do energii na zadanie wyznaczyć granice pełnych cykli; samo okno 120 sekund
nie gwarantuje jednakowej liczby wykonanych zadań.

## Wyniki do tekstu

- Fragmenty kodu wykonujące to samo zadanie.
- Przebiegi prądu ze skalą czasu i zaznaczonymi fazami pracy.
- Średni prąd, energia na pełny cykl i rozrzut między rejestracjami.
- Jawne założenia szacowania czasu pracy baterii: użyteczna pojemność lub
  energia, napięcie, sprawność zasilania i pobór własny układu zasilającego.

Przy założeniu stałej użytecznej pojemności i zgodnego toru zasilania wstępne
oszacowanie to `czas [h] = pojemność [mAh] / średni prąd [mA]`.
Przy przetwornicy porównywać użyteczną energię baterii w Wh ze średnią mocą
pobieraną z baterii w W. Opisać założenia; nie przedstawiać oszacowania jako
zmierzonego czasu pracy. Obliczenia te nie są jeszcze zaimplementowane w CLI.

## Proponowany układ artykułu

1. Pytanie tytułowe i krótki przykład, dlaczego liczba linii nie wystarcza.
2. Stanowisko: płytka, miernik, połączenia i co obejmuje pomiar.
3. To samo zadanie i trzy sposoby oczekiwania.
4. Wykresy i koszt rozruchu oraz wybudzania.
5. Energia cyklu, zmienność pomiarów i oszacowanie pracy z baterii.
6. Ograniczenia eksperymentu i odnośnik do kodu oraz danych.
