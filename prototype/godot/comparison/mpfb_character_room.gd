extends "res://comparison/character_room.gd"

# R4 keeps the original A room, camera, light, UI, and R1 idle character.
# Only the in-progress seated student is replaced by the MPFB candidate.
func _ready() -> void:
	super._ready()
	remove_child(imported_typing)
	imported_typing.queue_free()
	var suffix := "_casual" if "--mpfb-casual" in OS.get_cmdline_user_args() else ""
	suffix += "_ik" if "--mpfb-ik" in OS.get_cmdline_user_args() else ""
	var asset := "res://comparison/assets/fictional_student_mpfb" + suffix + ".glb"
	imported_typing = _import_pose(asset, "MPFB fictional student")
	imported_typing.position = Vector3(-0.88, 0.0, 0.10)
	imported_typing.rotation.y = PI
	_update_pose()
	print("R4_IMPORT meshes=", imported_typing.find_children("*", "MeshInstance3D", true, false).size(),
		" camera_fov=", camera.fov)
