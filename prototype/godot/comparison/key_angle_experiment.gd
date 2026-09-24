extends "res://comparison/comparison.gd"

# Keep the baseline A UI, camera, geometry, and phase handling intact.
func _load_route() -> void:
	assert(route == "baseline")
	if room:
		scene_view.remove_child(room)
		room.queue_free()
	room = load("res://comparison/key_angle_room.gd").new()
	room.refined = false
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--key-pitch-degrees="):
			room.key_pitch_degrees = float(arg.get_slice("=", 1))
	scene_view.add_child(room)
	room.apply_phase(phase)
	room.task_kind = tasks[selected_index]["kind"]
	room.apply_state(tasks[selected_index]["state"])
	texture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	route_button.text = ROUTE_NAMES[route]
	get_window().title = "目标书桌 · " + ROUTE_NAMES[route]
