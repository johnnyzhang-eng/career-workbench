extends "res://comparison/comparison.gd"

# Reuse the original task UI and screenshot harness without editing A or B.
func _load_route() -> void:
	assert(route == "baseline")
	if room:
		scene_view.remove_child(room)
		room.queue_free()
	room = load("res://comparison/ambient_room.gd").new()
	room.refined = false
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--ambient-multiplier="):
			room.ambient_multiplier = float(arg.get_slice("=", 1))
	scene_view.add_child(room)
	room.apply_phase(phase)
	room.task_kind = tasks[selected_index]["kind"]
	room.apply_state(tasks[selected_index]["state"])
	texture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	route_button.text = ROUTE_NAMES[route]
	get_window().title = "目标书桌 · " + ROUTE_NAMES[route]
