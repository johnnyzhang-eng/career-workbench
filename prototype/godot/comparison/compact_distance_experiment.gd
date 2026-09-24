extends "res://comparison/comparison.gd"

# Only the compact A room changes camera distance along the original ray.
var experiment_distance_scale := 1.0

func _load_route() -> void:
	assert(route == "baseline")
	if room:
		scene_view.remove_child(room)
		room.queue_free()
	room = load("res://comparison/compact_distance_room.gd").new()
	room.refined = false
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--compact-distance-scale="):
			experiment_distance_scale = float(arg.get_slice("=", 1))
	assert(experiment_distance_scale > 0.65 and experiment_distance_scale <= 1.0)
	room.compact_distance_scale = experiment_distance_scale
	scene_view.add_child(room)
	room.apply_phase(phase)
	room.task_kind = tasks[selected_index]["kind"]
	room.apply_state(tasks[selected_index]["state"])
	texture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	route_button.text = ROUTE_NAMES[route]
	get_window().title = "目标书桌 · A 构图实验"

func _layout() -> void:
	super._layout()
	if room and room.is_node_ready():
		room.apply_compact_framing(compact)

func _metrics() -> void:
	var cam: Camera3D = room.camera
	var avatar: Node3D = room.character
	var foot: Vector2 = cam.unproject_position(avatar.global_position + Vector3(0, 0.03, 0))
	var head: Vector2 = cam.unproject_position(avatar.global_position + Vector3(0, 2.49, 0))
	var view_scale: Vector2 = texture.size / Vector2(scene_view.size)
	var corners := {}
	for key in ["floor_front_left", "floor_front_right", "floor_back_left", "floor_back_right"]:
		var x := -3.7 if key.ends_with("left") else 3.7
		var z := 3.1 if key.begins_with("floor_front") else -3.1
		var p: Vector2 = cam.unproject_position(Vector3(x, 0, z)) * view_scale
		corners[key] = [snappedf(p.x, 0.01), snappedf(p.y, 0.01)]
	var controls := {}
	for key in ["computer", "calendar"]:
		var button: Button = computer_button if key == "computer" else calendar_button
		var rect := button.get_global_rect()
		controls[key] = [rect.position.x, rect.position.y, rect.size.x, rect.size.y]
	var result := {
		"phase": phase,
		"logical_size": [logical_size.x, logical_size.y],
		"scene_rect": [texture.position.x, texture.position.y, texture.size.x, texture.size.y],
		"camera_position": [cam.position.x, cam.position.y, cam.position.z],
		"camera_target": [0, 1.25, 0],
		"fov_degrees": cam.fov,
		"distance_scale": experiment_distance_scale if compact else 1.0,
		"avatar_logic_px": snappedf(absf(foot.y - head.y) * view_scale.y, 0.01),
		"avatar_head_local": [snappedf(head.x * view_scale.x, 0.01), snappedf(head.y * view_scale.y, 0.01)],
		"avatar_foot_local": [snappedf(foot.x * view_scale.x, 0.01), snappedf(foot.y * view_scale.y, 0.01)],
		"room_floor_corners_local": corners,
		"hotspot_buttons": controls,
	}
	print("COMPACT_METRICS ", JSON.stringify(result))

func _proof() -> void:
	await _click(computer_button)
	assert(detail.visible)
	await _click(close_button)
	assert(not detail.visible)
	var previous: int = selected_index
	await _click(calendar_button)
	assert(selected_index == (previous + 1) % tasks.size())
	_select_task(0)
	observations.append({"check":"hotspot_clicks_pass","scene_size":[texture.size.x,texture.size.y]})
	await super._proof()

func _write_observations() -> void:
	_metrics()
	super._write_observations()
