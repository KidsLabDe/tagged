# Baut PrusaSlicer-Projekte (2.x) fuer die Prusa MK4 ohne MMU: zwei Fronten je Platte, Logo auf Extruder 1,
# Deckel auf Extruder 2, Farbwechsel per M600 innerhalb der Schicht (Single Extruder Multi Material, kein Reinigungsturm).
# Logo zuerst: Schicht 1 beginnt schwarz, so reichen 3 Wechsel (je einer in Schicht 1-3).
# Aufruf: python3 prusa_3mf.py   (liest DiscCase_Front_N.3mf, schreibt DiscCase_Prusa_*.3mf)
import os
import zipfile
import xml.etree.ElementTree as ET

DIR = os.path.dirname(os.path.abspath(__file__))
NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
q = lambda tag: "{%s}%s" % (NS, tag)

PLATTEN = {"DiscCase_Prusa_Front_1_2.3mf": (1, 2), "DiscCase_Prusa_Front_3_4.3mf": (3, 4),
           "DiscCase_Prusa_Front_5.3mf": (5,)}
BED_X, BED_Y = 250.0, 210.0
ABSTAND = 10.0  # Luecke zwischen zwei Deckeln
FARBEN = ("#1A1A1A", "#C0AAC8")  # Extruder 1 Logo, Extruder 2 Deckel

# Aenderungen gegenueber dem MK4-Profil (prusa_mk4.ini)
MM = {
    "nozzle_diameter": "0.4,0.4",
    "single_extruder_multi_material": "1",
    "wipe_tower": "0",
    # kein M600 beim ersten Werkzeug; T0/T1 entfernen, die MK4 hat nur ein Werkzeug
    "toolchange_gcode": "{if previous_extruder >= 0}M600{endif}",
    "gcode_substitutions": '"^T[01]$";"";"r";"MK4 ohne MMU: keine Werkzeugbefehle"',
    "extruder_colour": '"%s";"%s"' % FARBEN,
    "filament_colour": "%s;%s" % FARBEN,
    "filament_settings_id": '"Generic PLA @PGIS";"Generic PLA @PGIS"',
}


def read_parts(path):
    """Liest Deckel und Logo aus der FreeCAD-3MF, Build-Transformationen angewendet."""
    root = ET.fromstring(zipfile.ZipFile(path).read("3D/3dmodel.model"))
    meshes = {}
    for obj in root.find(q("resources")).findall(q("object")):
        m = obj.find(q("mesh"))
        verts = [(float(v.get("x")), float(v.get("y")), float(v.get("z"))) for v in m.find(q("vertices"))]
        tris = [(int(t.get("v1")), int(t.get("v2")), int(t.get("v3"))) for t in m.find(q("triangles"))]
        meshes[obj.get("id")] = (verts, tris)
    parts = []
    for item in root.find(q("build")):
        verts, tris = meshes[item.get("objectid")]
        t = [float(x) for x in (item.get("transform") or "1 0 0 0 1 0 0 0 1 0 0 0").split()]
        verts = [(x * t[0] + y * t[3] + z * t[6] + t[9], x * t[1] + y * t[4] + z * t[7] + t[10],
                  x * t[2] + y * t[5] + z * t[8] + t[11]) for x, y, z in verts]
        parts.append((verts, tris))
    return parts  # Reihenfolge wie von FreeCAD exportiert: Deckel, Deckel_Logo


def write_project(dst, fronts, config):
    model = ET.Element("model", {"unit": "millimeter", "xml:lang": "en-US", "xmlns": NS,
                                 "xmlns:slic3rpe": "http://schemas.slic3r.org/3mf/2017/06"})
    ET.SubElement(model, "metadata", name="slic3rpe:Version3mf").text = "1"
    resources, build = ET.SubElement(model, "resources"), ET.SubElement(model, "build")
    cfg = ET.Element("config")
    for i, nr in enumerate(fronts):
        parts = read_parts(os.path.join(DIR, "DiscCase_Front_%d.3mf" % nr))
        allv = [v for verts, _ in parts for v in verts]
        cx = (min(v[0] for v in allv) + max(v[0] for v in allv)) / 2
        cy = (min(v[1] for v in allv) + max(v[1] for v in allv)) / 2
        z0 = min(v[2] for v in allv)
        width = max(v[0] for v in allv) - min(v[0] for v in allv)
        px = BED_X / 2 + (i - (len(fronts) - 1) / 2) * (width + ABSTAND)

        obj = ET.SubElement(resources, "object", id=str(i + 1), type="model")
        mesh = ET.SubElement(obj, "mesh")
        vs, ts = ET.SubElement(mesh, "vertices"), ET.SubElement(mesh, "triangles")
        ocfg = ET.SubElement(cfg, "object", id=str(i + 1), instances_count="1")
        ET.SubElement(ocfg, "metadata", type="object", key="name", value="Fangulus Front %d" % nr)
        offset, first = 0, 0
        for (verts, tris), name, extruder in zip(parts, ("Deckel", "Deckel_Logo"), (2, 1)):
            for x, y, z in verts:
                ET.SubElement(vs, "vertex", x="%.4f" % (x - cx), y="%.4f" % (y - cy), z="%.4f" % (z - z0))
            for a, b, c in tris:
                ET.SubElement(ts, "triangle", v1=str(a + offset), v2=str(b + offset), v3=str(c + offset))
            vol = ET.SubElement(ocfg, "volume", firstid=str(first), lastid=str(first + len(tris) - 1))
            for key, value in (("name", name), ("volume_type", "ModelPart"), ("extruder", extruder)):
                ET.SubElement(vol, "metadata", type="volume", key=key, value=str(value))
            offset += len(verts)
            first += len(tris)
        ET.SubElement(build, "item", objectid=str(i + 1),
                      transform="1 0 0 0 1 0 0 0 1 %.3f %.3f 0" % (px, BED_Y / 2), printable="1")

    content_types = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
                     '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel-1" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", ET.tostring(model, xml_declaration=True, encoding="UTF-8"))
        z.writestr("Metadata/Slic3r_PE_model.config", ET.tostring(cfg, xml_declaration=True, encoding="UTF-8"))
        z.writestr("Metadata/Slic3r_PE.config", config)
    print("geschrieben:", dst)


def load_config():
    lines = []
    for line in open(os.path.join(DIR, "prusa_mk4.ini"), encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("# generated by"):
            lines.append(";" + line[1:])
        elif line and not line.startswith("#"):
            key, _, value = line.partition(" = ")
            lines.append("; %s = %s" % (key, MM.get(key, value)))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    config = load_config()
    for name, fronts in PLATTEN.items():
        write_project(os.path.join(DIR, name), fronts, config)
