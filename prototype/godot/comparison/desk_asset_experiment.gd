extends "res://comparison/comparison.gd"

func _load_route() -> void:
	assert(route == "baseline")
	if room:
		scene_view.remove_child(room)
		room.queue_free()
	var asset_variant := "--asset-desk" in OS.get_cmdline_user_args()
	room = load("res://comparison/desk_asset_room.gd" if asset_variant else "res://comparison/room_3d.gd").new()
	room.refined = false
	scene_view.add_child(room)
	room.apply_phase(phase)
	room.task_kind = tasks[selected_index]["kind"]
	room.apply_state(tasks[selected_index]["state"])
	texture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	route_button.text = ROUTE_NAMES[route]
	get_window().title = "目标书桌 · 原版与木桌实验"
	print("DESK_VARIANT", "M2" if asset_variant else "A")
