extends "res://comparison/comparison.gd"

# An isolated layout experiment: give the original A room more of the compact
# window. The full-size view, room geometry, camera, lights and task fixture
# remain in the shared comparison code.
var focus_layout := false
var rigged_variant := false
var fixed_clock := false


func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg == "--activity-focus-layout":
			focus_layout = true
		if arg == "--rigged-character":
			rigged_variant = true
		if arg == "--fixed-clock":
			fixed_clock = true
	super._ready()


func _process(delta: float) -> void:
	super._process(delta)
	if fixed_clock and clock_text != null:
		clock_text.text = "12:00 · 对照时钟"


func _load_route() -> void:
	if not rigged_variant:
		super._load_route()
		return
	assert(route == "baseline")
	if room:
		scene_view.remove_child(room)
		room.queue_free()
	room = load("res://comparison/rigged_character_room.gd").new()
	room.refined = false
	scene_view.add_child(room)
	room.apply_phase(phase)
	room.task_kind = tasks[selected_index]["kind"]
	room.apply_state(tasks[selected_index]["state"])
	texture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	route_button.text = ROUTE_NAMES[route]
	get_window().title = "目标书桌 · R2 布局试验"


func _layout() -> void:
	super._layout()
	if not focus_layout or not compact or collapsed:
		return
	# In this preview mode, the compact panel shows room + one task chip;
	# controls for starting and recording results live in the expanded view.
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
	# Capture the same selected task in an explicit started state. This does
	# not test the hidden compact controls; it isolates render readability.
	tasks[0].state = "in_progress"
	_refresh("实验状态：本人明确开始任务")
	if rigged_variant and film_requested:
		# Observe the actual SitToType -> TypingLoop sequence in the enlarged
		# compact room. The video is evidence, not task completion.
		for i in range(60):
			await _capture("focus-motion-%03d" % i)
			await get_tree().create_timer(1.0 / 24.0).timeout
		await _capture("started")
		observations.append({"check":"rigged_motion_capture", "frames":60,
			"route":route, "size":str(get_viewport_rect().size)})
		return
	if rigged_variant:
		# Freeze the same right-hand-down keyframe in L0 and L1. This is a
		# layout comparison, not a proof of animation continuity.
		room.player.play("TypingLoop")
		room.player.seek(0.45, true)
		room.player.speed_scale = 0.0
	for i in range(36):
		await get_tree().process_frame
	await _capture("started")
	observations.append({"check":"render_state_only", "route":route,
		"size":str(get_viewport_rect().size)})
