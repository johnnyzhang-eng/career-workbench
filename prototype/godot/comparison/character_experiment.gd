extends "res://comparison/comparison.gd"

var character_variant := false


func _load_route() -> void:
	assert(route == "baseline")
	if room:
		scene_view.remove_child(room)
		room.queue_free()
	character_variant = "--adult-student" in OS.get_cmdline_user_args()
	room = load("res://comparison/character_room.gd" if character_variant else "res://comparison/room_3d.gd").new()
	room.refined = false
	scene_view.add_child(room)
	room.apply_phase(phase)
	room.task_kind = tasks[selected_index]["kind"]
	room.apply_state(tasks[selected_index]["state"])
	texture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	route_button.text = ROUTE_NAMES[route]
	get_window().title = "目标书桌 · " + ROUTE_NAMES[route]
	print("CHARACTER_VARIANT ", "R1" if character_variant else "R0")


func _capture(label: String) -> void:
	var target: Node3D = room.character
	if character_variant and label == "started":
		target = room.imported_typing
	var bounds := _projected_bounds(target)
	print("CHARACTER_BOUNDS ", JSON.stringify({
		"variant": "R1" if character_variant else "R0",
		"state": label,
		"viewport_pixels": [scene_view.size.x, scene_view.size.y],
		"display_scale": display_scale,
		"logical_xywh": bounds,
	}))
	await super._capture(label)


func _projected_bounds(target: Node3D) -> Array:
	var low := Vector2(INF, INF)
	var high := Vector2(-INF, -INF)
	var found := false
	for item in target.find_children("*", "MeshInstance3D", true, false):
		var mesh := item as MeshInstance3D
		var aabb := mesh.get_aabb()
		for x in [0.0, 1.0]:
			for y in [0.0, 1.0]:
				for z in [0.0, 1.0]:
					var corner := aabb.position + aabb.size * Vector3(x, y, z)
					var world := mesh.to_global(corner)
					if room.camera.is_position_behind(world):
						continue
					var pixel: Vector2 = room.camera.unproject_position(world)
					low = low.min(pixel)
					high = high.max(pixel)
					found = true
	assert(found)
	return [snappedf(low.x / display_scale, 0.01),
		snappedf(low.y / display_scale, 0.01),
		snappedf((high.x - low.x) / display_scale, 0.01),
		snappedf((high.y - low.y) / display_scale, 0.01)]
