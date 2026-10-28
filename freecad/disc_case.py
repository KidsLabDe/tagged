# Disc-Gehaeuse: RC522 + ESP32-C6 Super Mini (mit Lader) + 18650 + WS2812B-Streifen + KCD1-Wippschalter
# Ausfuehren in FreeCAD (Makro oder MCP Bridge). Erzeugt Dokument "DiscCase" und STLs in OUT_DIR.
# Koordinaten: x = Breite (0 = Mitte), y = Laenge (0 = Innenkante unten, USB-Seite), z = Dicke (0 = Rueckseite)
import os
import FreeCAD as App
import Part

OUT_DIR = "/home/kingbbq/src/tagged/freecad"
FONT = os.path.join(OUT_DIR, "PixelifySans-Bold.ttf")  # Pixelify Sans, statisch auf wght 700 gesetzt

TEXT_MAIN = "FANGULUS"
TEXT_TAP = "TAP HERE"
STATIONEN = (1, 2, 3, 4, 5)  # je Station ein Deckel mit grosser Ziffer

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
# ESP32-C6 Super Mini, USB-C an der unteren Wand. Akku-Pads liegen auf der Unterseite: Das Board liegt deshalb
# auf zwei Stegen C6_LIFT ueber dem Boden, darunter ein Kabelkanal mit Ausgang Richtung Akku.
C6 = (18.0, 22.5, 1.2)  # Breite x, Laenge y, Dicke
C6_LIFT = 3.0
# 18650 quer in einem Flexbatter-Halter (gedruckte Feder am Minuspol, Kontakte = Drahtwindungen durch die Schlitze),
# im Boden versenkt. Original fuer 18650: l=65.5, hf=0.75 -> 79 mm lang, passt nicht zwischen die LEDs.
# Hier kuerzer (mehr Vorspannung der Feder) und niedriger (Feder bleibt unter den LEDs). Nur ungeschuetzte Zellen.
BATT_L, BATT_D, BATT_HF = 64.0, 18.4, 0.6  # Flexbatter-Parameter l, d, hf
BATT_CY = 40.0
# KCD1-Wippschalter in der Rueckwand, in einer Mulde versenkt, damit er beim Aufhaengen nicht aufliegt
KCD1_CUT = (13.0, 19.2)  # Einbauoeffnung x, y
KCD1_BEZEL = (15.0, 21.0)  # Rahmen aussen
KCD1_DEPTH = 17.0  # Koerper + Loetfahnen unter der Platte
KCD1_POS = (29.0, 82.0)
KCD1_WELL, KCD1_PANEL = 3.0, 1.6  # Muldentiefe von hinten, Plattenstaerke (Rastnasen: 1-2 mm)
# Haken oben zum Aufhaengen (flach in der Rueckenebene, z.B. auf Naegel oder Schrauben)
HOOK_X = 12.0  # Abstand des Stiels von der Mitte
HOOK_W, HOOK_T, HOOK_RI, HOOK_GAP = 5.0, 4.0, 3.0, 5.0  # Stegbreite, Dicke, Innenradius, Einfaedelspalt
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


def text_faces(text, width, cx, cy, height=None):
    """Text als Flaechen, skaliert auf die Breite `width` (mm) bzw. Hoehe `height`, zentriert auf (cx, cy)."""
    import Draft
    doc = App.ActiveDocument
    ss = Draft.make_shapestring(String=text, FontFile=FONT, Size=10.0, Tracking=0.0)
    doc.recompute()
    shape = ss.Shape.copy()
    doc.removeObject(ss.Name)
    bb = shape.BoundBox
    shape.translate(App.Vector(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, 0))
    shape.scale(height / bb.YLength if height else width / bb.XLength)
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


def logo_solid(station):
    """Alle Front-Grafiken als 2D-Flaechen -> extrudiert auf LOGO_DEPTH, oben buendig mit dem Deckel."""
    solids = []
    # Kontaktlos-Symbol ueber der Antenne
    icx, icy = 0.0, 101.0
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
    # TAP HERE in der Lesezone, darunter grosse Stationsnummer und FANGULUS
    for f in (text_faces(TEXT_TAP, 40.0, 0, 83.0), text_faces(str(station), None, 0, 41.0, height=34.0),
              text_faces(TEXT_MAIN, 64.0, 0, 12.0)):
        flat.append(f.extrude(App.Vector(0, 0, 1)))
    logo = flat[0].fuse(flat[1:]).removeSplitter()
    logo.scale(1.0)
    m = App.Matrix()
    m.scale(1, 1, LOGO_DEPTH)
    logo = logo.transformGeometry(m)
    logo.translate(App.Vector(0, 0, Z_TOP + LID - LOGO_DEPTH))
    return logo


# --- Flexbatter -----------------------------------------------------------------------------------------------
# Portiert aus flexbatter.scad von Heinz Spiess (2014, CC BY-SA, https://www.thingiverse.com/thing:456900),
# n=1, ohne Schraubloecher und ohne Kanaele in der Unterseite (die liegt hier auf dem Gehaeuseboden).
FB_EW = 0.56
FB_W, FB_WS = 4 * FB_EW, 2 * FB_EW  # Wand, Federwand
FB_CH = FB_W - FB_WS


def fb_arc(r1, r2, h, a):
    """Ringsektor von 180 bis 180+a Grad (wie arc(r1, r2, a1=a, a2=0) im Original)."""
    s = Part.makeCylinder(r2, h, App.Vector(0, 0, 0), App.Vector(0, 0, 1), a).cut(cyl(r1, h + 2, 0, 0, -1))
    s.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 180)
    return s


def fb_sline(angle, radius, i, w, h):
    """Schlangenlinie aus Boegen (angle != 0) und Geraden (angle == 0, Laenge radius), wie sline() im Original."""
    a, r = angle[i], abs(radius[i])
    parts = [box(-w / 2, -r - 0.01, 0, w, 0.02, h)]
    if a:
        parts.append(fb_arc(r - w / 2, r + w / 2, h, abs(a)))
    elif r > 0:
        parts.append(box(-w / 2, -r, 0, w, r, h))
    if i + 1 < len(angle):
        sub = fb_sline(angle, radius, i + 1, w, h)
        sub.translate(App.Vector(-r, 0, 0) if a else App.Vector(0, -r, 0))
        sub.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), a)
        parts.append(sub)
    s = parts[0].fuse(parts[1:])
    if a:
        s.translate(App.Vector(r, 0, 0))
    if a < 0:
        s = s.mirror(App.Vector(0, 0, 0), App.Vector(1, 0, 0))
    return s


def flexbatter(l, d, hf, el=0.0, eps=0.28):
    """Halter in eigenen Koordinaten: Akku entlang x, Minuspol (Feder) bei x=0, Pluspol bei x=l, Unterseite z=0."""
    w, ws, ch = FB_W, FB_WS, FB_CH
    r = d / 5 + 2 * ws
    hb = hf * d + w + ch
    body = box(0, -w - d / 2, 0, l + w, d + 2 * w, hb)
    body = body.makeChamfer(ch, [e for e in body.Edges if e.BoundBox.ZMax > 1e-6])
    body = body.cut([box(-2, -d / 2, w, 2 + l, d, d + 1), box(-1, -d / 2, -1, 2, d, d + w + 2),
                     Part.makeCylinder(d / 2 + eps, l + 1, App.Vector(-1, 0, d / 2 + w), App.Vector(1, 0, 0))])
    D = d + 2 * w - 2 * ws - 0.7
    springs = []
    for sy in (1, -1):
        sp = fb_sline([0, 180, 0, 180, 0, -180, 0, 90, 0],
                      [r + ch + el, D / 4, el, D / 12, el / 2, D / 12, 1 + el / 2, D / 5, D / 3], 0, ws, hf * d + w)
        sp.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), -90)
        sp.translate(App.Vector(ch, d / 2 + w - ws / 2, 0))
        springs.append(sp if sy > 0 else sp.mirror(App.Vector(0, 0, 0), App.Vector(0, 1, 0)))
    h = body.fuse(springs)
    cut = []
    # Schlitze fuer die Kontaktwindungen (Plus- und Minuspol)
    for z in (-2 * ws, 2 * ws):
        cut.append(box(-2 * ws, -w, w - ws / 2 + d / 2 + z, l + 2 * w + 2, 2 * w, ws))
    # Durchgaenge fuer Draehte unten in den Seitenwaenden und an der Plus-Stirnwand
    for sy in (1, -1):
        for c in [box(l - 1, -d / 2, w, w + 2, 2, 2)] + [box(x, -d / 2 - w - ws - 1, w, 3, w + ws + 3, 2) for x in (3, l - 7)]:
            cut.append(c if sy < 0 else c.mirror(App.Vector(0, 0, 0), App.Vector(0, 1, 0)))
    # Gravur: Akku-Symbol, Plus und Minus
    eh = 0.25
    for cx, cy, dx, dy in ((w + l / 2, d / 4 + 1, l / 5, d / 4.5), (w + l / 2 + l / 10, d / 4 + 1, d / 7, d / 10),
                           (w + l / 2 + l / 5, d / 4 + 1, 1, d / 4), (w + l / 2 + l / 5, d / 4 + 1, d / 4, 1),
                           (w + l / 2 - l / 5, d / 4 + 1, 1, d / 4)):
        cut.append(box(cx - dx / 2, cy - dy / 2, w - 2 * eh, dx, dy, 4 * eh))
    h = h.cut(cut)
    # Kontaktbuckel quer an beiden Polen
    bulges = []
    for x in (-0.3, l):
        bulges += [Part.makeCylinder(ws, 6, App.Vector(x, -3, w + d / 2), App.Vector(0, 1, 0)),
                   Part.makeSphere(ws, App.Vector(x, -3, w + d / 2)), Part.makeSphere(ws, App.Vector(x, 3, w + d / 2))]
    return h.fuse(bulges).removeSplitter()


_HOLDER = {}


def holder_x_range():
    """Halter so verschieben, dass er inklusive Feder mittig liegt: Rueckgabe (x des Minuspols, Gesamtlaenge)."""
    key = (BATT_L, BATT_D, BATT_HF)
    if key not in _HOLDER:
        _HOLDER[key] = flexbatter(*key)
    bb = _HOLDER[key].BoundBox
    return -(bb.XMin + bb.XMax) / 2, bb.XLength


def battery_holder():
    x0, _ = holder_x_range()
    h = _HOLDER[(BATT_L, BATT_D, BATT_HF)].copy()
    h.translate(App.Vector(x0, BATT_CY, 0))  # Unterseite auf der Rueckseite, Boden des Halters ersetzt den Gehaeuseboden
    return h


def make_base():
    outer = rrect(W_IN + 2 * WALL, L_IN + 2 * WALL, R_IN + WALL, Z_TOP)
    inner = rrect(W_IN, L_IN, R_IN, H_IN + 1, FLOOR)
    led = rrect(W_IN + 2 * LED_RECESS, L_IN + 2 * LED_RECESS, R_IN + LED_RECESS, LED_Z1 - LED_Z0, LED_Z0)
    led_chamfer = Part.makeLoft([
        rrect_wire(W_IN + 2 * LED_RECESS, L_IN + 2 * LED_RECESS, R_IN + LED_RECESS, LED_Z1),
        rrect_wire(W_IN, L_IN, R_IN, LED_Z1 + LED_RECESS)], True)
    base = outer.cut(inner).cut(led).cut(led_chamfer)

    add = []
    # Board-Rahmen fuer den C6 Super Mini (3 Seiten, offen zur USB-Wand), Board liegt auf zwei Stegen
    bw, bl, bt = C6
    x0, g, t = -bw / 2, CLR, 1.2
    hf = C6_LIFT + bt + 1.0
    add += [box(x0 - g - t, 0, FLOOR, t, bl + g + t, hf),
            box(x0 + bw + g, 0, FLOOR, t, bl + g + t, hf),
            box(x0 - g - t, bl + g, FLOOR, bw + 2 * g + 2 * t, t, hf),
            box(x0 - g, 0, FLOOR, bw + 2 * g, 2.0, C6_LIFT),
            box(x0 - g, bl - 2.0, FLOOR, bw + 2 * g, 2.0 + g, C6_LIFT)]
    # 18650-Halter
    add.append(battery_holder())
    # Mulde mit Platte fuer den KCD1 (Rueckwand lokal verstaerkt)
    kx, ky = KCD1_POS
    ex, ey = KCD1_BEZEL
    add.append(box(kx - ex / 2 - 2.5, ky - ey / 2 - 2.5, 0, ex + 5, ey + 5, KCD1_WELL + KCD1_PANEL))
    # Haken oben, nach aussen gebogen; der Nagel wird durch den Spalt zwischen Hakenspitze und Kante eingefaedelt
    y_edge = L_IN + WALL
    yc = y_edge + HOOK_GAP + 3.0
    for sx in (-1, 1):
        xs = sx * HOOK_X
        xc = sx * (HOOK_X + HOOK_W / 2 + HOOK_RI)
        arc = cyl(HOOK_RI + HOOK_W, HOOK_T, xc, yc, 0).cut(cyl(HOOK_RI, HOOK_T + 2, xc, yc, -1)).common(
            box(xc - 20, yc, -1, 40, 20, HOOK_T + 2))
        tip_x = xc + sx * HOOK_RI if sx > 0 else xc - HOOK_RI - HOOK_W
        add += [box(xs - HOOK_W / 2, L_IN, 0, HOOK_W, yc - L_IN, HOOK_T), arc,
                box(tip_x, y_edge + HOOK_GAP, 0, HOOK_W, yc - y_edge - HOOK_GAP, HOOK_T),
                cyl(HOOK_W / 2, HOOK_T, tip_x + HOOK_W / 2, y_edge + HOOK_GAP, 0)]
    # Rohr fuer die Kordel
    add.append(cyl(5.0, Z_TOP, LANYARD[0], LANYARD[1], 0))
    base = base.fuse(add)

    cut = []
    # USB-C-Oeffnung in der unteren Wand
    zc = FLOOR + C6_LIFT + bt + 1.6
    cut.append(box(-5.5, -WALL - 1, zc - 2.75, 11, WALL + 1.5, 5.5))
    # Kabelkanal unter dem Board Richtung Akku
    cut.append(box(-4.0, bl - 3.0, FLOOR, 8.0, g + t + 4.0, C6_LIFT))
    # KCD1: Mulde von hinten und Einbauoeffnung
    cut.append(box(kx - ex / 2 - 0.5, ky - ey / 2 - 0.5, -1, ex + 1, ey + 1, KCD1_WELL + 1))
    cx_, cy_ = KCD1_CUT
    cut.append(box(kx - cx_ / 2, ky - cy_ / 2, -1, cx_, cy_, KCD1_WELL + KCD1_PANEL + 2))
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
    bw, bl, bt = C6
    d["C6SuperMini"] = box(-bw / 2, 0, FLOOR + C6_LIFT, bw, bl, bt).fuse(
        box(-4.5, -0.5, FLOOR + C6_LIFT + bt, 9, 7.5, 3.2))
    # Zelle zwischen den Kontaktbuckeln (die echte Zelle drueckt die Feder um ca. 2-3 mm zusammen)
    x0, _ = holder_x_range()
    d["Akku18650"] = Part.makeCylinder(BATT_D / 2, BATT_L - 2.3, App.Vector(x0 + 1.0, BATT_CY, 2.24 + BATT_D / 2),
                                       App.Vector(1, 0, 0))
    kx, ky = KCD1_POS
    d["Schalter"] = box(kx - KCD1_BEZEL[0] / 2, ky - KCD1_BEZEL[1] / 2, KCD1_WELL - 2.0, KCD1_BEZEL[0], KCD1_BEZEL[1],
                        2.0).fuse(box(kx - 6.4, ky - 9.5, KCD1_WELL, 12.8, 19.0, KCD1_PANEL + KCD1_DEPTH))
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
    logo = logo_solid(STATIONEN[0])
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
                  "Bauteil_RC522": (0.1, 0.3, 0.8), "Bauteil_C6SuperMini": (0.2, 0.2, 0.2),
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
    export_print({n: objs[n].Shape for n in ("Unterteil", "Deckel", "Deckel_Logo")}, "Druck", stl=True)
    # Je Station eine Front (Deckel + Logo) zum Einzeldruck
    for nr in STATIONEN:
        logo_nr = logo_solid(nr)
        lid_nr, inlay_nr = lid_full.cut(logo_nr), logo_nr.common(lid_full)
        print("Front %d       valid=%s solids=%d/%d" % (
            nr, lid_nr.isValid() and inlay_nr.isValid(), len(lid_nr.Solids), len(inlay_nr.Solids)))
        export_print({"Deckel": lid_nr, "Deckel_Logo": inlay_nr}, "Front_%d" % nr)

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


def export_print(parts, tag, stl=False):
    """Exportiert druckfertig ausgerichtet: Unterteil (falls dabei) mit Boden unten, Deckel mit Front unten daneben.
    DiscCase_<tag>.3mf enthaelt alle Teile (Logo als eigenes Objekt fuer Mehrfarbdruck)."""
    import Mesh
    flip = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 180))
    shapes = {"Unterteil": parts["Unterteil"].copy()} if "Unterteil" in parts else {}
    for name in ("Deckel", "Deckel_Logo"):
        s = parts[name].copy()
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
        if stl:
            Mesh.export([o], os.path.join(OUT_DIR, "DiscCase_%s.stl" % name))
    pdoc.recompute()
    Mesh.export(feats, os.path.join(OUT_DIR, "DiscCase_%s.3mf" % tag))
    import runpy, sys
    argv = sys.argv
    sys.argv = ["group_3mf.py", os.path.join(OUT_DIR, "DiscCase_%s.3mf" % tag), os.path.join(OUT_DIR, "DiscCase_%s_Bambu.3mf" % tag)]
    try:
        runpy.run_path(os.path.join(OUT_DIR, "group_3mf.py"), run_name="__main__")
    finally:
        sys.argv = argv
    for o in feats:
        b = o.Shape.BoundBox
        print("Druck %-12s z=%.2f..%.2f  x=%.1f..%.1f" % (o.Name, b.ZMin, b.ZMax, b.XMin, b.XMax))
    App.closeDocument("DiscCase_Druck")
    App.setActiveDocument("DiscCase")


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
