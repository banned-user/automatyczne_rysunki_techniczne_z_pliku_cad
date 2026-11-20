# Rysunek techniczny ze STEP

Prosta aplikacja: plik STEP wchodzi, PDF z rzutami wychodzi. To nie jest system CAD.
Nie ma DXF, przekrojów, GD&T ani listy części.

The same instructions in English are at the bottom.

## Co robi

1. Wgrywasz plik `.step` lub `.stp`.
2. Wybierasz liczbę rzutów, szczegółowość i arkusz.
3. Dostajesz jeden poziomy PDF. Skala jest dobierana tak, żeby rzuty zmieściły się na arkuszu z marginesem.
4. Tabelka rysunkowa zawiera nazwę pliku, rozmiar arkusza, skalę i datę.

Rzutowanie jest amerykańskie (third angle), zgodnie z układem z opisu narzędzia:

| Liczba rzutów | Układ |
| --- | --- |
| 1 | przód |
| 2 | przód oraz góra nad przodem |
| 3 | te dwa oraz prawy z prawej strony przodu |
| 4 | te trzy oraz izometria z boku |

Szczegółowość:

| Opcja | Krawędzie |
| --- | --- |
| Kontur | tylko widoczne ostre krawędzie |
| Krawędzie widoczne | ostre i gładkie krawędzie widoczne, bez linii ukrytych |
| Widoczne i ukryte | krawędzie widoczne oraz kreskowe linie ukryte |

Arkusz: A4, A3 albo A2, zawsze poziomo. Szablon to wbudowany arkusz FreeCAD `ISO5457` minimal w danym formacie. Symbol metody europejskiej (first angle) jest z tego szablonu usuwany, bo rzuty są ułożone odwrotnie.

Złożenie z wielu brył jest scalane w jedną kształt (`multiFuse`). Gdy scalenie się nie uda, bryły trafiają do jednego złożenia (`compound`) i powstaje jeden rysunek.

## Wymagania

Sprawdzone na Ubuntu 24.04. W repozytoriach Ubuntu 24.04 nie ma pakietu `freecad`, więc używamy oficjalnego AppImage **FreeCAD 1.1.4** oraz `xvfb` (TechDraw eksportuje PDF przez moduł GUI; samo `freecadcmd` w tej kompilacji nie ładuje `TechDrawGui`).

Suma kontrolna AppImage:

```text
f6dc6ba676e5ac96a565ebc8d657232f94c6158e85b4352141bd1a46f6b43434  FreeCAD_1.1.4-Linux-x86_64-py311.AppImage
```

Python 3.12, pakiety z `requirements.txt` (FastAPI 0.128.8, uvicorn 0.40.0, python-multipart 0.0.20).

## Instalacja FreeCAD 1.1.4

```bash
sudo apt-get update
sudo apt-get install -y xvfb ca-certificates curl
sudo mkdir -p /opt/freecad
cd /tmp
curl -fL -o FreeCAD_1.1.4-Linux-x86_64-py311.AppImage \
  https://github.com/FreeCAD/FreeCAD/releases/download/1.1.4/FreeCAD_1.1.4-Linux-x86_64-py311.AppImage
echo "f6dc6ba676e5ac96a565ebc8d657232f94c6158e85b4352141bd1a46f6b43434  FreeCAD_1.1.4-Linux-x86_64-py311.AppImage" | sha256sum -c
chmod +x FreeCAD_1.1.4-Linux-x86_64-py311.AppImage
sudo mv FreeCAD_1.1.4-Linux-x86_64-py311.AppImage /opt/freecad/
cd /opt/freecad
sudo ./FreeCAD_1.1.4-Linux-x86_64-py311.AppImage --appimage-extract
```

Program używany przez serwer:

```bash
export FREECAD_BIN=/opt/freecad/squashfs-root/usr/bin/freecad
```

`freecadcmd` z tego samego katalogu służy do zadań bez GUI, na przykład do wygenerowania przykładowego STEP.

## Uruchomienie serwera

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export FREECAD_BIN=/opt/freecad/squashfs-root/usr/bin/freecad
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Otwórz `http://127.0.0.1:8000`. Formularz jest po polsku: plik STEP, liczba rzutów, szczegółowość, arkusz, przycisk „Generuj PDF”. Odpowiedź to pobranie pliku PDF.

Przykład bez przeglądarki, na pliku z katalogu `samples/`:

```bash
curl -sS -D - -o /tmp/rysunek.pdf \
  -F "file=@samples/box_with_hole.step;filename=box_with_hole.step" \
  -F "views=3" \
  -F "detail=hidden" \
  -F "sheet=A4" \
  http://127.0.0.1:8000/generuj
```

Nagłówek odpowiedzi zawiera `application/pdf`.

## Przykładowy model

`samples/box_with_hole.step` to prostopadłościan 80 × 50 × 30 mm z przelotowym otworem o średnicy 16 mm. Można go odtworzyć:

```bash
SAMPLE_OUT="$PWD/samples/box_with_hole.step" \
  /opt/freecad/squashfs-root/usr/bin/freecadcmd scripts/make_sample_step.py
```

## English

Upload a `.step` or `.stp` file, choose 1–4 views, a detail level, and an A4/A3/A2 landscape sheet. The server writes the upload to a temporary file and runs FreeCAD 1.1.4 headless (`freecad` under `xvfb-run`, because this build's `freecadcmd` cannot load TechDrawGui). TechDraw places the views, fits a standard scale, and exports a vector PDF.

View placement is third-angle: top above front, right to the right of front, isometric off to the side. Detail levels map to TechDraw edge properties: outline is hard visible edges only, visible adds smooth edges, hidden adds dashed hidden lines (`HardHidden`).

An assembly is fused into one solid when that succeeds, otherwise kept as a single compound, and one drawing is produced.

Install FreeCAD 1.1.4 and xvfb with the commands above, then:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export FREECAD_BIN=/opt/freecad/squashfs-root/usr/bin/freecad
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```
