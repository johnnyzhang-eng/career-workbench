"""Build one original, editable Blender desk-top mesh and export it as GLB.

Run from repository root:
  blender --background --python prototype/comparison/hero_desk_experiment/build_asset.py

The legs, chair, computer, character, lighting and camera stay in Godot's A
baseline. This file authors only the replaceable table-top mesh.
"""

from pathlib import Path

import bpy


HERE = Path(__file__).resolve().parent
GODOT_ASSET = HERE.parent.parent / "godot" / "comparison" / "assets" / "hero_desk_top.glb"
BLEND = HERE / "hero_desk_top.blend"


def material(name, color, roughness):
    mat = bpy.data.materials.new(name)
    # Principled inputs use scene-linear values; hex swatches are sRGB.
    def linear(channel):
        value = int(channel, 16) / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    rgba = tuple(linear(color[i:i + 2]) for i in (0, 2, 4)) + (1.0,)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = 0.0
    return mat


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

# Blender Z up; glTF exporter maps this horizontal top to Godot Y up.
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
top = bpy.context.object
top.name = "Student desk tabletop"
top.dimensions = (3.55, 1.35, 0.17)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

top.data.materials.append(material("Warm satin wood top", "ad7356", 0.62))
top.data.materials.append(material("Deep wood fascia", "80503d", 0.73))
top.data.materials.append(material("Soft edge highlight", "c28965", 0.58))
for face in top.data.polygons:
    face.material_index = 0 if face.normal.z > 0.9 else 1

bevel = top.modifiers.new("Rounded working edge", "BEVEL")
bevel.width = 0.04
bevel.segments = 3
bevel.affect = "EDGES"
bevel.material = 2
bevel.harden_normals = True

normals = top.modifiers.new("Stable planar normals", "WEIGHTED_NORMAL")
normals.keep_sharp = True
normals.weight = 50

assert len([obj for obj in bpy.context.scene.objects if obj.type == "MESH"]) == 1
assert len(top.data.materials) == 3
assert all(abs(actual - expected) < 0.001 for actual, expected in zip(top.dimensions, (3.55, 1.35, 0.17)))
assert not any(obj.type == "ARMATURE" for obj in bpy.context.scene.objects)

BLEND.parent.mkdir(parents=True, exist_ok=True)
GODOT_ASSET.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), compress=True)
# Keep the .blend editable; apply only to the in-memory export copy. Blender
# 5.1's glTF exporter did not evaluate these modifiers in the first dry run.
bpy.context.view_layer.objects.active = top
bpy.ops.object.modifier_apply(modifier=bevel.name)
bpy.ops.object.modifier_apply(modifier=normals.name)
bpy.ops.object.select_all(action="DESELECT")
top.select_set(True)
bpy.context.view_layer.objects.active = top
bpy.ops.export_scene.gltf(
    filepath=str(GODOT_ASSET), export_format="GLB", use_selection=True,
)
print(
    "HERO_DESK_ASSET_OK objects=1 materials=3 bevel=0.04x3 "
    f"weighted_normals=yes blend_bytes={BLEND.stat().st_size} "
    f"glb_bytes={GODOT_ASSET.stat().st_size}"
)
