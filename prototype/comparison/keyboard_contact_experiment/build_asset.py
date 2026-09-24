"""Author one original keyboard asset for the A-room's existing Keyboard node.

Run from the repository root:
  blender --background --python prototype/comparison/keyboard_contact_experiment/build_asset.py

The editable .blend retains individual rounded keys. Only the in-memory GLB
export joins by material to keep the runtime at four meshes, not 52.
"""

from pathlib import Path

import bpy


HERE = Path(__file__).resolve().parent
GLB = HERE.parent.parent / "godot" / "comparison" / "assets" / "keyboard_contact.glb"
BLEND = HERE / "keyboard_contact.blend"


def linear(channel):
    value = int(channel, 16) / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def material(name, color, roughness, metallic=0.0):
    rgba = tuple(linear(color[i:i + 2]) for i in (0, 2, 4)) + (1.0,)
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return mat


def rounded_box(name, xyz, dims, mat, radius):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=xyz)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new("Visible softened edge", "BEVEL")
    bevel.width = radius
    bevel.segments = 2
    bevel.harden_normals = True
    normals = obj.modifiers.new("Planar weighted normals", "WEIGHTED_NORMAL")
    normals.keep_sharp = True
    return obj


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
shell = material("Deep slate shell", "344742", 0.63)
ivory = material("Warm ivory keycaps", "e9e2d6", 0.72)
accent = material("Task accent keys", "db8266", 0.60)
edge = material("Warm shell edge", "7a7369", 0.55, 0.13)

# Blender Z-up: glTF maps local +Z to Godot +Y. The object is centered on the
# original Godot keyboard at (-0.82, 1.28, -1.29).
rounded_box("Keyboard lower shell", (0, 0, -0.009), (0.95, 0.28, 0.048), shell, 0.014)
rounded_box("Raised key bed", (0, 0, 0.017), (0.88, 0.226, 0.008), edge, 0.003)

# Four rows and a broad spacebar create a recognizable input surface when the
# original fixture is viewed close-up; no legible lettering is implied.
for row in range(4):
    for col in range(12):
        if row == 3 and 3 <= col <= 8:
            continue
        key_material = accent if (row == 0 and col in (0, 11)) or (row == 3 and col in (0, 11)) else ivory
        rounded_box(
            f"Key r{row + 1} c{col + 1}",
            (-0.398 + col * 0.0724, -0.083 + row * 0.0554, 0.030),
            (0.060, 0.044, 0.012), key_material, 0.0025,
        )
rounded_box("Spacebar", (0.0, 0.083, 0.030), (0.414, 0.044, 0.012), ivory, 0.003)

mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
assert len(mesh_objects) == 45  # 2 shell parts + 42 individual keys + spacebar
assert not any(obj.type == "ARMATURE" for obj in bpy.context.scene.objects)
BLEND.parent.mkdir(parents=True, exist_ok=True)
GLB.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), compress=True)

# The saved master remains separated. Apply bevels and join by material only in
# this export session; runtime draw count is determined by GLB, not .blend.
for obj in mesh_objects:
    bpy.context.view_layer.objects.active = obj
    for modifier in tuple(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=modifier.name)

for mat in (shell, edge, ivory, accent):
    same = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.data.materials[0] == mat]
    assert same
    bpy.ops.object.select_all(action="DESELECT")
    for obj in same:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = same[0]
    if len(same) > 1:
        bpy.ops.object.join()
    bpy.context.view_layer.objects.active.name = f"Joined {mat.name}"

assert len([obj for obj in bpy.context.scene.objects if obj.type == "MESH"]) == 4
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=str(GLB), export_format="GLB", use_selection=True)
print(f"KEYBOARD_ASSET_OK editable_parts=45 runtime_meshes=4 blend_bytes={BLEND.stat().st_size} glb_bytes={GLB.stat().st_size}")
