"""Build a seat-corrected, clearer-action R3 character from the R1 source.

Run with Blender 5.1+ from repository root. This is an intentionally small
weight/animation experiment, not a finished deformation-quality character.
"""

from pathlib import Path

import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent
R1 = HERE.parent / "character_experiment" / "adult_student.blend"
BLEND = HERE / "adult_student_rigged_r3.blend"
GLB = HERE.parent.parent / "godot" / "comparison" / "assets" / "adult_student_rigged_r3.glb"


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

# The R2 pelvis bottoms at Y=.61 inside the chair top Y=.84. Lift the pelvis
# and trunk by .23 while keeping hands at the keyboard and shoes on the floor.
# Rebuild upper sleeves and thighs between their new and fixed endpoints. This
# is a geometric seat clearance, not a cloth or physics simulation.
LIFT = 0.23
for obj in tuple(parts):
    name = obj.name.split(".")[0]
    if name in ("Typing upper sleeve", "Horizontal thigh"):
        bpy.data.objects.remove(obj, do_unlink=True)
        continue
    if name in ("Typing forearm sleeve", "Hand above keyboard", "Bent shin",
                "Seated canvas sole", "Seated canvas upper") or name.startswith("Typing finger"):
        continue
    obj.location.z += LIFT
hip_bottoms = [obj.location.z - obj.scale.z for obj in typing.objects
               if obj.type == "MESH" and obj.name.startswith("Seated trouser hip")]
assert len(hip_bottoms) == 2 and all(abs(bottom - 0.84) < 0.001 for bottom in hip_bottoms)


def link_mesh(name, start, end, radius1, radius2, material):
    begin, finish = point(*start), point(*end)
    span = finish - begin
    bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=radius1,
                                    radius2=radius2, depth=span.length,
                                    location=(begin + finish) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = span.to_track_quat("Z", "Y").to_euler()
    for old in tuple(obj.users_collection):
        old.objects.unlink(obj)
    typing.objects.link(obj)
    obj.data.materials.append(bpy.data.materials[material])
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


for side, prefix in ((-1, "Left"), (1, "Right")):
    x = side * 0.215
    link_mesh("Horizontal thigh " + prefix, (x, 0.98, 0.06),
              (x, 0.69, 0.57), 0.17, 0.15, "Soft blue denim")
    link_mesh("Typing upper sleeve " + prefix,
              (side * 0.41, 1.73, 0.03), (side * 0.48, 1.25, 0.59),
              0.155, 0.13, "Clay hoodie")
    # Conceal the disconnected rigid-weight elbow gap without pretending this
    # is continuous human skinning. The bridge is weighted to the forearm.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10,
                                         location=point(side * 0.48, 1.25, 0.59))
    bridge = bpy.context.object
    bridge.name = "Elbow bridge " + prefix
    bridge.scale = (0.133, 0.133, 0.133)
    for old in tuple(bridge.users_collection):
        old.objects.unlink(bridge)
    typing.objects.link(bridge)
    bridge.data.materials.append(bpy.data.materials["Clay hoodie"])
    for polygon in bridge.data.polygons:
        polygon.use_smooth = True
parts = [obj for obj in typing.objects if obj.type == "MESH"]
assert len(parts) == 46

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


bone("Hips", (0, 1.01, 0), (0, 1.27, 0))
bone("Spine", (0, 1.27, 0), (0, 1.75, 0), "Hips")
for side, prefix in ((-1, "Left"), (1, "Right")):
    shoulder = (side * 0.41, 1.73, 0.03)
    elbow = (side * 0.48, 1.25, 0.59)
    wrist = (side * 0.25, 1.37, 1.35)
    finger = (side * 0.25, 1.37, 1.48)
    bone(prefix + "UpperArm", shoulder, elbow, "Spine")
    bone(prefix + "Forearm", elbow, wrist, prefix + "UpperArm")
    bone(prefix + "Hand", wrist, finger, prefix + "Forearm")
    bone(prefix + "Thigh", (side * 0.215, 1.01, 0.05),
         (side * 0.215, 0.69, 0.57), "Hips")
    bone(prefix + "Shin", (side * 0.215, 0.69, 0.57),
         (side * 0.215, 0.16, 0.63), prefix + "Thigh")
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
    if name.startswith("Elbow bridge "):
        return name.rsplit(" ", 1)[-1] + "Forearm"
    if name.startswith("Horizontal thigh "):
        return name.rsplit(" ", 1)[-1] + "Thigh"
    if name == "Bent shin":
        return ("Left" if obj.location.x < 0 else "Right") + "Shin"
    if name in ("Seated canvas sole", "Seated canvas upper"):
        return ("Left" if obj.location.x < 0 else "Right") + "Shin"
    if name == "Seated trouser hip":
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
assert all(name in mesh.vertex_groups for name in ("Hips", "Spine", "LeftUpperArm", "LeftForearm", "LeftHand", "RightUpperArm", "RightForearm", "RightHand", "LeftThigh", "LeftShin", "RightThigh", "RightShin"))
assert len(mesh.data.vertices) > 0


def set_pose(frame, hips_up=0.0, spine_pitch=0.0, left=0.0, right=0.0,
             knee=0.0):
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
        upper.rotation_euler = (tap * 0.09, 0, 0)
        upper.keyframe_insert(data_path="rotation_euler", frame=frame)
        forearm = arm.pose.bones[prefix + "Forearm"]
        forearm.rotation_mode = "XYZ"
        forearm.rotation_euler = (tap * 0.25, 0, 0)
        forearm.keyframe_insert(data_path="rotation_euler", frame=frame)
        hand = arm.pose.bones[prefix + "Hand"]
        hand.rotation_mode = "XYZ"
        hand.rotation_euler = (-tap * 0.15, 0, 0)
        hand.keyframe_insert(data_path="rotation_euler", frame=frame)
        thigh = arm.pose.bones[prefix + "Thigh"]
        thigh.rotation_mode = "XYZ"
        thigh.rotation_euler = (knee * 0.28, 0, 0)
        thigh.keyframe_insert(data_path="rotation_euler", frame=frame)
        shin = arm.pose.bones[prefix + "Shin"]
        shin.rotation_mode = "XYZ"
        shin.rotation_euler = (-knee * 0.34, 0, 0)
        shin.keyframe_insert(data_path="rotation_euler", frame=frame)


arm.animation_data_create()
settle = bpy.data.actions.new("ReachToType")
arm.animation_data.action = settle
set_pose(1, hips_up=0.0, spine_pitch=0.07, left=-0.55, right=-0.55)
set_pose(10, hips_up=0.0, spine_pitch=0.03, left=-0.2, right=-0.2)
set_pose(19)
settle.use_frame_range = True
settle.frame_start, settle.frame_end = 1, 19

typing_loop = bpy.data.actions.new("TypingLoop")
arm.animation_data.action = typing_loop
set_pose(1)
set_pose(6, left=0.9, right=-0.35)
set_pose(10)
set_pose(15, left=-0.35, right=0.9)
set_pose(19)
set_pose(24, left=0.9, right=-0.35)
set_pose(28)
set_pose(33, left=-0.35, right=0.9)
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
    "R3_ASSET vertices=", len(mesh.data.vertices),
    " vertex_groups=", len(mesh.vertex_groups),
    " bones=", len(arm.data.bones),
    " actions=", [action.name for action in bpy.data.actions],
    " blend_bytes=", BLEND.stat().st_size,
    " glb_bytes=", GLB.stat().st_size,
)
