extends "res://comparison/comparison.gd"

# Reuse the original A room wrapper and shared task UI without modifying them.
func _load_route() -> void:
	assert(route == "baseline")
	if room:
		scene_view.remove_child(room)
		room.queue_free()
	room = load("res://comparison/camera_fov_room.gd").new()
	room.refined = false
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--experiment-fov-degrees="):
			room.experiment_fov_degrees = float(arg.get_slice("=", 1))
	scene_view.add_child(room)
	room.apply_phase(phase)
	room.task_kind = tasks[selected_index]["kind"]
	room.apply_state(tasks[selected_index]["state"])
	texture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	route_button.text = ROUTE_NAMES[route]
	get_window().title = "目标书桌 · " + ROUTE_NAMES[route]
