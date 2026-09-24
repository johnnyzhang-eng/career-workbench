"""Bind the original R1 seated mesh to a small real armature and export animation.

Run with Blender 5.1+ from repository root. This is an intentionally small
weight/animation experiment, not a finished deformation-quality character.
"""

from pathlib import Path

import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent
R1 = HERE.parent / "character_experiment" / "adult_student.blend"
BLEND = HERE / "adult_student_rigged.blend"
GLB = HERE.parent.parent / "godot" / "comparison" / "assets" / "adult_student_rigged.glb"


def point(x, y, z):
    # Input coordinates match the Godot Y-up R1 brief; Blender is Z-up.
    return Vector((x, -z, y))


bpy.ops.wm.open_mainfile(filepath=str(R1))
scene = bpy.context.scene
typing = bpy.data.collections["Adult student - typing"]
idle = bpy.data.collections["Adult student - idle"]
for obj in tuple(idle.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.data.collections.remove(idle)
# Two short index/middle fingers per hand provide an observable keyboard
# contact cue. They remain separate editable mesh pieces before joining.
for side in (-1, 1):
    for offset in (-0.044, 0.044):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=10, ring_count=8,
            location=point(side * 0.25 + offset, 1.331, 1.482),
        )
        finger = bpy.context.object
        finger.name = "Typing finger Left" if side < 0 else "Typing finger Right"
        finger.scale = (0.034, 0.087, 0.025)
        for old in tuple(finger.users_collection):
            old.objects.unlink(finger)
        typing.objects.link(finger)
        finger.data.materials.append(bpy.data.materials["Warm skin"])
        for face in finger.data.polygons:
            face.use_smooth = True
parts = [obj for obj in typing.objects if obj.type == "MESH"]
assert len(parts) == 44

arm_data = bpy.data.armatures.new("Student seated rig data")
arm = bpy.data.objects.new("Student seated rig", arm_data)
typing.objects.link(arm)
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")


def bone(name, start, end, parent=None):
    item = arm_data.edit_bones.new(name)
    item.head = point(*start)
    item.tail = point(*end)
    if parent:
        item.parent = arm_data.edit_bones[parent]
        item.use_connect = False
    return item


bone("Hips", (0, 0.78, 0), (0, 1.04, 0))
bone("Spine", (0, 1.04, 0), (0, 1.52, 0), "Hips")
for side, prefix in ((-1, "Left"), (1, "Right")):
    shoulder = (side * 0.41, 1.50, 0.03)
    elbow = (side * 0.48, 1.25, 0.59)
    wrist = (side * 0.25, 1.37, 1.35)
    finger = (side * 0.25, 1.37, 1.48)
    bone(prefix + "UpperArm", shoulder, elbow, "Spine")
    bone(prefix + "Forearm", elbow, wrist, prefix + "UpperArm")
    bone(prefix + "Hand", wrist, finger, prefix + "Forearm")
bpy.ops.object.mode_set(mode="OBJECT")


def owning_bone(obj):
    name = obj.name.split(".")[0]
    if name in ("Seated shoulder", "Typing upper sleeve", "Typing forearm sleeve", "Hand above keyboard"):
        side = "Left" if obj.location.x < 0 else "Right"
        suffix = {
            "Seated shoulder": "UpperArm",
            "Typing upper sleeve": "UpperArm",
            "Typing forearm sleeve": "Forearm",
            "Hand above keyboard": "Hand",
        }[name]
        return side + suffix
    if name.startswith("Typing finger "):
        return "LeftHand" if obj.location.x < 0 else "RightHand"
    if name in ("Seated trouser hip", "Horizontal thigh", "Bent shin", "Seated canvas sole", "Seated canvas upper"):
        return "Hips"
    return "Spine"


# R1 has separate authorable pieces. Bake only non-rig bevel/normals, then join
# to one mesh with explicit per-vertex weights. The saved R2 .blend keeps the
# Armature modifier and weight groups editable.
bpy.ops.object.select_all(action="DESELECT")
for obj in parts:
    bone_name = owning_bone(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    for modifier in tuple(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    group = obj.vertex_groups.new(name=bone_name)
    group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    obj.select_set(False)

for obj in parts:
    obj.select_set(True)
bpy.context.view_layer.objects.active = parts[0]
bpy.ops.object.join()
mesh = bpy.context.object
mesh.name = "Editable seated student skin"
mesh.parent = arm
mesh.matrix_parent_inverse = arm.matrix_world.inverted()
skin = mesh.modifiers.new("Explicit bone weights", "ARMATURE")
skin.object = arm
assert all(name in mesh.vertex_groups for name in ("Hips", "Spine", "LeftUpperArm", "LeftForearm", "LeftHand", "RightUpperArm", "RightForearm", "RightHand"))
assert len(mesh.data.vertices) > 0


def set_pose(frame, hips_up=0.0, spine_pitch=0.0, left=0.0, right=0.0):
    scene.frame_set(frame)
    hips = arm.pose.bones["Hips"]
    hips.location = (0, 0, hips_up)
    hips.keyframe_insert(data_path="location", frame=frame)
    spine = arm.pose.bones["Spine"]
    spine.rotation_mode = "XYZ"
    spine.rotation_euler = (spine_pitch, 0, 0)
    spine.keyframe_insert(data_path="rotation_euler", frame=frame)
    for prefix, tap in (("Left", left), ("Right", right)):
        upper = arm.pose.bones[prefix + "UpperArm"]
        upper.rotation_mode = "XYZ"
        upper.rotation_euler = (tap * 0.06, 0, 0)
        upper.keyframe_insert(data_path="rotation_euler", frame=frame)
        forearm = arm.pose.bones[prefix + "Forearm"]
        forearm.rotation_mode = "XYZ"
        forearm.rotation_euler = (tap * 0.16, 0, 0)
        forearm.keyframe_insert(data_path="rotation_euler", frame=frame)
        hand = arm.pose.bones[prefix + "Hand"]
        hand.rotation_mode = "XYZ"
        hand.rotation_euler = (-tap * 0.12, 0, 0)
        hand.keyframe_insert(data_path="rotation_euler", frame=frame)


arm.animation_data_create()
settle = bpy.data.actions.new("SitToType")
arm.animation_data.action = settle
set_pose(1, hips_up=0.07, spine_pitch=-0.04, left=-0.3, right=-0.3)
set_pose(10, hips_up=0.025, spine_pitch=-0.02, left=-0.1, right=-0.1)
set_pose(19)
settle.use_frame_range = True
settle.frame_start, settle.frame_end = 1, 19

typing_loop = bpy.data.actions.new("TypingLoop")
arm.animation_data.action = typing_loop
set_pose(1)
set_pose(6, left=0.75, right=-0.18)
set_pose(10)
set_pose(15, left=-0.18, right=0.75)
set_pose(19)
set_pose(24, left=0.75, right=-0.18)
set_pose(28)
set_pose(33, left=-0.18, right=0.75)
set_pose(37)
typing_loop.use_frame_range = True
typing_loop.frame_start, typing_loop.frame_end = 1, 37
scene.frame_start, scene.frame_end = 1, 37
scene.render.fps = 30
scene.frame_set(1)

HERE.mkdir(parents=True, exist_ok=True)
GLB.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), compress=True)
bpy.ops.object.select_all(action="DESELECT")
arm.select_set(True)
mesh.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.gltf(
    filepath=str(GLB), export_format="GLB", use_selection=True,
    export_animations=True, export_animation_mode="ACTIONS",
)
print(
    "R2_ASSET vertices=", len(mesh.data.vertices),
    " vertex_groups=", len(mesh.vertex_groups),
    " bones=", len(arm.data.bones),
    " actions=", [action.name for action in bpy.data.actions],
    " blend_bytes=", BLEND.stat().st_size,
    " glb_bytes=", GLB.stat().st_size,
)
