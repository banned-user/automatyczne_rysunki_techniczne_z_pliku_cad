# Rysunek ze STEP (skrypt Fusion)

Skrypt uruchamiany w Autodesk Fusion na Windows. Wczytuje plik STEP, zakłada nowy model, składa rysunek i zapisuje jeden PDF obok pliku STEP. Nie dotyka aplikacji FreeCAD w tym repozytorium. Nie robi DXF, przekrojów, tolerancji geometrycznych ani listy części.

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

To jest skrypt (zakładka Scripts, przycisk Run), nie dodatek ładowany przy starcie. Okno jest dialogiem polecenia (`CommandInputs`), bo zwykłe `input()` nie daje list. W API nie ma pola pliku wewnątrz dialogu polecenia, więc obok „Plik STEP” jest przycisk otwierający `FileDialog`.

## Jak uruchomić

1. **Utilities → Scripts and Add-Ins**.
2. Zakładka **Scripts**.
3. **Rysunek ze STEP** → **Run**.
4. Wybierz plik, opcje i OK.
5. Po OK skrypt importuje STEP, zapisuje model do aktywnego projektu Fusion i dopiero wtedy robi rysunek. Na końcu pojawia się okno ze ścieżką PDF.

Model musi trafić do chmury: `DrawingManager.createDrawing` bierze `DataFile`, a nie otwarty, niezapisany dokument. Trzeba być zalogowanym i mieć aktywny projekt. Oficjalny przykład Autodesk mówi to samo.

## Opcje

**Plik STEP.** Przycisk „Wybierz plik” otwiera okno plików. Przyjmowane są `.step` i `.stp`. Ścieżka w polu jest tylko do odczytu.

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

Krawędzie interferencji są wyłączone (`isShowInterferenceEdges = False`). Krawędzie gwintu zostają przy domyślnej wartości API (włączone).

**Arkusz.** A4, A3 albo A2, zawsze poziomo (`LandscapeSheetOrientationType`). Pionowa orientacja nie jest w oknie. Jednostki rysunku: milimetry.

Skala jest jedna dla wszystkich rzutów, z szeregu 100:1 … 1:1 … 1:2, 1:5, 1:10, aż do 1:10000. Wybierana jest największa, przy której rzuty mieszczą się w siatce z marginesem (bok ok. 1,5 cm, dół ok. 5 cm pod tabelkę). Punkt wstawienia jest w centymetrach, początek w lewym dolnym rogu.

Dokumentacja podaje kierunek tylko dla przodu: patrzenie wzdłuż ujemnej osi Z, więc przód pokazuje osie X i Y, ale nie mówi, która jest pozioma. Dla góry i prawego rzutu nie podaje osi. Skala jest liczona ostrożnie: rzut prostokątny rezerwuje największy wymiar modelu w obu kierunkach (przód: większy z X i Y), izometria rezerwuje przekątną przestrzenną prostopadłościanu. Rysunek może mieć więcej pustego miejsca niż przy idealnym dopasowaniu. Tego nie sprawdzono w Fusion.

PDF powstaje obok STEP, z tą samą nazwą i rozszerzeniem `.pdf`. Gdy zapis się nie uda, skrypt pyta o inne miejsce. Grubości linii są włączone, PDF nie otwiera się sam.

## Ograniczenia API

Całe API rysunku jest oznaczone jako podgląd (wersje od lipca do października 2026). Autodesk pisze, że może się zmienić i nie należy na nim opierać programu oddawanego klientom. Innej, stabilnej metody wstawienia rzutów w tej pomocy nie ma.

- Brak pola pliku w `CommandInputs`. Jest lista, pole tekstowe i przycisk oraz osobne `UserInterface.createFileDialog`.
- Import i zapis dokumentu nie mogą iść wewnątrz zdarzenia polecenia. Skrypt nie wraca z `run()`, dopóki okno jest otwarte (`adsk.doEvents`), i importuje STEP dopiero po zamknięciu OK. Wcześniejsze `fireCustomEvent` po powrocie z `run()` w ogóle nie startowało pracy. Otwarty dokument „(Niezapisany)” nie jest plikiem źródłowym. Brak aktywnego projektu Fusion jest zgłaszany w oknie, zanim się zamknie.
- Rysunek wymaga modelu zapisanego w chmurze (`saveAs` do katalogu głównego aktywnego projektu, potem `dataFile`).
- Nie ma tworzenia rzutu pochodnego, więc nie da się oddać układu trzeciego kąta samej fladze dokumentu.
- Nie da się ustawić kąta rzutowania.
- Tabelka: `TitleBlockAttributeParameter` ma nazwę i pozycję, nie treść. Jedyny znacznik podany w pomocy to `SCALE`. Skrypt nie wymyśla znaczników na nazwę pliku, numer arkusza ani datę. Zostawia tabelkę nowego rysunku ISO i, jeśli pola SCALE nie ma, próbuje je dodać. Szkic rysunkowy nie ma tekstu, tylko geometrię.
- Nie ma usuwania rzutu. Tryb ręczny (`ManualDrawingCreationMode`) powinien dać pusty arkusz. Gdyby rzuty już były, skrypt dopisze swoje i napisze o tym w oknie.
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
- [ImportManager.importToNewDocument](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_ImportManager_importToNewDocument.htm)
- [ImportManager.createSTEPImportOptions](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_ImportManager_createSTEPImportOptions.htm)
- [Document.saveAs](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Document_saveAs.htm)
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
- [Working in a Separate Thread](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Threading_UM.htm)
