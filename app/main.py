"""Small web form: STEP file in, technical-drawing PDF out.

FreeCAD is executed as a separate process. This module does not import it.
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, Response

app = FastAPI(title="Rysunek techniczny ze STEP")

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "make_drawing.py"
MAX_UPLOAD = 64 * 1024 * 1024

PAGE = """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rysunek techniczny ze STEP</title>
  <style>
    body { font-family: sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; color: #1c1c1c; }
    h1 { font-size: 1.4rem; }
    form { display: grid; gap: 0.9rem; margin-top: 1.2rem; }
    label { font-weight: 600; }
    select, input[type=file] { font: inherit; padding: 0.35rem; }
    button { font: inherit; padding: 0.55rem 1rem; width: fit-content; }
    .hint { margin: 0; color: #444; font-weight: 400; font-size: 0.92rem; }
    .error { background: #fde8e8; border: 1px solid #e3b4b4; padding: 0.8rem 1rem; }
  </style>
</head>
<body>
  <h1>Rysunek techniczny ze STEP</h1>
  <p>Wgraj plik STEP. Aplikacja układa rzuty na poziomym arkuszu i zwraca PDF.</p>
  {error}
  <form action="/generuj" method="post" enctype="multipart/form-data">
    <label for="file">Plik STEP</label>
    <input id="file" name="file" type="file" accept=".step,.stp,.STEP,.STP" required>

    <label for="views">Liczba rzutów</label>
    <select id="views" name="views">
      <option value="1">1 — przód</option>
      <option value="2">2 — przód i góra</option>
      <option value="3" selected>3 — przód, góra i prawy</option>
      <option value="4">4 — trzy rzuty oraz izometria</option>
    </select>

    <label for="detail">Szczegółowość</label>
    <select id="detail" name="detail">
      <option value="outline">Kontur — tylko widoczne ostre krawędzie</option>
      <option value="visible">Krawędzie widoczne — ostre i gładkie, bez linii ukrytych</option>
      <option value="hidden" selected>Widoczne i ukryte</option>
    </select>
    <p class="hint">Kontur pomija krawędzie gładkie i linie ukryte. Poziom „widoczne i ukryte” dodaje kreskowe linie ukryte.</p>

    <label for="sheet">Arkusz</label>
    <select id="sheet" name="sheet">
      <option value="A4">A4 poziomo</option>
      <option value="A3">A3 poziomo</option>
      <option value="A2">A2 poziomo</option>
    </select>

    <button type="submit">Generuj PDF</button>
  </form>
</body>
</html>
"""


def page(error=""):
    block = "<p class=\"error\">%s</p>" % escape(error) if error else ""
    return PAGE.replace("{error}", block)


def escape(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def freecad_bin():
    candidates = []
    configured = os.environ.get("FREECAD_BIN")
    if configured:
        candidates.append(Path(configured))
    for name in ("freecad", "FreeCAD"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    candidates.append(Path("/opt/freecad/squashfs-root/usr/bin/freecad"))
    expanded = []
    for candidate in candidates:
        expanded.append(candidate)
        if candidate.name.lower() in {"freecadcmd", "freecadcmd.exe"}:
            expanded.append(candidate.with_name("freecad"))
    for candidate in expanded:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            if candidate.name.lower() not in {"freecadcmd", "freecadcmd.exe"}:
                return candidate
    return None


def fontconfig_file(usr, destination):
    directories = []
    for relative in ("share/Mod/TechDraw/Resources/fonts", "fonts"):
        path = usr / relative
        if path.is_dir():
            directories.append(path)
    lines = [
        '<?xml version="1.0"?>',
        '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">',
        "<fontconfig>",
        '  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>',
    ]
    lines.extend("  <dir>%s</dir>" % path for path in directories)
    lines.append("</fontconfig>")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ascii_download_name(filename):
    stem = Path(filename or "rysunek").stem
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "rysunek"
    return cleaned[:80] + ".pdf"


@app.get("/", response_class=HTMLResponse)
def index():
    return page()


@app.post("/generuj")
async def generuj(
    file: UploadFile = File(...),
    views: str = Form(...),
    detail: str = Form(...),
    sheet: str = Form(...),
):
    error = validate(file, views, detail, sheet)
    if error:
        return HTMLResponse(page(error), status_code=400)

    binary = freecad_bin()
    if binary is None:
        return HTMLResponse(
            page("Nie znaleziono programu FreeCAD. Ustaw FREECAD_BIN albo zainstaluj go według README."),
            status_code=500,
        )
    if shutil.which("xvfb-run") is None:
        return HTMLResponse(
            page("Brak programu xvfb-run. Zainstaluj pakiet xvfb."),
            status_code=500,
        )

    payload = await file.read()
    if not payload:
        return HTMLResponse(page("Plik STEP jest pusty."), status_code=400)
    if len(payload) > MAX_UPLOAD:
        return HTMLResponse(page("Plik STEP jest za duży (limit 64 MB)."), status_code=400)

    with tempfile.TemporaryDirectory(prefix="rysunek-") as temporary:
        work = Path(temporary)
        step_path = work / "model.step"
        pdf_path = work / "rysunek.pdf"
        error_path = work / "error.txt"
        step_path.write_bytes(payload)
        (work / "config").mkdir()
        (work / "data").mkdir()
        (work / "cache").mkdir()
        fonts = work / "fonts.conf"
        usr = binary.parent.parent
        fontconfig_file(usr, fonts)

        env = os.environ.copy()
        env.update(
            {
                "QT_QPA_PLATFORM": "xcb",
                "LIBGL_ALWAYS_SOFTWARE": "1",
                "FONTCONFIG_FILE": str(fonts),
                "XDG_CONFIG_HOME": str(work / "config"),
                "XDG_DATA_HOME": str(work / "data"),
                "XDG_CACHE_HOME": str(work / "cache"),
                "DRAW_INPUT": str(step_path),
                "DRAW_OUTPUT": str(pdf_path),
                "DRAW_VIEWS": views,
                "DRAW_DETAIL": detail,
                "DRAW_SHEET": sheet,
                "DRAW_NAME": file.filename or "model.step",
                "DRAW_ERROR": str(error_path),
            }
        )
        plugins = usr / "lib" / "qt6" / "plugins"
        if plugins.is_dir():
            env["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugins)
            env["QT_PLUGIN_PATH"] = str(plugins)

        command = [
            "xvfb-run",
            "-a",
            "-s",
            "-screen 0 1400x900x24",
            str(binary),
            str(SCRIPT),
        ]
        try:
            completed = subprocess.run(
                command,
                env=env,
                capture_output=True,
                timeout=180,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return HTMLResponse(
                page("Generowanie trwało zbyt długo i zostało przerwane."),
                status_code=500,
            )

        if completed.returncode != 0 or not pdf_path.is_file():
            message = error_path.read_text(encoding="utf-8").strip() if error_path.is_file() else ""
            if not message:
                message = "FreeCAD nie utworzył rysunku."
            return HTMLResponse(page(message), status_code=500)

        data = pdf_path.read_bytes()
        if not data.startswith(b"%PDF"):
            return HTMLResponse(page("Wynik nie jest plikiem PDF."), status_code=500)

        filename = ascii_download_name(file.filename)
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
        )


def validate(file, views, detail, sheet):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".step", ".stp"}:
        return "Wybierz plik STEP (.step lub .stp)."
    if views not in {"1", "2", "3", "4"}:
        return "Liczba rzutów musi być od 1 do 4."
    if detail not in {"outline", "visible", "hidden"}:
        return "Nieprawidłowa szczegółowość."
    if sheet not in {"A4", "A3", "A2"}:
        return "Arkusz musi być A4, A3 albo A2."
    return ""
