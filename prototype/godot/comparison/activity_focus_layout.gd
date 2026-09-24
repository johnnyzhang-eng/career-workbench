extends "res://comparison/comparison.gd"

# An isolated layout experiment: give the original A room more of the compact
# window. The full-size view, room geometry, camera, lights and task fixture
# remain in the shared comparison code.
var focus_layout := false


func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg == "--activity-focus-layout":
			focus_layout = true
	super._ready()


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
	for i in range(36):
		await get_tree().process_frame
	await _capture("started")
	observations.append({"check":"render_state_only", "route":route,
		"size":str(get_viewport_rect().size)})
