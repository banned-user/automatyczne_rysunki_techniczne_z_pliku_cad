"""Build one TechDraw page from a STEP file and export a vector PDF.

FreeCAD runs this file. The web app passes options through the environment
and never imports FreeCAD itself.

Views are placed in third-angle arrangement, as requested: top above the
front view, the right view to the right of the front view, and the isometric
view off to the side. The stock ISO 5457 sheet includes a static first-angle
symbol; that graphic is removed so the sheet does not contradict the views.
"""

import os
import re
import sys
import time


def log(message):
    path = os.environ.get("DRAW_LOG")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def fail(message):
    path = os.environ.get("DRAW_ERROR")
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(message)
    sys.stderr.write("ERROR: %s\n" % message)
    os._exit(1)


def main():
    try:
        import FreeCAD as App
        import FreeCADGui as Gui
        import TechDrawGui
    except Exception as exc:
        fail("Nie można załadować TechDraw: %s" % exc)

    step_path = os.environ.get("DRAW_INPUT", "")
    pdf_path = os.environ.get("DRAW_OUTPUT", "")
    if not step_path or not pdf_path:
        fail("Brak ścieżki pliku wejściowego lub PDF.")
    if not os.path.isfile(step_path):
        fail("Nie znaleziono pliku STEP.")

    try:
        view_count = int(os.environ.get("DRAW_VIEWS", "3"))
    except ValueError:
        fail("Nieprawidłowa liczba rzutów.")
    if view_count not in (1, 2, 3, 4):
        fail("Liczba rzutów musi być od 1 do 4.")

    detail = os.environ.get("DRAW_DETAIL", "hidden")
    if detail not in DETAIL:
        fail("Nieprawidłowa szczegółowość: %s" % detail)

    sheet = os.environ.get("DRAW_SHEET", "A4")
    if sheet not in SHEETS:
        fail("Nieprawidłowy arkusz: %s" % sheet)

    title = os.path.basename(os.environ.get("DRAW_NAME") or step_path)
    log("start %s views=%s detail=%s sheet=%s" % (title, view_count, detail, sheet))

    try:
        Gui.activateWorkbench("TechDrawWorkbench")
    except Exception as exc:
        fail("Nie można uruchomić środowiska TechDraw: %s" % exc)

    shape = load_shape(step_path)
    doc = App.newDocument("rysunek")
    part = doc.addObject("Part::Feature", "Part")
    part.Shape = shape

    template_file = prepare_template(sheet)
    page = doc.addObject("TechDraw::DrawPage", "Page")
    template = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
    template.Template = template_file
    page.Template = template
    page.ProjectionType = "Third angle"

    views = add_views(doc, page, part, view_count, detail)
    log("views created")
    doc.recompute()
    log("recomputed")
    wait_for_edges(views)
    log("edges ready")

    sizes = {name: measure(view) for name, view in views.items()}
    scale = fit_scale(sizes, sheet)
    place_views(views, sizes, scale, sheet)
    page.Scale = scale

    for view in views.values():
        view.LockPosition = True

    log("placed scale=%s" % format_scale(scale))
    page.ViewObject.show()
    fill_title_block(template, title, sheet, scale)
    doc.recompute()
    settle()

    write_stats(views, scale)
    svg_path = os.environ.get("DRAW_SVG")
    if svg_path:
        TechDrawGui.exportPageAsSvg(page, svg_path)

    log("export")
    try:
        TechDrawGui.exportPageAsPdf(page, pdf_path)
    except Exception as exc:
        fail("Eksport PDF nie powiódł się: %s" % exc)

    if not os.path.isfile(pdf_path) or os.path.getsize(pdf_path) < 1000:
        fail("Eksport PDF nie utworzył pliku.")
    with open(pdf_path, "rb") as handle:
        if not handle.read(5).startswith(b"%PDF"):
            fail("Eksport nie zwrócił pliku PDF.")
    os._exit(0)


DETAIL = {
    "outline": {
        "HardHidden": False,
        "SmoothVisible": False,
        "SmoothHidden": False,
        "SeamVisible": False,
        "SeamHidden": False,
        "IsoVisible": False,
        "IsoHidden": False,
    },
    "visible": {
        "HardHidden": False,
        "SmoothVisible": True,
        "SmoothHidden": False,
        "SeamVisible": False,
        "SeamHidden": False,
        "IsoVisible": False,
        "IsoHidden": False,
    },
    "hidden": {
        "HardHidden": True,
        "SmoothVisible": True,
        "SmoothHidden": False,
        "SeamVisible": False,
        "SeamHidden": False,
        "IsoVisible": False,
        "IsoHidden": False,
    },
}

# Usable rectangle on the landscape sheet, in millimetres, origin at the
# bottom-left. The box stays inside the border and above the title block.
SHEETS = {
    "A4": {"box": (24.0, 68.0, 283.0, 196.0), "page": (297.0, 210.0)},
    "A3": {"box": (24.0, 68.0, 406.0, 283.0), "page": (420.0, 297.0)},
    "A2": {"box": (24.0, 68.0, 580.0, 406.0), "page": (594.0, 420.0)},
}

VIEW_ORDER = ("front", "top", "right", "iso")

# Directions copied from TechDraw's third-angle DrawProjGroup.
VIEW_DIRECTIONS = {
    "front": ((0, -1, 0), (1, 0, 0)),
    "top": ((0, 0, 1), (1, 0, 0)),
    "right": ((1, 0, 0), (0, 1, 0)),
    "iso": ((1, -1, 1), (1, 1, 0)),
}

# Largest scale first. The value is paper size divided by model size.
NICE_SCALES = (
    100, 50, 20, 10, 5, 2, 1,
    0.5, 0.2, 0.1, 0.05, 0.02, 0.01,
    0.005, 0.002, 0.001,
)

GAP = 12.0


def load_shape(path):
    import Part

    try:
        shape = Part.read(path)
    except Exception as exc:
        fail("Nie udało się wczytać pliku STEP: %s" % exc)
    if shape is None or getattr(shape, "isNull", lambda: True)():
        fail("Pusty model: plik STEP nie zawiera geometrii.")

    solids = [solid for solid in shape.Solids if solid is not None and not solid.isNull()]
    if not solids:
        if shape.Faces:
            return shape
        fail("Pusty model: plik STEP nie zawiera bryły.")
    if len(solids) == 1:
        return solids[0]
    try:
        fused = solids[0].multiFuse(solids[1:])
        try:
            fused = fused.removeSplitter()
        except Exception:
            pass
        if fused is None or fused.isNull() or not fused.Solids:
            raise RuntimeError("puste scalenie")
        return fused
    except Exception:
        # Interfering or non-manifold assemblies still become one drawing.
        return Part.makeCompound(solids)


def resource_template(sheet):
    import FreeCAD as App

    filename = "%s_Landscape_ISO5457_minimal.svg" % sheet
    roots = []
    resource = App.getResourceDir()
    if resource:
        roots.append(resource)
        roots.append(os.path.join(resource, "share"))
    roots.append("/opt/freecad/squashfs-root/usr/share")
    relative = os.path.join("Mod", "TechDraw", "Templates", "ISO", filename)
    for root in roots:
        candidate = os.path.join(root, relative)
        if os.path.isfile(candidate):
            return candidate
    fail("Brak wbudowanego szablonu TechDraw dla arkusza %s." % sheet)


def prepare_template(sheet):
    source = resource_template(sheet)
    text = open(source, encoding="utf-8").read()
    # The built-in sheet draws a first-angle projection symbol. Views on this
    # page are third-angle, so the symbol would be wrong.
    text = re.sub(
        r"<(?:path|circle) id=\"first_angle_[^\"]*\"[^>]*/>\s*",
        "",
        text,
    )
    destination = os.path.join(
        os.path.dirname(os.environ.get("DRAW_OUTPUT", "/tmp/out.pdf")),
        "template_%s.svg" % sheet,
    )
    with open(destination, "w", encoding="utf-8") as handle:
        handle.write(text)
    return destination


def unit(components):
    import FreeCAD as App

    vector = App.Vector(*components)
    vector.normalize()
    return vector


def add_views(doc, page, part, view_count, detail):
    flags = DETAIL[detail]
    views = {}
    for name in VIEW_ORDER[:view_count]:
        direction, x_direction = VIEW_DIRECTIONS[name]
        view = doc.addObject("TechDraw::DrawViewPart", name)
        page.addView(view)
        view.Source = [part]
        view.Direction = unit(direction)
        view.XDirection = unit(x_direction)
        view.ScaleType = "Custom"
        view.Scale = 1.0
        view.X = 100.0
        view.Y = 100.0
        for prop, value in flags.items():
            setattr(view, prop, value)
        views[name] = view
    return views


def wait_for_edges(views):
    from PySide6 import QtCore

    app = QtCore.QCoreApplication.instance()
    deadline = time.time() + 90
    pending = set(views)
    while time.time() < deadline:
        if app is not None:
            app.processEvents()
        ready = [name for name in pending if list(views[name].getVisibleEdges())]
        for name in ready:
            pending.discard(name)
        if not pending:
            if app is not None:
                app.processEvents()
            return
        time.sleep(0.05)
    fail("TechDraw nie wygenerował geometrii rzutów: %s." % ", ".join(sorted(pending)))


def measure(view):
    edges = list(view.getVisibleEdges())
    if view.HardHidden:
        edges.extend(view.getHiddenEdges())
    xs = []
    ys = []
    for edge in edges:
        box = edge.BoundBox
        if box.DiagonalLength > 1e7:
            continue
        xs.extend((box.XMin, box.XMax))
        ys.extend((box.YMin, box.YMax))
    if not xs:
        fail("Rzut %s nie ma krawędzi." % view.Name)
    return max(max(xs) - min(xs), 0.01), max(max(ys) - min(ys), 0.01)


def paper_size(sizes, name, scale):
    width, height = sizes[name]
    return width * scale, height * scale


def block_size(sizes, scale):
    front_w, front_h = paper_size(sizes, "front", scale)
    stack_w = front_w
    base_h = front_h
    top_h = 0.0
    if "top" in sizes:
        top_w, top_h = paper_size(sizes, "top", scale)
        stack_w = max(stack_w, top_w)
    if "right" in sizes:
        _right_w, right_h = paper_size(sizes, "right", scale)
        base_h = max(front_h, right_h)
    ortho_w = stack_w
    ortho_h = base_h + (top_h + GAP if "top" in sizes else 0.0)
    if "right" in sizes:
        right_w, _right_h = paper_size(sizes, "right", scale)
        ortho_w = stack_w + GAP + right_w
    if "iso" not in sizes:
        return ortho_w, ortho_h
    iso_w, iso_h = paper_size(sizes, "iso", scale)
    return ortho_w + GAP + iso_w, max(ortho_h, iso_h)


def fit_scale(sizes, sheet):
    x0, y0, x1, y1 = SHEETS[sheet]["box"]
    available_w = (x1 - x0) - 8.0
    available_h = (y1 - y0) - 8.0
    chosen = NICE_SCALES[-1]
    for scale in NICE_SCALES:
        width, height = block_size(sizes, scale)
        if width <= available_w and height <= available_h:
            chosen = scale
            break
    return chosen


def place_views(views, sizes, scale, sheet):
    for view in views.values():
        view.ScaleType = "Custom"
        view.Scale = scale

    x0, y0, x1, y1 = SHEETS[sheet]["box"]
    total_w, total_h = block_size(sizes, scale)
    origin_x = x0 + ((x1 - x0) - total_w) / 2.0
    origin_y = y0 + ((y1 - y0) - total_h) / 2.0

    front_w, front_h = paper_size(sizes, "front", scale)
    stack_w = front_w
    base_h = front_h
    if "top" in views:
        stack_w = max(stack_w, paper_size(sizes, "top", scale)[0])
    if "right" in views:
        base_h = max(front_h, paper_size(sizes, "right", scale)[1])
    ortho_h = base_h + (paper_size(sizes, "top", scale)[1] + GAP if "top" in views else 0.0)
    ortho_bottom = origin_y + (total_h - ortho_h) / 2.0

    front = views["front"]
    front.X = origin_x + stack_w / 2.0
    front.Y = ortho_bottom + (base_h - front_h) / 2.0 + front_h / 2.0

    if "top" in views:
        top_w, top_h = paper_size(sizes, "top", scale)
        views["top"].X = front.X
        views["top"].Y = ortho_bottom + base_h + GAP + top_h / 2.0
    if "right" in views:
        right_w, right_h = paper_size(sizes, "right", scale)
        views["right"].X = origin_x + stack_w + GAP + right_w / 2.0
        views["right"].Y = ortho_bottom + (base_h - right_h) / 2.0 + right_h / 2.0
    if "iso" in views:
        iso_w, iso_h = paper_size(sizes, "iso", scale)
        ortho_w = total_w - GAP - iso_w
        views["iso"].X = origin_x + ortho_w + GAP + iso_w / 2.0
        views["iso"].Y = origin_y + total_h / 2.0


def format_scale(scale):
    if scale >= 1:
        return "%d : 1" % int(round(scale))
    return "1 : %d" % int(round(1.0 / scale))


def short_title(name):
    if len(name) <= 32:
        return name
    return name[:29] + "..."


def fill_title_block(template, filename, sheet, scale):
    from datetime import date

    texts = template.EditableTexts
    texts["title"] = short_title(filename)
    texts["document_type"] = "Arkusz %s" % sheet
    texts["scale"] = format_scale(scale)
    texts["date_of_issue"] = date.today().isoformat()
    texts["creator"] = ""
    texts["approval_person"] = ""
    texts["part_material"] = ""
    texts["general_tolerances"] = ""
    texts["revision_index"] = ""
    texts["drawing_number"] = ""
    texts["language_code"] = "PL"
    texts["sheet_number"] = "1 / 1"
    for key in ("legal_owner_1", "legal_owner_2", "legal_owner_3", "legal_owner_4"):
        if key in texts:
            texts[key] = ""
    template.EditableTexts = texts


def settle():
    import FreeCADGui as Gui
    from PySide6 import QtCore

    Gui.updateGui()
    app = QtCore.QCoreApplication.instance()
    if app is None:
        return
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()


def write_stats(views, scale):
    path = os.environ.get("DRAW_STATS")
    if not path:
        return
    import json

    def quantity(value):
        if hasattr(value, "Value"):
            return float(value.Value)
        return float(value)

    payload = {
        "scale": format_scale(scale),
        "scale_value": scale,
        "views": {
            name: {
                "visible": len(list(view.getVisibleEdges())),
                "hidden": len(list(view.getHiddenEdges())),
                "x": quantity(view.X),
                "y": quantity(view.Y),
            }
            for name, view in views.items()
        },
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)


# FreeCAD executes this file and then keeps the GUI alive. Always run and
# exit the process; do not hide the call behind __name__.
try:
    main()
except SystemExit:
    raise
except Exception as exc:
    fail(str(exc))
