"""Build a fictional clothed student from licensed MPFB assets for an R4 room trial.

Run from this repository root with Blender 5.1.2. The MPFB plugin and the
MakeHuman system asset pack must be installed in an isolated Blender profile;
see README.md. This is a source experiment, not a shipped character creator.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
POSE = ROOT / "private/asset-packs/poses/sweetan008_sitting-pose/sweetan008_sitting-pose.bvh"
IK = "--ik" in sys.argv
CASUAL = "--casual" in sys.argv
SUFFIX = ("_casual" if CASUAL else "") + ("_ik" if IK else "")
BLEND = ROOT / "private/mpfb-blends" / f"fictional_student_mpfb{SUFFIX}.blend"
GLB = ROOT / f"prototype/godot/comparison/assets/fictional_student_mpfb{SUFFIX}.glb"


def extension_symbol(module_suffix: str, symbol: str):
    """Resolve MPFB services independently of Blender's extension repo name."""
    for module_name in tuple(sys.modules):
        if module_name.endswith(module_suffix):
            return getattr(importlib.import_module(module_name), symbol)
    raise RuntimeError(f"MPFB module not registered: {module_suffix}")


if "bl_ext.blender_org.mpfb" not in bpy.context.preferences.addons:
    bpy.ops.preferences.addon_enable(module="bl_ext.blender_org.mpfb")
if "io_anim_bvh" not in bpy.context.preferences.addons:
    bpy.ops.preferences.addon_enable(module="io_anim_bvh")

HumanService = extension_symbol("mpfb.services.humanservice", "HumanService")
TargetService = extension_symbol("mpfb.services.targetservice", "TargetService")
AssetService = extension_symbol("mpfb.services.assetservice", "AssetService")
AnimationService = extension_symbol("mpfb.services.animationservice", "AnimationService")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
macro = TargetService.get_default_macro_info_dict()
macro["race"] = {"african": 0.0, "asian": 1.0, "caucasian": 0.0}
macro["gender"] = 0.8
macro["age"] = 0.5
basemesh = HumanService.create_human(macro_detail_dict=macro)
basemesh.name = "Fictional student - editable base"

skin_path = AssetService.find_asset_absolute_path("young_asian_male.mhmat", asset_subdir="skins")
if not skin_path:
    raise RuntimeError("Install the official makehuman_system_assets pack before running this script")
HumanService.set_character_skin(skin_path, basemesh, skin_type="GAMEENGINE")
HumanService.add_builtin_rig(basemesh, "default")

upper_and_lower = (
    ("clothes", "toigo_fisherman_sweater.mhclo", "Clothes"),
    ("clothes", "cortu_cargo_pants.mhclo", "Clothes"),
) if CASUAL else (("clothes", "male_casualsuit01.mhclo", "Clothes"),)
assets = (
    ("eyes", "low-poly.mhclo", "Eyes"),
    ("eyebrows", "eyebrow001.mhclo", "Eyebrows"),
    ("hair", "short02.mhclo", "Hair"),
) + upper_and_lower + (
    ("clothes", "shoes02.mhclo", "Clothes"),
)
for subdir, filename, asset_type in assets:
    path = AssetService.find_asset_absolute_path(filename, asset_subdir=subdir)
    if not path:
        raise RuntimeError(f"Missing official CC0 system asset: {subdir}/{filename}")
    HumanService.add_mhclo_asset(path, basemesh, asset_type=asset_type, material_type="GAMEENGINE")

rigs = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
assert len(rigs) == 1, [rig.name for rig in rigs]
rig = rigs[0]
assert POSE.is_file(), POSE
AnimationService.import_bvh_file_as_pose(rig, str(POSE))

if IK:
    # The original desk is farther from the chair than a real seated arm can
    # reach. This IK variant is paired with Godot's contact-layout experiment.
    # Targets are armature-local and correspond to the near edge of the keyboard
    # after moving the chair/character 0.55 m forward.
    for side, x in (("L", 0.25), ("R", -0.25)):
        target = bpy.data.objects.new(f"Keyboard wrist target {side}", None)
        bpy.context.scene.collection.objects.link(target)
        target.location = (x, -0.66, 1.25)
        wrist = rig.pose.bones[f"wrist.{side}"]
        constraint = wrist.constraints.new("IK")
        constraint.target = target
        constraint.chain_count = 5
        constraint.use_stretch = False
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.nla.bake(
        frame_start=1, frame_end=1, only_selected=False,
        visual_keying=True, clear_constraints=True, clear_parents=False,
        use_current_action=False, bake_types={"POSE"},
    )
    bpy.ops.object.mode_set(mode="OBJECT")
    for name in ("Keyboard wrist target L", "Keyboard wrist target R"):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    bpy.context.scene.frame_set(1)

# The source file retains the editable base, rig, and fitted clothing.
HERE.mkdir(parents=True, exist_ok=True)
BLEND.parent.mkdir(parents=True, exist_ok=True)
GLB.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), compress=True)

# Make a still frame from evaluated geometry. ExportService's character copy
# resets the pose before glTF export; simply exporting the rig with animations
# disabled also opens in its rest pose. Evaluating mesh modifiers at frame 1
# produces an honest *static* pose candidate for the room experiment.
depsgraph = bpy.context.evaluated_depsgraph_get()
static = []
for source in tuple(bpy.data.objects):
    if source.type != "MESH" or source.hide_render:
        continue
    evaluated = source.evaluated_get(depsgraph)
    posed_mesh = bpy.data.meshes.new_from_object(
        evaluated, preserve_all_data_layers=True, depsgraph=depsgraph
    )
    posed = bpy.data.objects.new(source.name + " - pose baked", posed_mesh)
    bpy.context.scene.collection.objects.link(posed)
    posed.matrix_world = source.matrix_world.copy()
    static.append(posed)
assert len(static) == (7 if CASUAL else 6), [obj.name for obj in static]
for image in bpy.data.images:
    if image.source == "FILE" and max(image.size) > 1024:
        image.scale(1024, max(1, round(image.size[1] * 1024 / image.size[0])))
bpy.ops.object.select_all(action="DESELECT")
for obj in static:
    obj.select_set(True)
bpy.context.view_layer.objects.active = static[0]
bpy.ops.export_scene.gltf(
    filepath=str(GLB), export_format="GLB", use_selection=True,
    export_animations=False, export_extras=False,
)
print("R4_EXPORT", {
    "blend_bytes": BLEND.stat().st_size,
    "glb_bytes": GLB.stat().st_size,
    "static_meshes": len(static),
    "static_vertices": sum(len(obj.data.vertices) for obj in static),
    "rig_bones": len(rig.data.bones),
    "source_pose": POSE.name,
    "keyboard_ik": IK,
    "student_casual_clothes": CASUAL,
})
