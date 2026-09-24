"""Generate and audit the original desk lamp used by the Godot room.

Run from the repository root:
  blender --background --python prototype/blender/build_lamp.py

The low-poly student and room are built from editable Godot primitives in
main.gd. This script preserves a Blender source for the imported desk prop.
"""

from pathlib import Path
import bpy
import bmesh


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "godot" / "assets" / "desk_lamp.glb"

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)


def material(name, hex_color):
    rgba = tuple(int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1.0,)
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = rgba
    principled.inputs["Roughness"].default_value = 0.78
    return mat


sage = material("Sage enamel", "83a8a0")
ink = material("Charcoal metal", "253442")
warm = material("Warm bulb", "ffe0a2")


def cylinder(name, location, radius, depth, mat, vertices=16):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth, location=location
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def shade():
    bpy.ops.mesh.primitive_cone_add(
        vertices=20,
        radius1=0.24,
        radius2=0.11,
        depth=0.30,
        location=(0.0, 0.0, 0.67),
    )
    obj = bpy.context.object
    obj.name = "Adjustable shade"
    obj.data.materials.append(sage)
    return obj


cylinder("Weighted base", (0, 0, 0.04), 0.23, 0.08, ink)
cylinder("Lower stem", (0, 0, 0.27), 0.035, 0.46, ink, 12)
cylinder("Pivot collar", (0, 0, 0.51), 0.08, 0.07, sage, 12)
shade()
cylinder("Warm bulb", (0, 0, 0.51), 0.08, 0.05, warm, 12)


mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
assert len(mesh_objects) == 5
for obj in mesh_objects:
    assert obj.data.materials, f"Missing material: {obj.name}"
    assert all(value > 0 for value in obj.dimensions), f"Bad dimensions: {obj.name}"
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.select_set(False)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    assert all(poly.normal.length > 0.99 for poly in obj.data.polygons)

# No armature or skin weights are needed for this rigid desk prop.
assert not any(obj.type == "ARMATURE" for obj in bpy.context.scene.objects)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format="GLB")
print(f"ASSET_QA_OK meshes={len(mesh_objects)} materials=3 normals=recalculated rig=n/a output={OUTPUT}")
