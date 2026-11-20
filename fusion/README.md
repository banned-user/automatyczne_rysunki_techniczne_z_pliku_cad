# Rysunek z otwartego modelu (skrypt Fusion)

Skrypt uruchamiany w Autodesk Fusion na Windows. Bierze model, który jest już otwarty, także niezapisany „(Niezapisany)”, składa rysunek i zapisuje jeden PDF. Nie importuje STEP, nie sprawdza aktywnego projektu i nie zapisuje dokumentu. Nie dotyka aplikacji FreeCAD w tym repozytorium. Nie robi DXF, przekrojów, tolerancji geometrycznych ani listy części.

Folder do skopiowania to `fusion/RysunekZeStep`. Nazwa folderu, pliku `.py` i pliku `.manifest` musi być taka sama: `RysunekZeStep`.

## Instalacja na Windows

Aktualna pomoc API (strona „Creating a Script or Add-In”) podaje dwa katalogi, które Fusion przeszukuje:

- domyślny dla nowych skryptów: `%APPDATA%\Autodesk\Autodesk Fusion\API\Scripts`
- starszy, nadal przeszukiwany: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\Scripts`

`%APPDATA%` to zwykle `C:\Users\<konto>\AppData\Roaming`. Artykuł Autodesk z 29 października 2026 nadal podaje ścieżkę z „Fusion 360”. Na dysku może istnieć jeden z tych katalogów albo oba. Włóż folder `RysunekZeStep` do tego, który jest. Po skopiowaniu ścieżka wygląda tak:

`%APPDATA%\Autodesk\Autodesk Fusion\API\Scripts\RysunekZeStep\RysunekZeStep.py`

albo

`%APPDATA%\Autodesk\Autodesk Fusion 360\API\Scripts\RysunekZeStep\RysunekZeStep.py`

Potem uruchom Fusion od nowa. Skrypt sam pojawia się na liście.

Jeśli folder leży gdzie indziej: **Utilities → Scripts and Add-Ins → Scripts → zielony plus** i wskaż plik `RysunekZeStep.py`. Fusion zapamiętuje to wskazanie.

To jest skrypt (zakładka Scripts, przycisk Run), nie dodatek ładowany przy starcie. Okno jest dialogiem polecenia (`CommandInputs`), bo zwykłe `input()` nie daje list.

## Jak uruchomić

1. Otwórz model w Fusion. Może być niezapisany.
2. **Utilities → Scripts and Add-Ins**.
3. Zakładka **Scripts**.
4. **RysunekZeStep** → **Run**.
5. Wybierz liczbę rzutów, szczegółowość i arkusz, potem OK.
6. Po OK skrypt robi rysunek z tego modelu. PDF pyta o miejsce, gdy dokument nie ma lokalnej ścieżki. Na końcu pojawia się okno ze ścieżką PDF.

Gdy nie ma otwartego modelu, skrypt pokazuje okno i kończy pracę, zanim pojawi się dialog opcji.

## Opcje

**Liczba rzutów.**

- 1 — sam przód.
- 2 — przód i góra nad przodem.
- 3 — przód, góra nad nim, prawy na prawo od przodu.
- 4 — te trzy oraz izometria z prawej strony, w górnym pasie.

To układ trzeciego kąta ustawiony współrzędnymi środka każdego rzutu. API umie dodać tylko widok bazowy (`Views.add` / `BaseViewInput`), nie rzut pochodny od innego widoku. Kąt rzutowania dokumentu (`DocumentSettings.projectionAngle`) jest tylko do odczytu. Norma ISO w tym API jest opisana jako pierwszy kąt, a formatki A2–A4 działają tylko przy normie ISO, nie ASME. Dlatego skrypt robi rysunek ISO i sam kładzie widoki bazowe tak, jak w trzecim kącie. Flaga dokumentu może nadal mówić „pierwszy kąt”; końcowe okno wypisuje, co udało się odczytać.

**Szczegółowość.**

- Kontur — styl `VisibleEdgesDrawingViewStyleType` i krawędzie styczne wyłączone (`OffTangentEdgeDisplayType`). Zostają widoczne krawędzie ostre.
- Krawędzie widoczne — ten sam styl widocznych krawędzi oraz styczne na pełnej długości (`FullLengthTangentEdgeDisplayType`). Bez krawędzi ukrytych.
- Widoczne i ukryte — styl `VisibleAndHiddenEdgesDrawingViewStyleType` (opis w dokumentacji: krawędzie widoczne i ukryte, kreskowe) plus styczne na pełnej długości. Dodatkowo `DocumentSettings.viewSettings.hiddenLineLineType` ustawiane jest na `LineTypes.HiddenLineType`. Domyślna wartość tej właściwości to linia ciągła, więc sam styl mógłby nie dać kresek. Nie ustawiam `Hidden2LineType` (osobny wzór HIDDEN2).

Krawędzie interferencji i gwintu zostają przy domyślnej wartości API. Skrypt nie wyłącza interferencji, żeby prosty model nie stracił krawędzi.

**Arkusz.** A4, A3 albo A2, zawsze poziomo (`LandscapeSheetOrientationType`). Pionowa orientacja nie jest w oknie. Jednostki rysunku: milimetry.

Skala jest jedna dla wszystkich rzutów, z szeregu 100:1 … 1:1 … 1:2, 1:5, 1:10, aż do 1:10000. Wybierana jest największa, przy której rzuty mieszczą się w siatce z marginesem (bok ok. 1,5 cm, dół ok. 5 cm pod tabelkę). Punkt wstawienia jest w centymetrach, początek w lewym dolnym rogu.

Dokumentacja podaje kierunek tylko dla przodu: patrzenie wzdłuż ujemnej osi Z, więc przód pokazuje osie X i Y, ale nie mówi, która jest pozioma. Dla góry i prawego rzutu nie podaje osi. Skala jest liczona ostrożnie: rzut prostokątny rezerwuje największy wymiar modelu w obu kierunkach (przód: większy z X i Y), izometria rezerwuje przekątną przestrzenną prostopadłościanu. Rysunek może mieć więcej pustego miejsca niż przy idealnym dopasowaniu. Tego nie sprawdzono w Fusion.

PDF idzie obok dokumentu tylko wtedy, gdy Fusion poda lokalną ścieżkę. Dokument w chmurze i „(Niezapisany)” jej nie mają, więc skrypt pyta, gdzie zapisać PDF. Grubości linii są włączone, PDF nie otwiera się sam.

## Ograniczenia API

Całe API rysunku jest oznaczone jako podgląd (wersje od lipca do października 2026). Autodesk pisze, że może się zmienić i nie należy na nim opierać programu oddawanego klientom. Innej, stabilnej metody wstawienia rzutów w tej pomocy nie ma.

- Okno zostaje po powrocie z `run()` (`autoTerminate(False)` i uchwyty trzymane w zmiennych globalnych). Pętla `doEvents` w `run()` zamykała to okno od razu. Po OK osobny wątek woła `fireCustomEvent`, a rysunek i PDF idą na głównym wątku, gdy polecenie już nie żyje. Komunikat o przedwczesnym zamknięciu nie jest pokazywany: inny powód zakończenia polecenia (błąd OK, wywłaszczenie) nie zamyka skryptu i nie zasłania dialogu.
- Pomoc `createDrawingInput` opisuje argument jako `DataFile`. Skrypt podaje `dataFile` otwartego dokumentu, gdy Fusion je już ma, a w przeciwnym razie sam otwarty dokument. Nie woła `save`, `saveAs` ani `activeProject`. Gdy to wywołanie się nie uda, okno z błędem pojawia się po zamknięciu dialogu opcji.
- Nie ma tworzenia rzutu pochodnego, więc nie da się oddać układu trzeciego kąta samej fladze dokumentu.
- Nie da się ustawić kąta rzutowania.
- Tabelka: `TitleBlockAttributeParameter` ma nazwę i pozycję, nie treść. Jedyny znacznik podany w pomocy to `SCALE`. Skrypt nie wymyśla znaczników na nazwę pliku, numer arkusza ani datę. Zostawia tabelkę nowego rysunku ISO i, jeśli pola SCALE nie ma, próbuje je dodać. Szkic rysunkowy nie ma tekstu, tylko geometrię.
- Arkusz powstaje tylko w `AutomaticDrawingCreationMode` (`CreateDrawingInput.creationMode`, domyślnie ten tryb). Pomoc nie ma osobnego typu `DrawingCreationOptions`. Tryb z placeholderami nie jest ustawiany. Gdyby `createDrawing` i tak zgłosiło błąd 3, komunikat wypisuje tryb odczytany z wejścia. Automatyczny arkusz części bywa samą ramką i tabelką. Skrypt czeka, aż polecenie automatyzacji zejdzie, ustawia wybrany format poziomo i sam dokłada widoki bazowe (przód, góra nad nim, prawy z prawej, izometria z boku). API nie usuwa rzutów, więc rzuty, które automatyzacja już wstawiła, zostają.
- Styl, skala i krawędzie styczne są ustawiane na `ViewParameters` przed `Views.add`. Gotowego rzutu skrypt nie czyta: `view.style` (`get_style`) rzuca `failed to read view style` i ten odczyt zdejmował rzut z arkusza. PDF powstaje dopiero wtedy, gdy każdy żądany rzut ma krzywe modelu (`viewCurves`).
- Wymiary gabarytowe idą na rzuty prostokątne, nie na izometrię. Najpierw `Sheet.autoDimension` ze strategią `OverallDimensionStrategyType`. Gdy to nic nie doda, skrypt bierze skrajne punkty `viewCurves` i woła `DrawingDimensions.addLinearDimension`.
- Ukryte kreski zależą od stylu widoku i od `hiddenLineLineType`. Wyglądu kresek (kreska krótka czy długa) nie sprawdzono na wydruku.
- `Sheet.width` / `Sheet.height` nie podają jednostki. Skrypt poznaje mm, cm albo cale po porównaniu z wymiarem A4/A3/A2. Punkt rzutu jest w centymetrach, jak w opisie `placementPoint`.

## Czego nie sprawdzono

Na maszynie, na której powstał ten skrypt, nie ma Fusion i nie ma modułu `adsk`. Skrypt nie był uruchomiony w Fusion, także na pliku przykładowym. Sprawdzono tylko składnię Pythona (`python3 -m py_compile`) oraz liczenie skali i siatki rzutów poza Fusion.

Próbka `samples/box_with_hole.step` jest na gałęzi `cursor/step-drawing-pdf-982f`, nie na `main`. Nie została skopiowana, bo Fusion i tak nie mógł jej otworzyć.

Nazwy wywołań są z pomocy otwartej przy pisaniu skryptu, między innymi:

- [Creating a Script or Add-In](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/WritingDebugging_UM.htm)
- [Command Inputs](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CommandInputs_UM.htm)
- [Command Inputs API Sample](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CommandInputsSample_Sample.htm)
- [FileDialog](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_FileDialog.htm)
- [Application.activeDocument](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Application_activeDocument.htm)
- [DrawingManager.createDrawingInput](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_DrawingManager_createDrawingInput.htm)
- [DrawingManager.get](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_DrawingManager_get.htm)
- [Create Automatic Drawing Sample](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CreateAutomaticDrawingSample_Sample.htm)
- [Views.add](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_Views_add.htm)
- [BaseViewInput](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_BaseViewInput.htm)
- [ViewParameters](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_ViewParameters.htm)
- [ViewOrientationTypes](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_ViewOrientationTypes.htm)
- [DrawingViewStyleTypes](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_DrawingViewStyleTypes.htm)
- [TangentEdgeDisplayTypes](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_TangentEdgeDisplayTypes.htm)
- [LineTypes](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_LineTypes.htm)
- [SheetSizes](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_SheetSizes.htm)
- [Export PDF Sample](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ExportPDFSample_Sample.htm)
- [TitleBlock.setAttributes](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_TitleBlock_setAttributes.htm)
- [Sheet.autoDimension](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_Sheet_autoDimension.htm)
- [DrawingDimensions.addLinearDimension](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_DrawingDimensions_addLinearDimension.htm)
- [View](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/drawing_View.htm)
- [Working in a Separate Thread](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Threading_UM.htm)
