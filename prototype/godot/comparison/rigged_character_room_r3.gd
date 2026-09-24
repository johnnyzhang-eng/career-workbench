extends "res://comparison/character_room.gd"

# R3 changes only R1's in-progress seated character. The A room is untouched.
var player: AnimationPlayer
var skeleton: Skeleton3D


func _ready() -> void:
	super._ready()
	var old_pose := imported_typing
	remove_child(old_pose)
	old_pose.queue_free()
	imported_typing = _import_pose("res://comparison/assets/adult_student_rigged_r3.glb", "R3 seated student")
	imported_typing.position = Vector3(-0.86, 0.0, 0.10)
	imported_typing.rotation.y = PI
	var players := imported_typing.find_children("*", "AnimationPlayer", true, false)
	var skeletons := imported_typing.find_children("*", "Skeleton3D", true, false)
	assert(players.size() == 1 and skeletons.size() == 1)
	player = players[0] as AnimationPlayer
	skeleton = skeletons[0] as Skeleton3D
	var names := player.get_animation_list()
	assert(player.has_animation("ReachToType") and player.has_animation("TypingLoop"))
	assert(skeleton.get_bone_count() == 12)
	player.get_animation("TypingLoop").loop_mode = Animation.LOOP_LINEAR
	player.animation_finished.connect(_on_animation_finished)
	_update_pose()
	if task_state == "in_progress":
		player.play("ReachToType")
	print("R3_GODOT_IMPORT skeleton_bones=", skeleton.get_bone_count(),
		" animations=", names,
		" meshes=", imported_typing.find_children("*", "MeshInstance3D", true, false).size(),
		" camera_fov=", camera.fov, " typing_loop_mode=", player.get_animation("TypingLoop").loop_mode)


func apply_state(value: String) -> void:
	super.apply_state(value)
	if player == null:
		return
	if task_state == "in_progress":
		player.play("ReachToType")
	else:
		player.stop()


func _on_animation_finished(name: StringName) -> void:
	if name == &"ReachToType" and task_state == "in_progress":
		player.play("TypingLoop")
		print("R3_LOOP_STARTED")
