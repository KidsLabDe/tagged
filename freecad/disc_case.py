# Disc-Gehaeuse: RC522 + Lolin S2 Mini + TP4056 (USB-C) + 18650 + WS2812B-Streifen + Schiebeschalter
# Ausfuehren in FreeCAD (Makro oder MCP Bridge). Erzeugt Dokument "DiscCase" und STLs in OUT_DIR.
# Koordinaten: x = Breite (0 = Mitte), y = Laenge (0 = Innenkante unten, USB-Seite), z = Dicke (0 = Rueckseite)
import os
import FreeCAD as App
import Part

OUT_DIR = "/home/kingbbq/src/polygen-nachbau/freecad"
FONT = "/usr/share/fonts/tex-gyre/texgyreadventor-bold.otf"

TEXT_MAIN = "DISC"
TEXT_SUB = "#01"
TEXT_TAP = "TAP HERE"

# Gehaeuse
W_IN, L_IN, R_IN = 80.0, 148.0, 16.0  # Innenraum
WALL = 2.0
FLOOR = 2.0
H_IN = 22.0  # Innenhoehe Boden -> Deckel
LID = 1.6
LOGO_DEPTH = 0.6
CLR = 0.3  # Spiel fuer Passungen (PETG)

# LED-Streifen (WS2812B, 10 mm breit): Nut innen rundum, Wand dort nur 1.2 mm, Oberkante 45° angeschraegt
LED_RECESS = 0.8
LED_Z0, LED_Z1 = FLOOR + 9.0, FLOOR + H_IN - 2.6

# Verschraubung: Gewindeeinsaetze M3 (z.B. M3 x 5.7) im Deckel, M3 x 8 Senkkopfschraube von hinten
INSERTS = True
INSERT_D, INSERT_DEPTH = 4.2, 6.0
BOSS_R = 4.0 if INSERTS else 3.5

# Bauteile
RC522 = (40.0, 60.0, 1.6)
RC522_CY = 100.0
S2MINI = (25.4, 34.3)
S2MINI_X0 = -23.4
TP4056 = (17.3, 28.0)
TP4056_X0 = 6.1
BATT_HOLDER = (77.0, 21.0, 19.0)  # 1x18650 Halter
BATT_Y0 = 42.0
SWITCH_Y = 32.0  # SS12D00-Schiebeschalter in der rechten Seitenwand
SCREWS = [(-33, 20), (33, 20), (-33, 100), (33, 100)]
LANYARD = (0.0, 140.0)

CY = L_IN / 2  # Mitte der Laengsachse
Z_TOP = FLOOR + H_IN


def rrect(w, l, r, h, z=0.0, cx=0.0, cy=CY):
    parts = [
        Part.makeBox(w - 2 * r, l, h, App.Vector(cx - w / 2 + r, cy - l / 2, z)),
        Part.makeBox(w, l - 2 * r, h, App.Vector(cx - w / 2, cy - l / 2 + r, z)),
    ]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(Part.makeCylinder(r, h, App.Vector(cx + sx * (w / 2 - r), cy + sy * (l / 2 - r), z)))
    return parts[0].fuse(parts[1:]).removeSplitter()


def rrect_wire(w, l, r, z):
    s = rrect(w, l, r, 1.0, z)
    face = [f for f in s.Faces if f.BoundBox.ZLength < 1e-6 and abs(f.BoundBox.ZMin - z) < 1e-6][0]
    return face.OuterWire


def box(x0, y0, z0, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, App.Vector(x0, y0, z0))


def cyl(r, h, x, y, z):
    return Part.makeCylinder(r, h, App.Vector(x, y, z))


def text_faces(text, width, cx, cy):
    """Text als Flaechen, skaliert auf die Breite `width` (mm), zentriert auf (cx, cy)."""
    import Draft
    doc = App.ActiveDocument
    ss = Draft.make_shapestring(String=text, FontFile=FONT, Size=10.0, Tracking=0.0)
    doc.recompute()
    shape = ss.Shape.copy()
    doc.removeObject(ss.Name)
    bb = shape.BoundBox
    shape.translate(App.Vector(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, 0))
    shape.scale(width / bb.XLength)
    shape.translate(App.Vector(cx, cy, 0))
    return shape


def arc_band(r0, r1, angle_deg, cx, cy):
    ring = Part.makeCylinder(r1, 1, App.Vector(cx, cy, 0)).cut(Part.makeCylinder(r0, 1, App.Vector(cx, cy, 0)))
    half = angle_deg / 2
    import math
    a0, a1 = math.radians(90 - half), math.radians(90 + half)
    R = r1 + 1
    wedge_pts = [App.Vector(cx, cy, 0), App.Vector(cx + R * 2 * math.cos(a0), cy + R * 2 * math.sin(a0), 0),
                 App.Vector(cx, cy + R * 2, 0),
                 App.Vector(cx + R * 2 * math.cos(a1), cy + R * 2 * math.sin(a1), 0), App.Vector(cx, cy, 0)]
    wedge = Part.Face(Part.makePolygon(wedge_pts)).extrude(App.Vector(0, 0, 1))
    band = ring.common(wedge)
    # runde Enden
    ends = []
    rm, w = (r0 + r1) / 2, (r1 - r0) / 2
    for a in (a0, a1):
        ends.append(Part.makeCylinder(w, 1, App.Vector(cx + rm * math.cos(a), cy + rm * math.sin(a), 0)))
    return band.fuse(ends)


def logo_solid():
    """Alle Front-Grafiken als 2D-Flaechen -> extrudiert auf LOGO_DEPTH, oben buendig mit dem Deckel."""
    solids = []
    # Kontaktlos-Symbol ueber der Antenne
    icx, icy = 0.0, 90.0
    solids.append(Part.makeCylinder(2.4, 1, App.Vector(icx, icy, 0)))
    for r0 in (7.0, 12.0, 17.0):
        solids.append(arc_band(r0, r0 + 2.5, 90, icx, icy))
    # Eckwinkel um die Lesezone
    zw, zl, arm, t = 50.0, 66.0, 9.0, 1.6
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * zw / 2, RC522_CY + sy * zl / 2
            solids.append(box(min(x, x - sx * arm), y - t / 2, 0, arm, t, 1))
            solids.append(box(x - t / 2, min(y, y - sy * arm), 0, t, arm, 1))
    flat = []
    for s in solids:
        flat.append(s)
    for f in (text_faces(TEXT_TAP, 40.0, 0, 57.0), text_faces(TEXT_MAIN, 56.0, 0, 29.0), text_faces(TEXT_SUB, 16.0, 0, 10.0)):
        flat.append(f.extrude(App.Vector(0, 0, 1)))
    logo = flat[0].fuse(flat[1:]).removeSplitter()
    logo.scale(1.0)
    m = App.Matrix()
    m.scale(1, 1, LOGO_DEPTH)
    logo = logo.transformGeometry(m)
    logo.translate(App.Vector(0, 0, Z_TOP + LID - LOGO_DEPTH))
    return logo


def make_base():
    outer = rrect(W_IN + 2 * WALL, L_IN + 2 * WALL, R_IN + WALL, Z_TOP)
    inner = rrect(W_IN, L_IN, R_IN, H_IN + 1, FLOOR)
    led = rrect(W_IN + 2 * LED_RECESS, L_IN + 2 * LED_RECESS, R_IN + LED_RECESS, LED_Z1 - LED_Z0, LED_Z0)
    led_chamfer = Part.makeLoft([
        rrect_wire(W_IN + 2 * LED_RECESS, L_IN + 2 * LED_RECESS, R_IN + LED_RECESS, LED_Z1),
        rrect_wire(W_IN, L_IN, R_IN, LED_Z1 + LED_RECESS)], True)
    base = outer.cut(inner).cut(led).cut(led_chamfer)

    add = []
    # Rahmen fuer S2 Mini und TP4056 (3 Seiten, offen zur USB-Wand)
    for x0, (bw, bl) in ((S2MINI_X0, S2MINI), (TP4056_X0, TP4056)):
        g, t = CLR, 1.2
        add += [box(x0 - g - t, 0, FLOOR, t, bl + g + t, 3),
                box(x0 + bw + g, 0, FLOOR, t, bl + g + t, 3),
                box(x0 - g - t, bl + g, FLOOR, bw + 2 * g + 2 * t, t, 3)]
    # Schienen fuer den 18650-Halter
    hw = BATT_HOLDER[1] + 0.6
    add += [box(-38, BATT_Y0 - 1.2, FLOOR, 76, 1.2, 4), box(-38, BATT_Y0 + hw, FLOOR, 76, 1.2, 4)]
    # Fuehrung fuer den Schiebeschalter (Koerper 8.6 x 3.6 mm)
    sg = 4.3 + CLR / 2
    add += [box(W_IN / 2 - 5, SWITCH_Y - sg - 1.2, FLOOR, 5, 1.2, 4), box(W_IN / 2 - 5, SWITCH_Y + sg, FLOOR, 5, 1.2, 4)]
    # Rohr fuer die Kordel
    add.append(cyl(5.0, Z_TOP, LANYARD[0], LANYARD[1], 0))
    base = base.fuse(add)

    cut = []
    # USB-C-Oeffnungen in der unteren Wand
    for x0, (bw, bl) in ((S2MINI_X0, S2MINI), (TP4056_X0, TP4056)):
        cx = x0 + bw / 2
        cut.append(box(cx - 5.5, -WALL - 1, FLOOR + 0.25, 11, WALL + 1.5, 5.5))
    # Schlitz fuer den Schalterhebel
    cut.append(box(W_IN / 2 - 0.5, SWITCH_Y - 3.5, FLOOR + 0.65, WALL + 1.5, 7, 2.2))
    # Schraubenloecher mit Senkung (Rueckseite)
    for x, y in SCREWS:
        cut.append(cyl(1.7, FLOOR + 1, x, y, -0.5))
        cut.append(Part.makeCone(3.2, 1.7, 1.5, App.Vector(x, y, 0)))
    cut.append(cyl(2.5, Z_TOP + 2, LANYARD[0], LANYARD[1], -1))
    return base.cut(cut).removeSplitter()


def make_lid():
    plate = rrect(W_IN + 2 * WALL, L_IN + 2 * WALL, R_IN + WALL, LID, Z_TOP)
    lip = rrect(W_IN - 2 * CLR, L_IN - 2 * CLR, R_IN - CLR, 1.4, Z_TOP - 1.4).cut(
        rrect(W_IN - 2 * CLR - 2.4, L_IN - 2 * CLR - 2.4, R_IN - CLR - 1.2, 2, Z_TOP - 1.7))
    add = [lip]
    # Schraubdome bis kurz ueber den Boden, unten Bohrung fuer Gewindeeinsatz bzw. Kernloch
    hole_r, hole_depth = (INSERT_D / 2, INSERT_DEPTH) if INSERTS else (1.3, Z_TOP - FLOOR - 1.0)
    for x, y in SCREWS:
        add.append(cyl(BOSS_R, Z_TOP - FLOOR - 0.2, x, y, FLOOR + 0.2).cut(cyl(hole_r, hole_depth + 0.2, x, y, FLOOR)))
    # Rahmen fuer den RC522 (liegt mit der Rueckseite am Deckel)
    rw, rl, _ = RC522
    g, t, h = 0.4, 1.2, 2.0
    frame = box(-rw / 2 - g - t, RC522_CY - rl / 2 - g - t, Z_TOP - h, rw + 2 * (g + t), rl + 2 * (g + t), h).cut(
        box(-rw / 2 - g, RC522_CY - rl / 2 - g, Z_TOP - h - 1, rw + 2 * g, rl + 2 * g, h + 2))
    add.append(frame)
    lid = plate.fuse(add)
    lid = lid.cut(cyl(2.5, 10, LANYARD[0], LANYARD[1], Z_TOP - 5))
    return lid.removeSplitter()


def make_dummies():
    d = {}
    rw, rl, rt = RC522
    d["RC522"] = box(-rw / 2, RC522_CY - rl / 2, Z_TOP - rt, rw, rl, rt)
    d["S2Mini"] = box(S2MINI_X0, 0, FLOOR, S2MINI[0], S2MINI[1], 1.0).fuse(
        box(S2MINI_X0 + S2MINI[0] / 2 - 4.5, -0.5, FLOOR + 1.0, 9, 7.5, 3.2))
    d["TP4056"] = box(TP4056_X0, 0, FLOOR, TP4056[0], TP4056[1], 1.6).fuse(
        box(TP4056_X0 + TP4056[0] / 2 - 4.5, -0.5, FLOOR + 1.6, 9, 7.5, 3.2))
    bl, bw, bh = BATT_HOLDER
    d["Akku18650"] = box(-bl / 2, BATT_Y0 + 0.3, FLOOR, bl, bw, bh)
    d["Schalter"] = box(W_IN / 2 - 3.6, SWITCH_Y - 4.3, FLOOR, 3.6, 8.6, 3.5).fuse(
        box(W_IN / 2, SWITCH_Y - 0.75, FLOOR + 1.0, 3.5, 1.5, 1.5))
    strip_outer = rrect(W_IN + 2 * LED_RECESS, L_IN + 2 * LED_RECESS, R_IN + LED_RECESS, 10, LED_Z0 + 0.4)
    strip_inner = rrect(W_IN - 2.0, L_IN - 2.0, R_IN - 1.0, 12, LED_Z0)
    d["LED_Streifen"] = strip_outer.cut(strip_inner)
    return d


def build():
    if "DiscCase" in App.listDocuments():
        App.closeDocument("DiscCase")
    doc = App.newDocument("DiscCase")
    App.setActiveDocument("DiscCase")

    base = make_base()
    lid_full = make_lid()
    logo = logo_solid()
    lid = lid_full.cut(logo)
    logo_inlay = logo.common(lid_full)

    objs = {}
    for name, shape in (("Unterteil", base), ("Deckel", lid), ("Deckel_Logo", logo_inlay)):
        o = doc.addObject("Part::Feature", name)
        o.Shape = shape
        objs[name] = o
    dummies = make_dummies()
    for name, shape in dummies.items():
        o = doc.addObject("Part::Feature", "Bauteil_" + name)
        o.Shape = shape
        objs["Bauteil_" + name] = o
    doc.recompute()

    try:
        import FreeCADGui as Gui
        colors = {"Unterteil": (0.85, 0.75, 0.9), "Deckel": (0.9, 0.8, 0.95), "Deckel_Logo": (0.1, 0.1, 0.1),
                  "Bauteil_RC522": (0.1, 0.3, 0.8), "Bauteil_S2Mini": (0.2, 0.2, 0.2), "Bauteil_TP4056": (0.1, 0.3, 0.8),
                  "Bauteil_Akku18650": (0.2, 0.6, 0.2), "Bauteil_Schalter": (0.9, 0.5, 0.1),
                  "Bauteil_LED_Streifen": (1.0, 0.95, 0.9)}
        for name, o in objs.items():
            v = o.ViewObject
            v.ShapeColor = colors.get(name, (0.7, 0.7, 0.7))
            if name in ("Unterteil", "Deckel"):
                v.Transparency = 55
    except Exception as e:
        print("GUI-Farben uebersprungen:", e)

    os.makedirs(OUT_DIR, exist_ok=True)
    doc.saveAs(os.path.join(OUT_DIR, "DiscCase.FCStd"))
    export_print(objs)

    for name in ("Unterteil", "Deckel", "Deckel_Logo"):
        s = objs[name].Shape
        print("%-12s valid=%s solids=%d  bbox=%.1f x %.1f x %.1f  vol=%.0f mm3" % (
            name, s.isValid(), len(s.Solids), s.BoundBox.XLength, s.BoundBox.YLength, s.BoundBox.ZLength, s.Volume))
    v = objs["Unterteil"].Shape.common(objs["Deckel"].Shape).Volume
    if v > 0.01:
        print("KOLLISION: Deckel mit Unterteil (%.2f mm3)" % v)
    # Kollisionspruefung Bauteile <-> Gehaeuse
    for name, shape in dummies.items():
        for part in ("Unterteil", "Deckel"):
            v = shape.common(objs[part].Shape).Volume
            if v > 0.5:
                print("KOLLISION: %s mit %s (%.1f mm3)" % (name, part, v))
    return doc


def export_print(objs):
    """Exportiert druckfertig ausgerichtet: Unterteil mit Boden unten, Deckel mit Front unten daneben.
    DiscCase_Druck.3mf enthaelt alle drei Teile (Logo als eigenes Objekt fuer Mehrfarbdruck)."""
    import Mesh
    flip = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 180))
    shapes = {"Unterteil": objs["Unterteil"].Shape.copy()}
    for name in ("Deckel", "Deckel_Logo"):
        s = objs[name].Shape.copy()
        s.transformShape(flip.toMatrix())
        shapes[name] = s
    lid_bb = shapes["Deckel"].BoundBox
    offset = App.Vector(W_IN / 2 + WALL + 10 - lid_bb.XMin, 0, -lid_bb.ZMin)
    for name in ("Deckel", "Deckel_Logo"):
        shapes[name].translate(offset)

    if "DiscCase_Druck" in App.listDocuments():
        App.closeDocument("DiscCase_Druck")
    pdoc = App.newDocument("DiscCase_Druck")
    feats = []
    for name, s in shapes.items():
        o = pdoc.addObject("Part::Feature", name)
        o.Shape = s
        feats.append(o)
        Mesh.export([o], os.path.join(OUT_DIR, "DiscCase_%s.stl" % name))
    pdoc.recompute()
    Mesh.export(feats, os.path.join(OUT_DIR, "DiscCase_Druck.3mf"))
    import runpy, sys
    argv = sys.argv
    sys.argv = ["group_3mf.py", os.path.join(OUT_DIR, "DiscCase_Druck.3mf"), os.path.join(OUT_DIR, "DiscCase_Druck_Bambu.3mf")]
    try:
        runpy.run_path(os.path.join(OUT_DIR, "group_3mf.py"), run_name="__main__")
    finally:
        sys.argv = argv
    for o in feats:
        b = o.Shape.BoundBox
        print("Druck %-12s z=%.2f..%.2f  x=%.1f..%.1f" % (o.Name, b.ZMin, b.ZMax, b.XMin, b.XMax))
    App.closeDocument("DiscCase_Druck")
    App.setActiveDocument(objs["Unterteil"].Document.Name)


def render_previews(doc):
    import FreeCADGui as Gui
    Gui.ActiveDocument = Gui.getDocument(doc.Name)
    view = Gui.ActiveDocument.ActiveView

    def show(names, opaque=()):
        for o in doc.Objects:
            o.ViewObject.Visibility = o.Name in names
            if o.Name in ("Unterteil", "Deckel"):
                o.ViewObject.Transparency = 0 if o.Name in opaque else 55

    show(["Deckel", "Deckel_Logo"], opaque=["Deckel"])
    view.viewTop()
    view.fitAll()
    view.saveImage(os.path.join(OUT_DIR, "preview_front.png"), 1000, 1400, "White")
    show([o.Name for o in doc.Objects if o.Name not in ("Deckel", "Deckel_Logo")])
    view.viewIsometric()
    view.fitAll()
    view.saveImage(os.path.join(OUT_DIR, "preview_inside.png"), 1400, 1000, "White")
    show(["Unterteil"], opaque=["Unterteil"])
    view.viewBottom()
    view.fitAll()
    view.saveImage(os.path.join(OUT_DIR, "preview_back.png"), 1000, 1400, "White")
    show([o.Name for o in doc.Objects])


if __name__ == "__main__":
    render_previews(build())
