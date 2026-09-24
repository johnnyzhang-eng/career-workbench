extends "res://comparison/comparison.gd"

func _load_route() -> void:
	assert(route == "baseline")
	if room:
		scene_view.remove_child(room)
		room.queue_free()
	var use_hero := false
	for arg in OS.get_cmdline_user_args():
		if arg == "--hero-desk":
			use_hero = true
	room = load("res://comparison/hero_desk_room.gd" if use_hero else "res://comparison/room_3d.gd").new()
	room.refined = false
	scene_view.add_child(room)
	room.apply_phase(phase)
	room.task_kind = tasks[selected_index]["kind"]
	room.apply_state(tasks[selected_index]["state"])
	texture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	route_button.text = ROUTE_NAMES[route]
	get_window().title = "目标书桌 · " + ROUTE_NAMES[route]
	print("HERO_DESK_VARIANT ", "D1" if use_hero else "D0")
