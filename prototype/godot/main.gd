extends Node3D

# Original, code-built room. The fixture is display data; these preview transitions
# intentionally do not write Career Workbench domain events.
const SNAPSHOT_PATH := "res://fixture/snapshot.json"
const INK := Color("253442")
const CREAM := Color("fff7e9")
const ACCENT := Color("e57958")
const SAGE := Color("83a8a0")

var task: Dictionary = {}
var snapshot_today := ""
var preview_state := "scheduled"
var selected := false
var evidence_note := ""
var evidence_url := ""
var camera_view := "room"
var character: Node3D
var hand: Node3D
var camera: Camera3D
var ui: Control
var title_label: Label
var clock_label: Label
var day_label: Label
var state_label: Label
var feedback_label: Label
var detail_panel: PanelContainer
var note_input: LineEdit
var url_input: LineEdit
var start_button: Button
var complete_button: Button
var defer_button: Button
var task_button: Button
var action_time := 0.0


func _ready() -> void:
	var snapshot: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(SNAPSHOT_PATH))
	assert(snapshot.get("schema_version") == 0)
	task = snapshot["tasks"][0]
	snapshot_today = snapshot["today"]
	preview_state = task["state"]
	_build_room()
	_build_ui()
	_show_state("Click the computer, calendar, or today's task.")
	get_viewport().size_changed.connect(_layout_ui)
	_layout_ui()


func _process(delta: float) -> void:
	action_time += delta
	if preview_state == "in_progress":
		character.position.y = 0.025 * sin(action_time * 4.0)
		hand.rotation.z = -0.20 + 0.12 * sin(action_time * 7.0)
	else:
		character.position.y = 0.0
		hand.rotation.z = 0.07 * sin(action_time * 2.0)
	if Engine.get_process_frames() % 20 == 0:
		var now := Time.get_datetime_dict_from_system()
		clock_label.text = "%04d.%02d.%02d  %02d:%02d" % [now.year, now.month, now.day, now.hour, now.minute]
		day_label.text = "TODAY  ·  01" if Time.get_date_string_from_system() == snapshot_today else "FIXTURE DAY  ·  " + snapshot_today


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_F12:
			_save_capture()
		elif event.keycode == KEY_1:
			_set_view("room")
		elif event.keycode == KEY_2:
			_set_view("side")
		elif event.keycode == KEY_3:
			_set_view("back")
		elif event.keycode == KEY_4:
			_set_view("lamp")
		elif event.keycode == KEY_ESCAPE:
			selected = false
			detail_panel.visible = false
			feedback_label.text = "Task detail closed."
		elif event.keycode == KEY_ENTER and not selected:
			_open_task("keyboard")
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var origin := camera.project_ray_origin(event.position)
		var end := origin + camera.project_ray_normal(event.position) * 30.0
		var query := PhysicsRayQueryParameters3D.create(origin, end)
		var hit := get_world_3d().direct_space_state.intersect_ray(query)
		if hit and hit.collider.has_meta("hotspot"):
			_open_task(str(hit.collider.get_meta("hotspot")))


func _set_view(view: String) -> void:
	camera_view = view
	match view:
		"room":
			camera.position = Vector3(7.5, 6.2, 9.0)
			camera.fov = 45.0
			camera.look_at(Vector3(0, 1.25, 0))
		"side":
			camera.position = Vector3(4.6, 3.2, 3.4)
			camera.fov = 50.0
			camera.look_at(Vector3(1.25, 1.2, 0.7))
		"back":
			camera.position = Vector3(1.25, 3.1, -2.8)
			camera.fov = 55.0
			camera.look_at(Vector3(1.25, 1.2, 0.7))
		"lamp":
			camera.position = Vector3(1.5, 2.5, 0.0)
			camera.fov = 45.0
			camera.look_at(Vector3(0.46, 1.7, -1.82))
	_show_state("View: %s. Press 1 for the room." % view)


func _save_capture() -> void:
	var size := get_viewport().get_visible_rect().size
	var filename := "scene-%dx%d-%s-%s.png" % [int(size.x), int(size.y), preview_state, camera_view]
	var output := ProjectSettings.globalize_path("res://../evidence/" + filename)
	var error := get_viewport().get_texture().get_image().save_png(output)
	if error == OK:
		print("CAPTURE_SAVED ", output)
	else:
		push_error("Capture failed: " + str(error))


func _material(color: Color, roughness := 1.0, emission := false) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = roughness
	if emission:
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = 0.5
	return material


func _box(parent: Node3D, name: String, pos: Vector3, size: Vector3, color: Color) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = size
	var node := MeshInstance3D.new()
	node.name = name
	node.mesh = mesh
	node.material_override = _material(color)
	node.position = pos
	parent.add_child(node)
	return node


func _sphere(parent: Node3D, name: String, pos: Vector3, radius: float, color: Color) -> MeshInstance3D:
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = radius * 2.0
	var node := MeshInstance3D.new()
	node.name = name
	node.mesh = mesh
	node.material_override = _material(color)
	node.position = pos
	parent.add_child(node)
	return node


func _cylinder(parent: Node3D, name: String, pos: Vector3, radius: float, height: float, color: Color) -> MeshInstance3D:
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	var node := MeshInstance3D.new()
	node.name = name
	node.mesh = mesh
	node.material_override = _material(color)
	node.position = pos
	parent.add_child(node)
	return node


func _hotspot(name: String, pos: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new()
	body.name = name
	body.position = pos
	body.set_meta("hotspot", name)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	body.add_child(shape)
	add_child(body)


func _build_room() -> void:
	var world := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("dbe8e4")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = CREAM
	env.ambient_light_energy = 0.30
	world.environment = env
	add_child(world)
	camera = Camera3D.new()
	camera.position = Vector3(7.5, 6.2, 9.0)
	add_child(camera)
	camera.look_at(Vector3(0, 1.25, 0))
	camera.fov = 45.0
	camera.current = true
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, -32, 0)
	sun.light_color = Color("fff0d9")
	sun.light_energy = 0.68
	sun.shadow_enabled = true
	add_child(sun)
	_box(self, "Warm floor", Vector3(0, -0.15, 0), Vector3(7.4, 0.28, 6.2), Color("d0a77a"))
	_box(self, "Back wall", Vector3(0, 2.0, -3.05), Vector3(7.4, 4.0, 0.18), Color("ead7c1"))
	_box(self, "Left wall", Vector3(-3.65, 2.0, 0), Vector3(0.18, 4.0, 6.2), Color("e7d7c2"))
	_box(self, "Skirting", Vector3(0, 0.13, -2.90), Vector3(7.3, 0.22, 0.12), Color("bd886d"))
	# A distinct desk silhouette, warm paper props and a generous empty floor.
	_box(self, "Desk top", Vector3(-0.65, 1.16, -1.55), Vector3(3.55, 0.17, 1.35), Color("a86d56"))
	for x in [-2.12, 0.82]:
		for z in [-2.04, -1.05]:
			_box(self, "Desk leg", Vector3(x, 0.57, z), Vector3(0.18, 1.14, 0.18), Color("805343"))
	_box(self, "Monitor stand", Vector3(-0.85, 1.40, -1.94), Vector3(0.12, 0.34, 0.11), INK)
	_box(self, "Monitor base", Vector3(-0.85, 1.24, -1.94), Vector3(0.62, 0.05, 0.3), INK)
	_box(self, "Monitor", Vector3(-0.85, 1.72, -1.94), Vector3(1.31, 0.89, 0.11), INK)
	_box(self, "Monitor display", Vector3(-0.85, 1.72, -1.873), Vector3(1.18, 0.75, 0.015), Color("7eb0ac"))
	_box(self, "Screen task card", Vector3(-0.85, 1.75, -1.86), Vector3(0.89, 0.48, 0.015), CREAM)
	_box(self, "Screen accent", Vector3(-1.16, 1.84, -1.84), Vector3(0.16, 0.07, 0.017), ACCENT)
	_box(self, "Keyboard", Vector3(-0.82, 1.28, -1.29), Vector3(0.95, 0.035, 0.28), Color("e9e2d6"))
	if ResourceLoader.exists("res://assets/desk_lamp.glb"):
		var lamp_scene: PackedScene = load("res://assets/desk_lamp.glb")
		var lamp := lamp_scene.instantiate() as Node3D
		lamp.name = "Blender desk lamp"
		lamp.position = Vector3(0.46, 1.25, -1.82)
		add_child(lamp)
	else:
		_cylinder(self, "Preview lamp base", Vector3(0.46, 1.29, -1.82), 0.23, 0.08, INK)
		_cylinder(self, "Preview lamp stem", Vector3(0.46, 1.52, -1.82), 0.035, 0.46, INK)
		_cylinder(self, "Preview lamp shade", Vector3(0.46, 1.90, -1.82), 0.20, 0.28, SAGE)
	_box(self, "Calendar", Vector3(1.1, 2.4, -2.92), Vector3(1.25, 1.35, 0.10), Color("fff9ed"))
	_box(self, "Calendar header", Vector3(1.1, 2.88, -2.85), Vector3(1.25, 0.27, 0.02), ACCENT)
	for row in range(3):
		for col in range(4):
			_box(self, "Calendar day", Vector3(0.70 + col * 0.26, 2.55 - row * 0.29, -2.84), Vector3(0.14, 0.08, 0.025), Color("ddbfa3") if row != 1 or col != 2 else SAGE)
	_box(self, "Window", Vector3(-2.65, 2.30, -2.90), Vector3(1.48, 1.55, 0.12), Color("96c5c5"))
	_box(self, "Window frame vertical", Vector3(-2.65, 2.30, -2.81), Vector3(0.08, 1.55, 0.10), CREAM)
	_box(self, "Window frame horizontal", Vector3(-2.65, 2.30, -2.81), Vector3(1.48, 0.08, 0.10), CREAM)
	_box(self, "Window sill", Vector3(-2.65, 1.49, -2.73), Vector3(1.78, 0.12, 0.35), CREAM)
	_box(self, "Bookshelf", Vector3(2.38, 1.47, -2.70), Vector3(0.75, 2.85, 0.45), Color("bd8662"))
	for y in [0.55, 1.30, 2.05]:
		_box(self, "Shelf", Vector3(2.38, y, -2.39), Vector3(0.79, 0.10, 0.6), Color("815945"))
	for i in range(4):
		_box(self, "Book", Vector3(2.12 + i * 0.16, 1.64, -2.31), Vector3(0.11, 0.55 + 0.07 * (i % 2), 0.24), [ACCENT, SAGE, CREAM, INK][i])
	_box(self, "Rug", Vector3(0.48, 0.015, 0.95), Vector3(3.5, 0.025, 2.45), Color("eecbb0"))
	_box(self, "Chair seat", Vector3(-0.88, 0.75, 0.10), Vector3(0.78, 0.18, 0.78), SAGE)
	_box(self, "Chair back", Vector3(-0.88, 1.22, 0.47), Vector3(0.78, 0.9, 0.14), SAGE)
	_cylinder(self, "Chair stem", Vector3(-0.88, 0.37, 0.10), 0.08, 0.70, INK)
	_build_character()
	_hotspot("computer", Vector3(-0.85, 1.7, -1.9), Vector3(1.5, 1.25, 0.5))
	_hotspot("calendar", Vector3(1.1, 2.4, -2.8), Vector3(1.45, 1.5, 0.48))


func _build_character() -> void:
	character = Node3D.new()
	character.name = "Original student mascot"
	character.position = Vector3(1.25, 0.0, 0.7)
	add_child(character)
	_cylinder(character, "Left shoe", Vector3(-0.22, 0.12, 0.12), 0.19, 0.22, INK)
	_cylinder(character, "Right shoe", Vector3(0.22, 0.12, 0.12), 0.19, 0.22, INK)
	_cylinder(character, "Left leg", Vector3(-0.20, 0.42, 0), 0.13, 0.52, Color("677d87"))
	_cylinder(character, "Right leg", Vector3(0.20, 0.42, 0), 0.13, 0.52, Color("677d87"))
	_sphere(character, "Oversized hoodie", Vector3(0, 1.03, 0), 0.52, ACCENT)
	_sphere(character, "Head", Vector3(0, 1.82, 0.01), 0.46, Color("eac39f"))
	_sphere(character, "Hair cap", Vector3(0, 2.10, -0.03), 0.39, Color("4d4242"))
	for x in [-0.17, 0.17]:
		_sphere(character, "Eye", Vector3(x, 1.86, 0.43), 0.045, INK)
	_sphere(character, "Nose", Vector3(0, 1.72, 0.46), 0.035, Color("bf8069"))
	_cylinder(character, "Left arm", Vector3(-0.49, 1.15, 0.05), 0.15, 0.62, ACCENT)
	hand = Node3D.new()
	hand.name = "Animated right arm"
	hand.position = Vector3(0.46, 1.36, 0)
	character.add_child(hand)
	_cylinder(hand, "Sleeve", Vector3(0.03, -0.25, 0), 0.15, 0.58, ACCENT)
	_sphere(hand, "Hand", Vector3(0.03, -0.57, 0), 0.13, Color("eac39f"))
	_box(character, "Backpack", Vector3(0, 1.05, -0.43), Vector3(0.64, 0.68, 0.27), SAGE)
	_box(character, "Backpack pocket", Vector3(0, 0.98, -0.58), Vector3(0.40, 0.26, 0.04), CREAM)


func _label(text_value: String, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text_value
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _button(text_value: String, color: Color) -> Button:
	var button := Button.new()
	button.text = text_value
	button.custom_minimum_size = Vector2(0, 39)
	button.add_theme_font_size_override("font_size", 15)
	button.add_theme_color_override("font_color", INK)
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	style.content_margin_left = 12
	style.content_margin_right = 12
	button.add_theme_stylebox_override("normal", style)
	return button


func _build_ui() -> void:
	ui = Control.new()
	ui.name = "Today HUD"
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(ui)
	var top := PanelContainer.new()
	top.name = "Top strip"
	var top_style := StyleBoxFlat.new()
	top_style.bg_color = Color("253442ec")
	top_style.content_margin_left = 18
	top_style.content_margin_right = 18
	top_style.content_margin_top = 11
	top_style.content_margin_bottom = 11
	top.add_theme_stylebox_override("panel", top_style)
	ui.add_child(top)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	top.add_child(row)
	title_label = _label("AUTUMN DESK  /  Fictional preview", 20, CREAM)
	title_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(title_label)
	clock_label = _label("", 18, Color("cce5db"))
	row.add_child(clock_label)

	var side := PanelContainer.new()
	side.name = "Checklist"
	var side_style := StyleBoxFlat.new()
	side_style.bg_color = Color("fff7e9f2")
	side_style.corner_radius_top_left = 16
	side_style.corner_radius_top_right = 16
	side_style.corner_radius_bottom_left = 16
	side_style.corner_radius_bottom_right = 16
	side_style.content_margin_left = 20
	side_style.content_margin_right = 20
	side_style.content_margin_top = 18
	side_style.content_margin_bottom = 18
	side.add_theme_stylebox_override("panel", side_style)
	ui.add_child(side)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 11)
	side.add_child(column)
	day_label = _label("TODAY  ·  01", 17, ACCENT)
	column.add_child(day_label)
	column.add_child(_label("One task at a time", 23, INK))
	column.add_child(_label("A small room for a real daily rhythm.", 14, Color("677782")))
	var separator := HSeparator.new()
	column.add_child(separator)
	task_button = _button("□  " + str(task["title"]), Color("e3ebe6"))
	task_button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	task_button.pressed.connect(func(): _open_task("checklist"))
	column.add_child(task_button)
	state_label = _label("SCHEDULED · eligibility unknown", 14, Color("6a7b7f"))
	column.add_child(state_label)
	column.add_child(_label("Source: fictional " + str(task["source_id"]) + "\nDeadline: unknown (not verified)", 13, Color("667780")))
	column.add_child(_label("Try clicking the computer or calendar.\nEnter opens task · Esc closes it.", 13, Color("7e8d8b")))
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(spacer)
	column.add_child(_label("SCENE PREVIEW · no real application", 12, ACCENT))

	detail_panel = PanelContainer.new()
	detail_panel.name = "Task detail"
	detail_panel.visible = false
	var detail_style := StyleBoxFlat.new()
	detail_style.bg_color = Color("fffaf1")
	detail_style.corner_radius_top_left = 14
	detail_style.corner_radius_top_right = 14
	detail_style.corner_radius_bottom_left = 14
	detail_style.corner_radius_bottom_right = 14
	detail_style.border_color = Color("c3b4a3")
	detail_style.set_border_width_all(2)
	detail_style.set_content_margin_all(20)
	detail_panel.add_theme_stylebox_override("panel", detail_style)
	ui.add_child(detail_panel)
	var detail := VBoxContainer.new()
	detail.add_theme_constant_override("separation", 7)
	detail_panel.add_child(detail)
	detail.add_child(_label("TASK  /  " + str(task["id"]), 14, ACCENT))
	detail.add_child(_label(str(task["title"]), 20, INK))
	detail.add_child(_label(str(task["reason"]), 13, Color("526575")))
	detail.add_child(_label("Done when: " + str(task["completion_rule"]), 13, INK))
	detail.add_child(_label("Fictional source · eligibility unknown · no verified deadline", 12, ACCENT))
	note_input = LineEdit.new()
	note_input.placeholder_text = "Verification conclusion (demo text)"
	_style_input(note_input)
	detail.add_child(note_input)
	url_input = LineEdit.new()
	url_input.placeholder_text = "Source URL (https://example.invalid/...)"
	_style_input(url_input)
	detail.add_child(url_input)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 7)
	detail.add_child(actions)
	start_button = _button("Start", Color("b6d2ca"))
	start_button.pressed.connect(_start_task)
	actions.add_child(start_button)
	complete_button = _button("Complete", Color("f3c6a4"))
	complete_button.pressed.connect(_complete_task)
	actions.add_child(complete_button)
	defer_button = _button("Defer", Color("e8d9b8"))
	defer_button.pressed.connect(_defer_task)
	actions.add_child(defer_button)
	var close := _button("Close", Color("eceae4"))
	close.pressed.connect(func(): detail_panel.visible = false; selected = false)
	detail.add_child(close)

	var feedback_panel := PanelContainer.new()
	feedback_panel.name = "Feedback"
	var fb_style := StyleBoxFlat.new()
	fb_style.bg_color = Color("253442e8")
	fb_style.corner_radius_top_left = 10
	fb_style.corner_radius_top_right = 10
	fb_style.corner_radius_bottom_left = 10
	fb_style.corner_radius_bottom_right = 10
	fb_style.set_content_margin_all(12)
	feedback_panel.add_theme_stylebox_override("panel", fb_style)
	ui.add_child(feedback_panel)
	feedback_label = _label("", 14, CREAM)
	feedback_panel.add_child(feedback_label)


func _style_input(input: LineEdit) -> void:
	var style := StyleBoxFlat.new()
	style.bg_color = Color("f0eee5")
	style.corner_radius_top_left = 6
	style.corner_radius_top_right = 6
	style.corner_radius_bottom_left = 6
	style.corner_radius_bottom_right = 6
	style.set_content_margin_all(7)
	input.add_theme_stylebox_override("normal", style)
	input.add_theme_color_override("font_color", INK)
	input.add_theme_color_override("font_placeholder_color", Color("758283"))
	input.custom_minimum_size.y = 36


func _layout_ui() -> void:
	var size := get_viewport().get_visible_rect().size
	var top: Control = ui.get_node("Top strip")
	top.position = Vector2(16, 16)
	top.size = Vector2(size.x - 32, 52)
	var side: Control = ui.get_node("Checklist")
	var width := minf(350.0, size.x * 0.43)
	side.position = Vector2(size.x - width - 16, 82)
	side.size = Vector2(width, size.y - 162)
	detail_panel.position = Vector2(16, maxf(82.0, size.y - 430.0))
	detail_panel.size = Vector2(minf(420.0, size.x - width - 48.0), minf(356.0, size.y - 165.0))
	var feedback: Control = ui.get_node("Feedback")
	feedback.position = Vector2(16, size.y - 66)
	feedback.size = Vector2(size.x - 32, 48)


func _open_task(from: String) -> void:
	selected = true
	detail_panel.visible = true
	_show_state("Opened task from %s. This is a fictional scene preview." % from)


func _start_task() -> void:
	if preview_state == "completed":
		_show_state("Already completed in this preview.")
		return
	preview_state = "in_progress"
	action_time = 0.0
	_show_state("Started: the student is checking the computer.")


func _complete_task() -> void:
	evidence_note = note_input.text.strip_edges()
	evidence_url = url_input.text.strip_edges()
	if preview_state != "in_progress":
		_show_state("Start the task first.")
		return
	if evidence_note.is_empty() or not evidence_url.begins_with("https://"):
		_show_state("Add a conclusion and HTTPS source URL before completing.")
		return
	preview_state = "completed"
	_show_state("Demo task completed with a conclusion and source. No application submitted.")


func _defer_task() -> void:
	if preview_state == "completed":
		_show_state("Completed preview task cannot be deferred.")
		return
	preview_state = "deferred"
	_show_state("Deferred in this preview. No fictional deadline was invented.")


func _show_state(message: String) -> void:
	feedback_label.text = message
	match preview_state:
		"scheduled":
			state_label.text = "SCHEDULED · eligibility unknown"
			task_button.text = "□  " + str(task["title"])
		"in_progress":
			state_label.text = "IN PROGRESS · checking source"
			task_button.text = "◉  " + str(task["title"])
		"completed":
			state_label.text = "COMPLETED · preview evidence entered"
			task_button.text = "✓  " + str(task["title"])
		"deferred":
			state_label.text = "DEFERRED · no due date assumed"
			task_button.text = "↗  " + str(task["title"])
