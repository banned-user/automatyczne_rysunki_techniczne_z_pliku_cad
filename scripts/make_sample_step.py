"""Write samples/box_with_hole.step. Run with freecadcmd, not the web app.

The solid is an 80 x 50 x 30 mm box with a vertical through-hole, diameter 16 mm,
centered on the top face.
"""

import os

import FreeCAD as App
import Part

output = os.environ.get("SAMPLE_OUT")
if not output:
    raise SystemExit("Ustaw SAMPLE_OUT na ścieżkę pliku STEP.")

box = Part.makeBox(80, 50, 30)
hole = Part.makeCylinder(8, 40, App.Vector(40, 25, -5), App.Vector(0, 0, 1))
shape = box.cut(hole)
shape.exportStep(output)
os._exit(0)
