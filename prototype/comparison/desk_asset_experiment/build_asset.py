"""Pack one Poly Haven glTF/1K texture set as a Godot-ready GLB.

Run after fetch_source.py with Blender 5.1.2 in background mode. This script
does not alter the asset geometry or textures; visual fit happens in Godot.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "private/polyhaven-desk/wooden_table_02_1k.gltf"
BLEND = ROOT / "private/polyhaven-desk/wooden_table_02_1k.blend"
GLB = ROOT / "prototype/godot/comparison/assets/polyhaven_wooden_table_02_1k.glb"
assert SOURCE.is_file(), "First run fetch_source.py"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SOURCE))
meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
assert len(meshes) == 1, [obj.name for obj in meshes]
mesh = meshes[0]
assert len(mesh.data.polygons) > 0 and len(mesh.data.materials) == 1

BLEND.parent.mkdir(parents=True, exist_ok=True)
GLB.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), compress=True)
bpy.ops.object.select_all(action="DESELECT")
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
bpy.ops.export_scene.gltf(filepath=str(GLB), export_format="GLB", use_selection=True)

print("DESK_GLB", {
    "sha256": hashlib.sha256(GLB.read_bytes()).hexdigest(),
    "bytes": GLB.stat().st_size,
    "vertices": len(mesh.data.vertices),
    "polygons": len(mesh.data.polygons),
    "material": mesh.data.materials[0].name,
})
