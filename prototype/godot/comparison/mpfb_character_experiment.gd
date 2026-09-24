extends "res://comparison/character_experiment.gd"

var focus_layout := false


func _ready() -> void:
	focus_layout = "--activity-focus-layout" in OS.get_cmdline_user_args()
	super._ready()


func _layout() -> void:
	super._layout()
	if not focus_layout or not compact or collapsed:
		return
	# The #43 room-first layout is an art comparison only. It hides action
	# controls that the actual #50 companion keeps visible in its first screen.
	_rect(texture, 8, 46, logical_size.x - 16, 222)
	for i in range(list_buttons.size()):
		list_buttons[i].visible = i == selected_index
		if i == selected_index:
			_rect(list_buttons[i], 8, 274, logical_size.x - 16, 35)
	status.hide()
	start_button.hide()
	done_button.hide()
	defer_button.hide()
	footer.hide()
	scene_view.size = Vector2i(texture.size * display_scale)
	_position_hotspots()


func _proof() -> void:
	if not focus_layout:
		await super._proof()
		return
	tasks[0].state = "in_progress"
	_refresh("实验状态：本人明确开始任务")
	for i in range(36):
		await get_tree().process_frame
	await _capture("started")
	print("COMPARISON_PROOF_PASS ", route)


func _load_route() -> void:
	assert(route == "baseline")
	if room:
		scene_view.remove_child(room)
		room.queue_free()
	var args := OS.get_cmdline_user_args()
	var mpfb := "--mpfb-student" in args
	var rigged := "--rigged-student" in args
	var scale_contact_m3 := "--scale-contact-m3" in args
	assert(not scale_contact_m3 or mpfb)
	assert(not (mpfb and rigged))
	character_variant = mpfb or rigged
	var room_script := "res://comparison/room_3d.gd"
	if scale_contact_m3:
		room_script = "res://comparison/scale_contact_room.gd"
	elif mpfb:
		room_script = "res://comparison/mpfb_character_room.gd"
	elif rigged:
		room_script = "res://comparison/rigged_character_room.gd"
	room = load(room_script).new()
	room.refined = false
	scene_view.add_child(room)
	if "--contact-layout" in OS.get_cmdline_user_args():
		for node in room.get_children():
			if node.name.begins_with("Chair"):
				node.position.z -= 0.55
		var active_character := room.get("imported_typing") as Node3D
		if active_character:
			active_character.position.z -= 0.55
		room.get_node("Keyboard").position.z += 0.15
	if "--scaled-character" in OS.get_cmdline_user_args():
		var scaled := room.get("imported_typing") as Node3D
		assert(scaled != null)
		scaled.scale = Vector3.ONE * 1.35
		scaled.position.y -= 0.34
	if "--chair-low" in OS.get_cmdline_user_args():
		var chair_back := room.get_node("Chair back") as MeshInstance3D
		var back_mesh := chair_back.mesh.duplicate() as BoxMesh
		back_mesh.size.y = 0.38
		chair_back.mesh = back_mesh
		chair_back.position.y = 0.98
	if "--camera-side" in OS.get_cmdline_user_args():
		room.camera.position = Vector3(9.2, 6.2, 5.0)
		room.camera.look_at(Vector3(-0.1, 1.25, -0.4))
	if "--task-focus" in OS.get_cmdline_user_args():
		room.camera.position = Vector3(3.3, 3.0, 3.0)
		room.camera.look_at(Vector3(-0.76, 1.11, -0.45))
	if "--hero-focus" in OS.get_cmdline_user_args():
		room.camera.position = Vector3(2.1, 2.3, 2.3)
		room.camera.look_at(Vector3(-0.78, 1.12, -0.53))
	room.apply_phase(phase)
	room.task_kind = tasks[selected_index]["kind"]
	room.apply_state(tasks[selected_index]["state"])
	texture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	route_button.text = ROUTE_NAMES[route]
	get_window().title = "目标书桌 · " + ROUTE_NAMES[route]
	print("R4_VARIANT ", "R4" if mpfb else ("R2" if rigged else "R0"))
	print("R4_CAMERA ", "C7" if "--hero-focus" in OS.get_cmdline_user_args() else ("C3" if "--task-focus" in OS.get_cmdline_user_args() else ("C1" if "--camera-side" in OS.get_cmdline_user_args() else "C0")))
	print("R4_CHAIR ", "low" if "--chair-low" in OS.get_cmdline_user_args() else "original")
	print("R4_CONTACT ", "forward_055_keyboard_back_015" if "--contact-layout" in OS.get_cmdline_user_args() else "original")
	print("R4_SCALE ", "1.35x_and_down_034" if "--scaled-character" in OS.get_cmdline_user_args() else "original")
	print("R4_M3_SCALE_CONTACT ", scale_contact_m3)
