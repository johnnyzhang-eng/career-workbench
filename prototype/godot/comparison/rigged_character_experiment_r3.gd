extends "res://comparison/comparison.gd"

var r3_sequence := false
var r3_video := false


func _load_route() -> void:
	assert(route == "baseline")
	if room:
		scene_view.remove_child(room)
		room.queue_free()
	for arg in OS.get_cmdline_user_args():
		if arg == "--r3-sequence": r3_sequence = true
		if arg == "--r3-video": r3_video = true
	room = load("res://comparison/rigged_character_room_r3.gd").new()
	room.refined = false
	scene_view.add_child(room)
	room.apply_phase(phase)
	room.task_kind = tasks[selected_index]["kind"]
	room.apply_state(tasks[selected_index]["state"])
	texture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	route_button.text = ROUTE_NAMES[route]
	get_window().title = "目标书桌 · R3 骨骼试验"
	print("R3_VARIANT seat-and-action")


func _capture(label: String) -> void:
	if not r3_sequence or label != "idle":
		await super._capture(label)
		return
	assert(room.player != null and room.skeleton != null)
	DirAccess.make_dir_recursive_absolute(output_dir)
	_action("start") # Virtual task only; this never writes Career Workbench state.
	for entry in [
		["reach-start", "ReachToType", 0.0],
		["reach-mid", "ReachToType", 0.30],
		["reach-end", "ReachToType", 0.60],
		["typing-start", "TypingLoop", 0.0],
		["typing-left-down", "TypingLoop", 0.15],
		["typing-right-down", "TypingLoop", 0.45],
		["typing-mid", "TypingLoop", 0.75],
		["typing-end", "TypingLoop", 1.05],
		["typing-loop-end", "TypingLoop", 1.20],
	]:
		await _sample_animation(entry[0], entry[1], entry[2])
	if r3_video:
		await _capture_video_frames()


func _sample_animation(label: String, animation: String, seconds: float) -> void:
	room.player.play(animation)
	room.player.seek(seconds, true)
	room.player.advance(0)
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var path := "%s/%s-%dx%d-%s.png" % [output_dir, label, logical_size.x, logical_size.y, phase]
	assert(get_viewport().get_texture().get_image().save_png(path) == OK)
	var wrists := {}
	for side in ["Left", "Right"]:
		var bone_index: int = room.skeleton.find_bone(side + "Hand")
		assert(bone_index >= 0)
		var local: Vector3 = room.skeleton.get_bone_global_pose(bone_index).origin
		var world: Vector3 = room.skeleton.to_global(local)
		wrists[side] = [snappedf(world.x, 0.001), snappedf(world.y, 0.001), snappedf(world.z, 0.001)]
	print("R3_FRAME ", JSON.stringify({
		"label": label, "animation": animation, "seconds": seconds,
		"wrists_world": wrists, "window_pixels": [get_window().size.x, get_window().size.y],
		"viewport_pixels": [scene_view.size.x, scene_view.size.y],
		"path": path,
	}))


func _capture_video_frames() -> void:
	var frames_dir := output_dir + "/video_frames"
	DirAccess.make_dir_recursive_absolute(frames_dir)
	room.player.play("ReachToType")
	var elapsed := 0.0
	var frame := 0
	while elapsed < 3.0 and frame < 110:
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		var path := "%s/frame-%03d.png" % [frames_dir, frame]
		assert(get_viewport().get_texture().get_image().save_png(path) == OK)
		elapsed += get_process_delta_time()
		frame += 1
	print("R3_VIDEO_CAPTURE frames=", frame, " elapsed_seconds=", snappedf(elapsed, 0.001),
		" frame_dir=", frames_dir)
