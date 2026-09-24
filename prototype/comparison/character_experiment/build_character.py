"""Author two editable, original adult-student poses for the A-room experiment.

Blender 5.x: blender --background --python prototype/comparison/character_experiment/build_character.py
The seated model is a deliberately static typing pose, not a rig or animation.
"""

from pathlib import Path

import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent.parent / "godot" / "comparison" / "assets"


def point(x, y, z):
    # Author coordinates in Godot's Y-up convention. glTF converts Blender Z-up.
    return Vector((x, -z, y))


def linear(value):
    value = int(value, 16) / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def material(name, hexa, roughness=0.82):
    rgba = tuple(linear(hexa[i:i + 2]) for i in (0, 2, 4)) + (1.0,)
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = rgba
    principled.inputs["Roughness"].default_value = roughness
    return mat


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
MATS = {
    "skin": material("Warm skin", "ddad88"),
    "hair": material("Warm dark hair", "3b3534"),
    "coat": material("Clay hoodie", "ba664d"),
    "coat_dark": material("Hoodie shadow and rib", "8b473d"),
    "shirt": material("Cream tee", "eee2ca"),
    "pants": material("Soft blue denim", "516a75"),
    "shoe": material("Charcoal canvas", "27383f"),
    "sole": material("Warm white sole", "e7ddca"),
}


def collect(obj, collection, name, mat):
    obj.name = name
    for old in tuple(obj.users_collection):
        old.objects.unlink(obj)
    collection.objects.link(obj)
    obj.data.materials.append(MATS[mat])
    if obj.type == "MESH":
        for poly in obj.data.polygons:
            poly.use_smooth = True
    return obj


def ellipsoid(collection, name, center, size, mat, segments=20, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=point(*center))
    obj = bpy.context.object
    obj.scale = (size[0], size[2], size[1])
    return collect(obj, collection, name, mat)


def box(collection, name, center, size, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=point(*center))
    obj = bpy.context.object
    obj.dimensions = (size[0], size[2], size[1])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    collect(obj, collection, name, mat)
    if bevel:
        mod = obj.modifiers.new("Soft authored edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        obj.modifiers.new("Weighted face normals", "WEIGHTED_NORMAL")
    return obj


def limb(collection, name, start, end, radius, mat, end_radius=None):
    begin, finish = point(*start), point(*end)
    span = finish - begin
    bpy.ops.mesh.primitive_cone_add(
        vertices=16, radius1=radius, radius2=end_radius or radius * 0.88,
        depth=span.length, location=(begin + finish) / 2,
    )
    obj = bpy.context.object
    obj.rotation_euler = span.to_track_quat("Z", "Y").to_euler()
    return collect(obj, collection, name, mat)


def face_and_hair(collection, head_y):
    ellipsoid(collection, "Adult head", (0, head_y, 0), (0.335, 0.365, 0.31), "skin")
    ellipsoid(collection, "Layered hair crown", (0, head_y + 0.205, -0.055), (0.37, 0.20, 0.34), "hair")
    for x in (-0.25, -0.14, -0.03, 0.10, 0.23):
        ellipsoid(collection, "Separated dark fringe", (x, head_y + 0.22 - abs(x) * 0.24, 0.25),
                  (0.12, 0.10 + abs(x) * 0.09, 0.09), "hair", 12, 8)
    for x in (-0.34, 0.34):
        ellipsoid(collection, "Short side hair", (x, head_y + 0.015, -0.045),
                  (0.085, 0.21, 0.19), "hair", 12, 8)
        ellipsoid(collection, "Ear", (x * 0.98, head_y - 0.025, 0),
                  (0.07, 0.105, 0.05), "skin", 12, 8)
    for x in (-0.135, 0.135):
        ellipsoid(collection, "Eye", (x, head_y + 0.02, 0.301),
                  (0.033, 0.042, 0.016), "hair", 10, 8)
    ellipsoid(collection, "Nose", (0, head_y - 0.10, 0.31),
              (0.055, 0.056, 0.045), "skin", 12, 8)


def upper_body(collection, hip_y, seated=False):
    chest_y = hip_y + 0.58
    ellipsoid(collection, "Tapered hoodie shell", (0, hip_y + 0.46, 0),
              (0.42, 0.56, 0.315), "coat")
    box(collection, "Hoodie hem", (0, hip_y + 0.07, 0),
        (0.70, 0.12, 0.58), "coat_dark", 0.055)
    ellipsoid(collection, "Raised hood", (0, chest_y + 0.20, -0.24),
              (0.35, 0.25, 0.19), "coat_dark")
    ellipsoid(collection, "Tee at neckline", (0, chest_y + 0.24, 0.215),
              (0.17, 0.105, 0.065), "shirt")
    box(collection, "Front kangaroo pocket", (0, hip_y + 0.29, 0.304),
        (0.38, 0.20, 0.025), "coat_dark", 0.022)
    for x in (-0.085, 0.085):
        limb(collection, "Cotton drawstring", (x, chest_y + 0.21, 0.295),
             (x, chest_y - 0.005, 0.32), 0.012, "shirt", 0.011)
    ellipsoid(collection, "Neck", (0, chest_y + 0.305, 0), (0.11, 0.15, 0.11), "skin")
    head_y = chest_y + (0.67 if not seated else 0.61)
    face_and_hair(collection, head_y)
    return chest_y


def build_idle(collection):
    hip_y = 0.79
    chest = upper_body(collection, hip_y)
    for side in (-1, 1):
        x = side * 0.22
        ellipsoid(collection, "Denim hip", (x, 0.79, 0), (0.21, 0.20, 0.22), "pants")
        limb(collection, "Tapered trouser leg", (x, 0.71, 0),
             (x + side * 0.02, 0.17, 0.025), 0.16, "pants", 0.12)
        box(collection, "Canvas shoe sole", (x, 0.066, 0.12),
            (0.33, 0.11, 0.47), "sole", 0.045)
        box(collection, "Canvas shoe upper", (x, 0.145, 0.09),
            (0.31, 0.16, 0.42), "shoe", 0.07)
        shoulder = (side * 0.43, chest + 0.14, 0)
        elbow = (side * 0.53, chest - 0.18, 0.07)
        wrist = (side * 0.44, chest - 0.46, 0.15)
        ellipsoid(collection, "Hoodie shoulder", shoulder, (0.19, 0.19, 0.19), "coat")
        limb(collection, "Full hoodie sleeve", shoulder, elbow, 0.17, "coat", 0.14)
        limb(collection, "Cuffed sleeve", elbow, wrist, 0.14, "coat", 0.105)
        ellipsoid(collection, "Hand", (wrist[0], wrist[1] - 0.05, wrist[2] + 0.02),
                  (0.12, 0.15, 0.10), "skin", 12, 8)


def build_typing(collection):
    # Chair seat Y=0.75, keyboard Y=1.28 and Z=-1.29 in original A.
    hip_y = 0.78
    chest = upper_body(collection, hip_y, seated=True)
    for side in (-1, 1):
        x = side * 0.215
        ellipsoid(collection, "Seated trouser hip", (x, hip_y, 0.05),
                  (0.20, 0.17, 0.28), "pants")
        limb(collection, "Horizontal thigh", (x, 0.75, 0.06),
             (x, 0.69, 0.57), 0.17, "pants", 0.15)
        limb(collection, "Bent shin", (x, 0.69, 0.57),
             (x, 0.16, 0.63), 0.15, "pants", 0.11)
        box(collection, "Seated canvas sole", (x, 0.062, 0.76),
            (0.32, 0.11, 0.43), "sole", 0.045)
        box(collection, "Seated canvas upper", (x, 0.14, 0.74),
            (0.30, 0.16, 0.39), "shoe", 0.07)
        shoulder = (side * 0.41, chest + 0.14, 0.03)
        elbow = (side * 0.48, 1.25, 0.59)
        wrist = (side * 0.25, 1.37, 1.35)
        ellipsoid(collection, "Seated shoulder", shoulder, (0.17, 0.18, 0.18), "coat")
        limb(collection, "Typing upper sleeve", shoulder, elbow, 0.15, "coat", 0.13)
        limb(collection, "Typing forearm sleeve", elbow, wrist, 0.13, "coat", 0.10)
        ellipsoid(collection, "Hand above keyboard", (wrist[0], 1.37, 1.38),
                  (0.12, 0.065, 0.14), "skin", 12, 8)


collections = {}
for pose in ("idle", "typing"):
    collection = bpy.data.collections.new("Adult student - " + pose)
    bpy.context.scene.collection.children.link(collection)
    collections[pose] = collection
build_idle(collections["idle"])
build_typing(collections["typing"])
for unused in tuple(bpy.data.materials):
    if unused.users == 0:
        bpy.data.materials.remove(unused)

HERE.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "adult_student.blend"), compress=True)
# Preserve editable bevel/normal modifiers in the .blend and bake them only
# into the exported GLBs; Blender's exporter can omit unevaluated modifiers.
for collection in collections.values():
    for obj in collection.objects:
        if obj.type != "MESH":
            continue
        bpy.context.view_layer.objects.active = obj
        for mod in list(obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=mod.name)
for pose, collection in collections.items():
    bpy.ops.object.select_all(action="DESELECT")
    for obj in collection.objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = next(iter(collection.objects))
    target = ASSETS / f"adult_student_{pose}.glb"
    bpy.ops.export_scene.gltf(filepath=str(target), export_format="GLB", use_selection=True)
    print(f"CHARACTER_ASSET pose={pose} objects={len(collection.objects)} bytes={target.stat().st_size}")
print(f"CHARACTER_SOURCE bytes={(HERE / 'adult_student.blend').stat().st_size}")
