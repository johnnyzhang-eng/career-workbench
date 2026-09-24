extends "res://comparison/room_3d.gd"

# A-room clone: replace only the character. No room, camera, light or UI edits.
var imported_idle: Node3D
var imported_typing: Node3D


func _ready() -> void:
	super._ready()
	assert(not refined)
	var original := character
	remove_child(original)
	original.queue_free()
	imported_idle = _import_pose("res://comparison/assets/adult_student_idle.glb", "Adult student idle")
	imported_idle.position = home
	imported_typing = _import_pose("res://comparison/assets/adult_student_typing.glb", "Adult student typing")
	imported_typing.position = Vector3(-0.88, 0.0, 0.10)
	imported_typing.rotation.y = PI
	character = imported_idle
	hand = Node3D.new() # The inherited A idle script expects a hand target.
	add_child(hand)
	_update_pose()
	print("CHARACTER_IMPORTED idle_meshes=", imported_idle.find_children("*", "MeshInstance3D", true, false).size(),
		" typing_meshes=", imported_typing.find_children("*", "MeshInstance3D", true, false).size(),
		" camera_fov=", camera.fov)


func _import_pose(path: String, label: String) -> Node3D:
	var scene: PackedScene = load(path)
	assert(scene != null)
	var node := scene.instantiate() as Node3D
	assert(node != null)
	node.name = label
	add_child(node)
	return node


func apply_state(value: String) -> void:
	super.apply_state(value)
	_update_pose()


func _update_pose() -> void:
	if imported_idle == null or imported_typing == null:
		return
	imported_idle.visible = task_state != "in_progress"
	imported_typing.visible = task_state == "in_progress"
	print("CHARACTER_POSE ", "typing_static" if imported_typing.visible else "idle_static")
