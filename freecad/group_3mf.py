# Fasst Deckel + Logo in einer 3MF zu einem Objekt mit zwei Teilen zusammen (fuer Bambu Studio / Orca)
# Aufruf: python3 group_3mf.py DiscCase_Druck.3mf DiscCase_Druck_Bambu.3mf
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
ET.register_namespace("", NS)
q = lambda tag: "{%s}%s" % (NS, tag)

src, dst = sys.argv[1], sys.argv[2]
zin = zipfile.ZipFile(src)
root = ET.fromstring(zin.read("3D/3dmodel.model"))
resources, build = root.find(q("resources")), root.find(q("build"))

objects = resources.findall(q("object"))
names = ["Unterteil", "Deckel", "Deckel_Logo"][-len(objects):]  # Reihenfolge wie von FreeCAD exportiert, Unterteil optional
for obj, name in zip(objects, names):
    obj.set("name", name)
base = [o for o in objects if o.get("name") == "Unterteil"]
lid_parts = [o for o in objects if o.get("name") != "Unterteil"]
extruders = {"Unterteil": 1, "Deckel": 1, "Deckel_Logo": 2}  # Filament-Slot je Teil

# Ohne "BambuStudio-" als Application laedt Bambu Studio nur die Geometrie und ignoriert model_settings.config
for md in root.findall(q("metadata")):
    root.remove(md)
for i, (key, val) in enumerate((("Application", "BambuStudio-02.08.02.61"), ("BambuStudio:3mfVersion", "1"))):
    md = ET.Element(q("metadata"), name=key)
    md.text = val
    root.insert(i, md)

group = ET.SubElement(resources, q("object"), id=str(len(objects) + 1), type="model", name="Deckel_mit_Logo")
comps = ET.SubElement(group, q("components"))
for obj in lid_parts:
    ET.SubElement(comps, q("component"), objectid=obj.get("id"))

transforms = {item.get("objectid"): item.get("transform") for item in build}
for item in list(build):
    build.remove(item)
items = [(ET.SubElement(build, q("item"), objectid=b.get("id")), b) for b in base]
items.append((ET.SubElement(build, q("item"), objectid=group.get("id")), lid_parts[0]))
for item, obj in items:
    if transforms.get(obj.get("id")):
        item.set("transform", transforms[obj.get("id")])

cfg = ET.Element("config")
def add_meta(parent, key, value):
    ET.SubElement(parent, "metadata", key=key, value=str(value))
for obj, members in [(b, [b]) for b in base] + [(group, lid_parts)]:
    o = ET.SubElement(cfg, "object", id=obj.get("id"))
    add_meta(o, "name", obj.get("name"))
    add_meta(o, "extruder", extruders[members[0].get("name")])
    for m in members:
        part = ET.SubElement(o, "part", id=m.get("id") if obj is group else "1", subtype="normal_part")
        add_meta(part, "name", m.get("name"))
        add_meta(part, "extruder", extruders[m.get("name")])
plate = ET.SubElement(cfg, "plate")
add_meta(plate, "plater_id", 1)
add_meta(plate, "locked", "false")
for obj in base + [group]:
    inst = ET.SubElement(plate, "model_instance")
    add_meta(inst, "object_id", obj.get("id"))
    add_meta(inst, "instance_id", 0)
model_settings = ET.tostring(cfg, xml_declaration=True, encoding="UTF-8")

with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
    for info in zin.infolist():
        if info.filename == "3D/3dmodel.model":
            zout.writestr(info.filename, ET.tostring(root, xml_declaration=True, encoding="UTF-8"))
        else:
            zout.writestr(info, zin.read(info.filename))
    zout.writestr("Metadata/model_settings.config", model_settings)
    # Drucker-/Filament-Profile (aus einem Bambu-Studio-Projekt kopiert); ohne die stuerzt Bambu Studio ab
    project = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bambu_project_settings.config")
    if os.path.exists(project):
        zout.write(project, "Metadata/project_settings.config")
print("geschrieben:", dst)
