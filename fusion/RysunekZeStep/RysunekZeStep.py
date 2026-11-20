# -*- coding: utf-8 -*-
"""Rysunek ze STEP — skrypt Fusion (okno polecenia, nie dodatek).

Uruchomienie: Utilities → Scripts and Add-Ins → zakładka Scripts → Run.
Instrukcja instalacji: fusion/README.md w tym repozytorium.

Skrypt korzysta z podglądowego API rysunków (DrawingManager, Views.add).
Nie został uruchomiony w Fusion na maszynie, na której powstał.
"""

import math
import os
import time
import traceback

import adsk.core
import adsk.drawing
import adsk.fusion

CMD_ID = 'RysunekZeStepCmd'
HANDLERS = []

# Skale z szeregu ISO 5455, od największej. Wybierana jest największa, która
# mieści rzuty w polu arkusza.
STANDARD_SCALES = (
    100.0,
    50.0,
    20.0,
    10.0,
    5.0,
    2.0,
    1.0,
    1.0 / 2.0,
    1.0 / 5.0,
    1.0 / 10.0,
    1.0 / 20.0,
    1.0 / 50.0,
    1.0 / 100.0,
    1.0 / 200.0,
    1.0 / 500.0,
    1.0 / 1000.0,
    1.0 / 2000.0,
    1.0 / 5000.0,
    1.0 / 10000.0,
)

# Arkusz ISO w orientacji poziomej, milimetry (szerokość × wysokość).
ISO_LANDSCAPE_MM = {
    'A4': (297.0, 210.0),
    'A3': (420.0, 297.0),
    'A2': (594.0, 420.0),
}

VIEW_LABELS = {
    '1 — przód': 1,
    '2 — przód i góra': 2,
    '3 — przód, góra i prawy': 3,
    '4 — te trzy oraz izometria': 4,
}

DETAIL_LABELS = {
    'Kontur': 'contour',
    'Krawędzie widoczne': 'visible',
    'Widoczne i ukryte': 'hidden',
}

SHEET_LABELS = {
    'A4 poziomo': 'A4',
    'A3 poziomo': 'A3',
    'A2 poziomo': 'A2',
}

app = None
ui = None
dialog_state = {}
pending_job = None
dialog_closed = False
dialog_accepted = False


def largest_standard_scale(max_scale):
    """Największa skala ze STANDARD_SCALES nie większa niż max_scale."""
    for scale in STANDARD_SCALES:
        if scale <= max_scale + 1e-9:
            return scale
    return STANDARD_SCALES[-1]


def format_scale(scale):
    if scale >= 1.0 - 1e-9:
        whole = int(round(scale))
        if abs(scale - whole) < 1e-6:
            return '{}:1'.format(whole)
        return '{:g}:1'.format(scale)
    inverse = 1.0 / scale
    whole = int(round(inverse))
    if abs(inverse - whole) < 1e-4:
        return '1:{}'.format(whole)
    return '1:{:g}'.format(inverse)


def view_grid(count):
    """Układ trzeciego kąta: góra nad przodem, prawy na prawo od przodu, izometria z boku.

    Wiersz 0 jest na dole arkusza. Zwraca (lista (klucz, kolumna, wiersz), kolumny, wiersze).
    """
    if count <= 1:
        return [('front', 0, 0)], 1, 1
    if count == 2:
        return [('top', 0, 1), ('front', 0, 0)], 1, 2
    if count == 3:
        return [('top', 0, 1), ('front', 0, 0), ('right', 1, 0)], 2, 2
    return [('top', 0, 1), ('front', 0, 0), ('right', 1, 0), ('iso', 2, 1)], 3, 2


def required_model_extent(key, dx, dy, dz):
    """Bok kwadratu (cm modelu), w którym na pewno mieści się rzut.

    ViewOrientationTypes opisuje przód jako patrzenie wzdłuż ujemnej osi Z,
    więc przód pokazuje X i Y, ale nie mówi, która oś jest pozioma na arkuszu.
    Dla góry i prawego rzutu dokumentacja nie podaje osi. Dlatego każdy rzut
    prostokątny rezerwuje największy z wymiarów w obu kierunkach, a izometria
    rezerwuje przekątną przestrzenną (każdy rzut prostopadłościanu się w niej mieści).
    """
    largest = max(dx, dy, dz, 0.0)
    if key == 'front':
        return max(dx, dy, 0.0)
    if key == 'iso':
        return math.hypot(dx, dy, dz)
    return largest


def sheet_size_cm(width, height, sheet_key):
    """Szerokość i wysokość arkusza w centymetrach oraz skąd wzięto jednostki.

    BaseViewInput.placementPoint jest w centymetrach. Sheet.width nie podaje
    jednostki; CustomSheetSize mówi o jednostkach dokumentu (dla ISO: mm).
    """
    expect_w, expect_h = ISO_LANDSCAPE_MM[sheet_key]

    def close(value, expected):
        return abs(value - expected) <= max(1.0, abs(expected) * 0.08)

    if close(width, expect_w) and close(height, expect_h):
        return width / 10.0, height / 10.0, 'mm'
    if close(width, expect_w / 10.0) and close(height, expect_h / 10.0):
        return width, height, 'cm'
    if close(width, expect_w / 25.4) and close(height, expect_h / 25.4):
        return width * 2.54, height * 2.54, 'in'
    if width > 100.0:
        return width / 10.0, height / 10.0, 'mm?'
    return width, height, '?'


def margins_cm(sheet_w, sheet_h):
    """Marginesy w cm. Dolny jest wyższy, żeby zejść z typowej tabelki rysunkowej."""
    left = right = top = 1.5
    bottom = 5.0
    if sheet_w < left + right + 8.0:
        left = right = 0.8
    if sheet_h < top + bottom + 8.0:
        top = 0.8
        bottom = max(2.0, sheet_h * 0.22)
    return left, right, top, bottom


def place_views(sheet_w, sheet_h, count, extents):
    """Zwraca (skala, lista {key, x, y}, czy skala mieści się w limicie).

    x, y to środek rzutu w cm, początek w lewym dolnym rogu arkusza.
    """
    specs, cols, rows = view_grid(count)
    left, right, top, bottom = margins_cm(sheet_w, sheet_h)
    usable_w = sheet_w - left - right
    usable_h = sheet_h - top - bottom
    if usable_w <= 1.0 or usable_h <= 1.0:
        raise ValueError('Arkusz jest za mały, żeby rozmieścić rzuty z marginesem.')

    cell_w = usable_w / float(cols)
    cell_h = usable_h / float(rows)
    pad = min(0.8, cell_w * 0.15, cell_h * 0.15)
    avail_w = cell_w - pad
    avail_h = cell_h - pad
    if avail_w <= 0.4 or avail_h <= 0.4:
        raise ValueError('Za mało miejsca między rzutami.')

    limits = []
    for key, _col, _row in specs:
        extent = extents[key]
        if extent > 1e-6:
            limits.append(min(avail_w / extent, avail_h / extent))
    if not limits:
        raise ValueError('Model nie ma wymiaru, z którego da się zrobić rzut.')

    limit = min(limits)
    scale = largest_standard_scale(limit)
    fits = scale <= limit + 1e-9

    placed = []
    for key, col, row in specs:
        placed.append({
            'key': key,
            'x': left + (col + 0.5) * cell_w,
            'y': bottom + (row + 0.5) * cell_h,
        })
    return scale, placed, fits


def document_name_from_step(step_path):
    stem = os.path.splitext(os.path.basename(step_path))[0]
    cleaned = []
    for char in stem:
        if char.isalnum() or char in ' _-':
            cleaned.append(char)
        else:
            cleaned.append('_')
    name = ''.join(cleaned).strip(' ._')
    return name or 'STEP'


def pdf_path_beside_step(step_path):
    folder, filename = os.path.split(step_path)
    stem = os.path.splitext(filename)[0] or 'rysunek'
    return os.path.join(folder, stem + '.pdf')


def _message(text):
    if ui:
        ui.messageBox(text, 'Rysunek ze STEP')


def _finish():
    try:
        command_def = ui.commandDefinitions.itemById(CMD_ID)
        if command_def:
            command_def.deleteMe()
    except Exception:
        pass
    adsk.terminate()


def _require_cloud_project():
    """Rysunek API bierze DataFile z chmury. Otwarty niezapisany dokument nie jest źródłem."""
    project = None
    folder = None
    try:
        project = app.data.activeProject
        folder = project.rootFolder if project else None
    except Exception:
        project = None
        folder = None
    if not project or not folder:
        raise ValueError(
            'Brak aktywnego projektu Fusion. Zaloguj się i wybierz projekt.\n'
            'Otwarty dokument „(Niezapisany)” nie jest plikiem STEP i nie musi być zapisany. '
            'Skrypt zakłada nowy model ze wskazanego pliku i zapisuje go w projekcie, '
            'bo rysunek da się utworzyć tylko z modelu w chmurze.'
        )


def _read_options():
    path = dialog_state['path'].value.strip()
    if not path:
        raise ValueError('Wybierz plik STEP.')
    lower = path.lower()
    if not (lower.endswith('.step') or lower.endswith('.stp')):
        raise ValueError('Plik musi mieć rozszerzenie .step lub .stp.')
    if not os.path.isfile(path):
        raise ValueError('Nie ma takiego pliku:\n{}'.format(path))

    view_item = dialog_state['views'].selectedItem
    detail_item = dialog_state['detail'].selectedItem
    sheet_item = dialog_state['sheet'].selectedItem
    if not view_item or not detail_item or not sheet_item:
        raise ValueError('Wybierz liczbę rzutów, szczegółowość i arkusz.')
    if view_item.name not in VIEW_LABELS:
        raise ValueError('Nieznana liczba rzutów.')
    if detail_item.name not in DETAIL_LABELS:
        raise ValueError('Nieznana szczegółowość.')
    if sheet_item.name not in SHEET_LABELS:
        raise ValueError('Nieznany arkusz.')

    _require_cloud_project()

    return {
        'step': path,
        'views': VIEW_LABELS[view_item.name],
        'detail': DETAIL_LABELS[detail_item.name],
        'sheet': SHEET_LABELS[sheet_item.name],
    }


def _choose_step_file():
    dialog = ui.createFileDialog()
    dialog.title = 'Plik STEP'
    dialog.filter = 'Pliki STEP (*.step;*.stp)'
    dialog.filterIndex = 0
    dialog.isMultiSelectEnabled = False
    current = dialog_state['path'].value.strip()
    if current:
        dialog.initialDirectory = os.path.dirname(current)
        dialog.initialFilename = os.path.basename(current)
    if dialog.showOpen() != adsk.core.DialogResults.DialogOK:
        return
    dialog_state['path'].value = dialog.filename


def _appearance(detail):
    visible = adsk.drawing.DrawingViewStyleTypes.VisibleEdgesDrawingViewStyleType
    hidden = adsk.drawing.DrawingViewStyleTypes.VisibleAndHiddenEdgesDrawingViewStyleType
    tangent_off = adsk.drawing.TangentEdgeDisplayTypes.OffTangentEdgeDisplayType
    tangent_on = adsk.drawing.TangentEdgeDisplayTypes.FullLengthTangentEdgeDisplayType
    if detail == 'contour':
        return visible, tangent_off
    if detail == 'visible':
        return visible, tangent_on
    return hidden, tangent_on


def _orientation(key):
    orientations = adsk.drawing.ViewOrientationTypes
    return {
        'front': orientations.FrontViewOrientationType,
        'top': orientations.TopViewOrientationType,
        'right': orientations.RightViewOrientationType,
        'iso': orientations.IsoTopRightViewOrientationType,
    }[key]


def _wait_for_data_file(document):
    data_file = document.dataFile
    if data_file:
        return data_file
    deadline = time.time() + 90.0
    while time.time() < deadline:
        adsk.doEvents()
        time.sleep(0.25)
        data_file = document.dataFile
        if data_file:
            return data_file
    return None


def _save_design(document, step_path):
    """Zapis do aktywnego projektu Fusion. createDrawing wymaga DataFile w chmurze."""
    project = app.data.activeProject
    if not project:
        raise RuntimeError(
            'Brak aktywnego projektu Fusion. Zaloguj się i wybierz projekt, '
            'potem uruchom skrypt ponownie.'
        )
    folder = project.rootFolder
    description = 'Import STEP do rysunku PDF'
    name = document_name_from_step(step_path)
    if not document.saveAs(name, folder, description, ''):
        stamped = '{} {}'.format(name, time.strftime('%Y%m%d-%H%M%S'))
        if not document.saveAs(stamped, folder, description, ''):
            raise RuntimeError(
                'Nie udało się zapisać zaimportowanego modelu do projektu Fusion. '
                'Rysunek API tworzy się tylko z pliku zapisanego w chmurze.'
            )
    data_file = _wait_for_data_file(document)
    if not data_file:
        raise RuntimeError(
            'Model został zapisany, ale Fusion nie zwrócił jeszcze pliku danych '
            '(DataFile). Poczekaj chwilę i uruchom skrypt ponownie na tym samym STEP.'
        )
    return data_file


def _model_extents(design):
    box = design.rootComponent.boundingBox
    dx = abs(box.maxPoint.x - box.minPoint.x)
    dy = abs(box.maxPoint.y - box.minPoint.y)
    dz = abs(box.maxPoint.z - box.minPoint.z)
    if not all(math.isfinite(value) for value in (dx, dy, dz)):
        raise RuntimeError('Nie da się odczytać gabarytu modelu.')
    if max(dx, dy, dz) <= 1e-6:
        raise RuntimeError('Zaimportowany model nie ma geometrii do narysowania.')
    return dx, dy, dz


def _apply_sheet(sheet, sheet_key):
    sizes = {
        'A4': adsk.drawing.SheetSizes.A4ISOSheetSize,
        'A3': adsk.drawing.SheetSizes.A3ISOSheetSize,
        'A2': adsk.drawing.SheetSizes.A2ISOSheetSize,
    }
    sheet.sheetSize = sizes[sheet_key]
    sheet.orientation = adsk.drawing.SheetOrientationTypes.LandscapeSheetOrientationType


def _ensure_title_block(drawing, sheet, sheet_w, scale_text):
    """Zostawia tabelkę Fusion. API nie ma pola na dowolny tekst (nazwa, data).

    Jedyny udokumentowany znacznik to SCALE. Jeśli tabelka go nie ma, skrypt
    próbuje go dodać. Niepowodzenie nie przerywa eksportu.
    """
    note = (
        'Tabelka: API nie pozwala wpisać nazwy pliku, arkusza ani daty. '
        'Zostaje tabelka, którą Fusion wstawia do nowego rysunku ISO.'
    )
    try:
        block = sheet.titleBlock
    except Exception:
        block = None
    if not block:
        try:
            blocks = drawing.titleBlocks
            if blocks and blocks.count:
                block = blocks.item(0)
                sheet.titleBlock = block
                note = (
                    'Tabelka: przypisano istniejącą definicję z rysunku. '
                    'API nie pozwala wpisać nazwy pliku, arkusza ani daty.'
                )
        except Exception:
            block = None
    if not block:
        return 'Tabelka: rysunek nie zwrócił żadnej tabelki. PDF będzie bez niej.'

    names = []
    try:
        existing = block.getAttributes()
        if existing:
            for attr in existing:
                names.append((attr.attributeName or '').upper())
    except Exception:
        existing = None

    if 'SCALE' in names:
        return note + ' Pole SCALE już jest w tabelce.'

    try:
        parameter = block.createAttributeParameter()
        parameter.attributeName = 'SCALE'
        parameter.position = adsk.core.Point2D.create(max(0.5, sheet_w - 4.0), 1.2)
        if block.setAttributes([parameter]):
            return note + ' Dodano pole SCALE (skala {}).'.format(scale_text)
    except Exception:
        pass
    return note + ' Nie udało się dodać pola SCALE.'


def _add_base_view(views, key, scale, style, tangent, x_cm, y_cm):
    view_input = views.createBaseViewInput()
    view_input.placementPoint = adsk.drawing.DrawingPoint.create(
        adsk.core.Point2D.create(x_cm, y_cm)
    )
    parameters = view_input.viewParameters
    parameters.orientation = _orientation(key)
    parameters.scaleValue = scale
    parameters.style = style
    parameters.tangentEdgesType = tangent
    parameters.isShowInterferenceEdges = False
    view = views.add(view_input)
    if not view:
        raise RuntimeError('Fusion nie dodał rzutu ({}).'.format(key))
    # Właściwości gotowego rzutu mają inną nazwę krawędzi stycznych niż wejście.
    if view.style != style:
        view.style = style
    if view.tangentEdges != tangent:
        view.tangentEdges = tangent
    if abs((view.scaleValue or 0.0) - scale) > 1e-6:
        view.scaleValue = scale
    return view


def _export_pdf(drawing, step_path):
    target = pdf_path_beside_step(step_path)
    if _write_pdf(drawing, target):
        return target

    dialog = ui.createFileDialog()
    dialog.title = 'Zapisz PDF'
    dialog.filter = 'PDF (*.pdf)'
    dialog.filterIndex = 0
    dialog.initialDirectory = os.path.dirname(target)
    dialog.initialFilename = os.path.basename(target)
    if dialog.showSave() != adsk.core.DialogResults.DialogOK:
        raise RuntimeError(
            'Nie udało się zapisać PDF obok pliku STEP, a wybór innego miejsca został anulowany.'
        )
    chosen = dialog.filename
    if not chosen.lower().endswith('.pdf'):
        chosen += '.pdf'
    if not _write_pdf(drawing, chosen):
        raise RuntimeError('Eksport PDF nie powiódł się:\n{}'.format(chosen))
    return chosen


def _write_pdf(drawing, path):
    export_manager = drawing.exportManager
    options = export_manager.createPDFExportOptions(path)
    options.sheetsToExport = adsk.drawing.PDFSheetsExport.AllPDFSheetsExport
    options.useLineWeights = True
    options.openPDF = False
    return bool(export_manager.execute(options))


def _create_drawing(data_file, sheet_key):
    manager = adsk.drawing.DrawingManager.get()
    if not manager:
        raise RuntimeError('Fusion nie zwrócił DrawingManager.')
    drawing_input = manager.createDrawingInput(
        data_file,
        adsk.drawing.DrawingCreationModes.ManualDrawingCreationMode,
    )
    if not drawing_input:
        raise RuntimeError('Nie udało się przygotować rysunku.')

    sizes = {
        'A4': adsk.drawing.SheetSizes.A4ISOSheetSize,
        'A3': adsk.drawing.SheetSizes.A3ISOSheetSize,
        'A2': adsk.drawing.SheetSizes.A2ISOSheetSize,
    }
    drawing_input.baseDocumentType = adsk.drawing.BaseDocumentTypes.FromScratchBaseDocumentType
    drawing_input.standard = adsk.drawing.DrawingStandardTypes.ISODrawingStandardType
    drawing_input.units = adsk.drawing.DrawingUnitTypes.MillimeterDrawingUnitType
    drawing_input.sheetSize = sizes[sheet_key]
    drawing_input.orientationType = adsk.drawing.SheetOrientationTypes.LandscapeSheetOrientationType
    drawing_input.creationMode = adsk.drawing.DrawingCreationModes.ManualDrawingCreationMode

    drawing_file = manager.createDrawing(drawing_input)
    if not drawing_file:
        raise RuntimeError(
            'Tworzenie rysunku nie zwróciło pliku. API rysunków jest w podglądzie '
            'i wymaga zapisanego modelu.'
        )
    opened = app.documents.open(drawing_file, True)
    drawing_document = adsk.drawing.DrawingDocument.cast(opened)
    if not drawing_document:
        drawing_document = adsk.drawing.DrawingDocument.cast(app.activeDocument)
    if not drawing_document:
        raise RuntimeError('Nie udało się otworzyć utworzonego rysunku.')
    return drawing_document.drawing


def _projection_note(drawing):
    try:
        angle = drawing.documentSettings.projectionAngle
    except Exception:
        return 'Kąt rzutowania dokumentu: nie odczytano (właściwość jest tylko do odczytu).'
    third = adsk.drawing.ProjectionAngleTypes.ThirdAngleProjectionAngleType
    first = adsk.drawing.ProjectionAngleTypes.FirstAngleProjectionAngleType
    if angle == third:
        flag = 'trzeci kąt'
    elif angle == first:
        flag = 'pierwszy kąt (tak opisuje norma ISO w tym API)'
    else:
        flag = 'nieznany'
    return (
        'Flaga dokumentu: {}. Rzuty są osobnymi widokami bazowymi ustawionymi '
        'jak w trzecim kącie (góra nad przodem, prawy na prawo od przodu). '
        'API nie tworzy rzutu pochodnego i nie pozwala zmienić kąta dokumentu.'
    ).format(flag)


def build_drawing(options):
    if ui.activeCommand != 'SelectCommand':
        select_command = ui.commandDefinitions.itemById('SelectCommand')
        if select_command:
            select_command.execute()
            adsk.doEvents()

    step_path = options['step']
    _message(
        'Importuję STEP i tworzę rysunek.\n'
        'Otwarty, niezapisany dokument jest pomijany. Nowy model ze STEP zostanie zapisany '
        'w aktywnym projekcie Fusion. Po kliknięciu OK poczekaj na kolejne okno.'
    )

    importer = app.importManager
    step_options = importer.createSTEPImportOptions(step_path)
    step_options.isViewFit = True
    design_document = importer.importToNewDocument(step_options)
    if not design_document:
        raise RuntimeError('Import STEP nie utworzył dokumentu.')

    design = adsk.fusion.Design.cast(
        design_document.products.itemByProductType('DesignProductType')
    )
    if not design:
        raise RuntimeError('Zaimportowany dokument nie jest modelem Fusion.')

    dx, dy, dz = _model_extents(design)
    data_file = _save_design(design_document, step_path)
    drawing = _create_drawing(data_file, options['sheet'])
    sheet = drawing.activeSheet
    if not sheet:
        raise RuntimeError('Nowy rysunek nie ma arkusza.')

    try:
        _apply_sheet(sheet, options['sheet'])
    except Exception:
        pass

    sheet_w, sheet_h, unit_guess = sheet_size_cm(sheet.width, sheet.height, options['sheet'])
    count = int(options['views'])
    extents = {}
    for key, _col, _row in view_grid(count)[0]:
        extents[key] = required_model_extent(key, dx, dy, dz)
    scale, placed, fits = place_views(sheet_w, sheet_h, count, extents)
    style, tangent = _appearance(options['detail'])

    warnings = []
    if options['detail'] == 'hidden':
        try:
            drawing.documentSettings.viewSettings.hiddenLineLineType = (
                adsk.drawing.LineTypes.HiddenLineType
            )
        except Exception:
            warnings.append(
                'Nie ustawiono typu linii HIDDEN. Styl rzutu i tak prosi o krawędzie ukryte.'
            )

    if sheet.views.count:
        warnings.append(
            'Arkusz nie był pusty (było już {} rzutów). API widoku nie ma usuwania, '
            'więc doszły nowe rzuty.'.format(sheet.views.count)
        )

    for item in placed:
        _add_base_view(
            sheet.views,
            item['key'],
            scale,
            style,
            tangent,
            item['x'],
            item['y'],
        )

    scale_text = format_scale(scale)
    title_note = _ensure_title_block(drawing, sheet, sheet_w, scale_text)
    pdf_path = _export_pdf(drawing, step_path)

    lines = [
        'Zapisano PDF:',
        pdf_path,
        '',
        'Arkusz: {} poziomo. Skala: {}.'.format(options['sheet'], scale_text),
        _projection_note(drawing),
        title_note,
        'Jednostka odczytana z szerokości arkusza: {}.'.format(unit_guess),
    ]
    if not fits:
        lines.append(
            'Nawet najmniejsza skala z szeregu (1:10000) może nie zmieścić modelu w marginesie.'
        )
    lines.extend(warnings)
    _message('\n'.join(lines))


class CreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            command = adsk.core.CommandCreatedEventArgs.cast(args).command
            command.setDialogInitialSize(520, 420)
            inputs = command.commandInputs

            inputs.addTextBoxCommandInput(
                'wstep',
                '',
                'Import STEP do nowego modelu, rysunek ISO i jeden PDF obok pliku STEP. '
                'Otwarty, niezapisany dokument jest pomijany. '
                'Bez przekrojów, tolerancji geometrycznych i listy części.',
                4,
                True,
            )

            path_input = inputs.addStringValueInput('plikStep', 'Plik STEP', '')
            path_input.isReadOnly = True
            dialog_state['path'] = path_input

            inputs.addBoolValueInput('wybierzPlik', 'Wybierz plik', False, '', False)

            views = inputs.addDropDownCommandInput(
                'liczbaRzutow',
                'Liczba rzutów',
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            views.tooltipDescription = (
                '1 przód. 2 przód i góra nad nim. 3 dodatkowo prawy na prawo od przodu. '
                '4 dodatkowo izometria z boku. Układ jak w trzecim kącie.'
            )
            for index, label in enumerate(VIEW_LABELS):
                views.listItems.add(label, index == 2, '')
            dialog_state['views'] = views

            detail = inputs.addDropDownCommandInput(
                'szczegolowosc',
                'Szczegółowość',
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            detail.tooltipDescription = (
                'Kontur: tylko widoczne krawędzie ostre. '
                'Krawędzie widoczne: ostre i styczne, bez ukrytych. '
                'Widoczne i ukryte: to samo oraz krawędzie ukryte (typ linii HIDDEN).'
            )
            for index, label in enumerate(DETAIL_LABELS):
                detail.listItems.add(label, index == 0, '')
            dialog_state['detail'] = detail

            sheet = inputs.addDropDownCommandInput(
                'arkusz',
                'Arkusz',
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            sheet.tooltipDescription = 'Wszystkie arkusze są poziome (A4, A3 albo A2).'
            for index, label in enumerate(SHEET_LABELS):
                sheet.listItems.add(label, index == 1, '')
            dialog_state['sheet'] = sheet

            on_execute = ExecuteHandler()
            command.execute.add(on_execute)
            HANDLERS.append(on_execute)

            on_input = InputChangedHandler()
            command.inputChanged.add(on_input)
            HANDLERS.append(on_input)

            on_destroy = DestroyHandler()
            command.destroy.add(on_destroy)
            HANDLERS.append(on_destroy)
            dialog_state['ready'] = True
        except Exception:
            _message('Nie udało się zbudować okna:\n{}'.format(traceback.format_exc()))


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            if not dialog_state.get('ready'):
                return
            changed = adsk.core.InputChangedEventArgs.cast(args).input
            if changed and changed.id == 'wybierzPlik':
                _choose_step_file()
        except Exception:
            _message('Nie udało się wybrać pliku:\n{}'.format(traceback.format_exc()))


class ExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        global pending_job
        event_args = adsk.core.CommandEventArgs.cast(args)
        try:
            pending_job = _read_options()
        except ValueError as error:
            pending_job = None
            event_args.executeFailed = True
            event_args.executeFailedMessage = str(error)
        except Exception:
            pending_job = None
            event_args.executeFailed = True
            event_args.executeFailedMessage = traceback.format_exc()


class DestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        global dialog_closed, dialog_accepted
        try:
            reason = adsk.core.CommandEventArgs.cast(args).terminationReason
            dialog_accepted = (
                reason == adsk.core.CommandTerminationReason.CompletedTerminationReason
                and pending_job is not None
            )
        except Exception:
            dialog_accepted = False
            _message('Błąd przy zamykaniu okna:\n{}'.format(traceback.format_exc()))
        dialog_closed = True


def run(_context):
    global app, ui, pending_job, dialog_closed, dialog_accepted
    app = adsk.core.Application.get()
    ui = app.userInterface if app else None
    pending_job = None
    dialog_closed = False
    dialog_accepted = False
    dialog_state.clear()
    try:
        if not app or not ui:
            return

        existing = ui.commandDefinitions.itemById(CMD_ID)
        if existing:
            existing.deleteMe()

        command_def = ui.commandDefinitions.addButtonDefinition(
            CMD_ID,
            'Rysunek ze STEP',
            'Importuje plik STEP i zapisuje rysunek PDF.',
        )
        on_created = CreatedHandler()
        command_def.commandCreated.add(on_created)
        HANDLERS.append(on_created)
        command_def.execute()
        # run() musi żyć do zamknięcia okna. Po powrocie z run() znika zdarzenie
        # własne i fireCustomEvent zwraca fałsz, zanim import w ogóle ruszy.
        adsk.autoTerminate(False)
        if not dialog_state.get('ready'):
            dialog_closed = True
        while not dialog_closed:
            adsk.doEvents()
            if dialog_closed:
                break
            time.sleep(0.05)
        for _ in range(3):
            adsk.doEvents()
        if dialog_accepted and pending_job:
            try:
                build_drawing(pending_job)
            except Exception:
                _message('Nie udało się utworzyć rysunku:\n{}'.format(traceback.format_exc()))
        _finish()
    except Exception:
        _message('Nie udało się uruchomić skryptu:\n{}'.format(traceback.format_exc()))
        _finish()
