extends "res://comparison/mpfb_character_room.gd"

var camera_target := Vector3(0, 1.25, 0)
var camera_tween: Tween

# M3 is a joint meter-scale/contact diagnosis. It reuses the exact 1K CC0
# table from draft #56, keeps the original A lighting, and places the seated
# MPFB student, keyboard, chair and monitor at compatible heights. A's walls
# and desk footprint remain oversized; this is not a production-ready room.
func _ready() -> void:
	super._ready()
	var hidden_original_parts := 0
	for child in get_children():
		if child.name == "Desk top" or _is_original_desk_leg(child):
			child.hide()
			hidden_original_parts += 1
		if child.name.begins_with("Chair"):
			child.position += Vector3(0.0, -0.40, -0.55)
		if child.name.begins_with("Monitor") or child.name.begins_with("Screen") or child.name == "Keyboard" or child.name == "Blender desk lamp":
			child.position.y -= 0.40
	assert(hidden_original_parts == 5)
	get_node("Keyboard").position.z += 0.15
	var chair_stem := get_node("Chair stem") as MeshInstance3D
	var stem_mesh := chair_stem.mesh.duplicate() as CylinderMesh
	stem_mesh.height = 0.50
	chair_stem.mesh = stem_mesh
	chair_stem.position.y = 0.26
	var chair_back := get_node("Chair back") as MeshInstance3D
	var back_mesh := chair_back.mesh.duplicate() as BoxMesh
	back_mesh.size.y = 0.35
	chair_back.mesh = back_mesh
	chair_back.position.y = 0.62
	imported_typing.position += Vector3(0.0, -0.39, -0.55)
	var model: PackedScene = load("res://comparison/assets/polyhaven_wooden_table_02_1k.glb")
	assert(model != null)
	var desk := model.instantiate() as Node3D
	desk.name = "M3 CC0 wooden table"
	desk.position = Vector3(-0.65, 0.0, -1.55)
	desk.scale = Vector3(3.13, 1.0, 1.91)
	add_child(desk)
	print("M3_CONTACT heights=", [0.80, 0.44, 0.84, imported_typing.position.y],
		" desk_scale=", desk.scale)


func apply_state(value: String) -> void:
	super.apply_state(value)
	if not camera:
		return
	# Opt-in camera-only probe. The default M3 shot remains unchanged.
	var side_angle := "--m3-side-angle" in OS.get_cmdline_user_args()
	var goal_position := Vector3(7.5, 6.2, 9.0)
	if value == "in_progress":
		goal_position = Vector3(1.65, 1.9, 0.9) if side_angle else Vector3(2.1, 2.0, 2.3)
	var goal_target := Vector3(-0.78, 0.80, -0.53) if value == "in_progress" else Vector3(0, 1.25, 0)
	if not is_node_ready():
		camera.position = goal_position
		camera_target = goal_target
		camera.look_at(camera_target)
		return
	if camera_tween and camera_tween.is_running():
		camera_tween.kill()
	camera_tween = create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	camera_tween.set_parallel(true)
	camera_tween.tween_property(camera, "position", goal_position, 0.65)
	camera_tween.tween_property(self, "camera_target", goal_target, 0.65)
	print("M3_CAMERA_TWEEN ", value, " target=", goal_position)


func _process(delta: float) -> void:
	super._process(delta)
	if camera:
		camera.look_at(camera_target)


func _is_original_desk_leg(child: Node) -> bool:
	# Four generated legs share a source name, but Godot renames three of them.
	if not child is MeshInstance3D:
		return false
	var box := (child as MeshInstance3D).mesh as BoxMesh
	return box != null and box.size.distance_to(Vector3(0.18, 1.14, 0.18)) < 0.001 \
		and absf((child as MeshInstance3D).position.y - 0.57) < 0.001
