extends Control

# Renderer comparison only. No backend, inference, application or exam claim.
const ROUTES := ["baseline", "3d", "2d", "pixel"]
const ROUTE_NAMES := {"baseline":"A · 原 3D", "3d":"B · 改良 3D", "2d":"C · 等距 2D", "pixel":"D · 像素化 2D"}
const CREAM := Color("f6efdf")
const INK := Color("344742")
var route := "3d"
var phase := "day"
var tasks: Array = []
var selected_index := 0
var room: Node
var scene_view: SubViewport
var texture: TextureRect
var back: ColorRect
var header: Label
var clock_text: Label
var route_button: Button
var phase_button: Button
var size_button: Button
var collapse_button: Button
var pin_button: Button
var glass_button: Button
var house_button: Button
var collapsed := false
var desktop_background_test := false
var glass := false
var restore_size := Vector2i(360,320)
var footer: Label
var side_title: Label
var list_buttons: Array[Button] = []
var status: Label
var start_button: Button
var done_button: Button
var defer_button: Button
var computer_button: Button
var calendar_button: Button
var detail: Panel
var detail_title: Label
var note: LineEdit
var detail_hint: Label
var confirm_button: Button
var close_button: Button
var output_dir := ""
var capture_requested := false
var proof_requested := false
var quit_requested := false
var film_requested := false
var desktop_requested := false
var film_index := 0
var telemetry := false
var telemetry_clock := 0.0
var compact := false
var logical_size := Vector2i(360,320)
var display_scale := 1.0
var frame_clock := 0.0
var started_usec := Time.get_ticks_usec()
var frames: Array[float] = []
var observations: Array = []

func _ready() -> void:
	Engine.max_fps = 30
	get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	display_scale = DisplayServer.screen_get_scale()
	var target_size := Vector2i(360, 320)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--route="): route = arg.get_slice("=", 1)
		elif arg.begins_with("--phase="): phase = arg.get_slice("=", 1)
		elif arg.begins_with("--size="):
			var values := arg.get_slice("=",1).split("x")
			target_size = Vector2i(int(values[0]), int(values[1]))
		elif arg.begins_with("--out="): output_dir = arg.trim_prefix("--out=")
		elif arg == "--capture": capture_requested = true
		elif arg == "--proof": proof_requested = true
		elif arg == "--quit": quit_requested = true
		elif arg == "--film": film_requested = true
		elif arg == "--telemetry": telemetry = true
		elif arg == "--desktop-proof": desktop_requested = true
		elif arg == "--desktop-background-test": desktop_background_test = true
	assert(route in ROUTES)
	get_window().min_size = Vector2i(80,80)
	_set_logical_size(target_size)
	get_window().always_on_top = target_size.x <= 420
	get_window().title = "目标书桌 · " + ROUTE_NAMES[route]
	if target_size.x <= 420:
		var screen := DisplayServer.screen_get_usable_rect()
		DisplayServer.window_set_position(Vector2i(screen.end.x - int(target_size.x*display_scale) - 36, screen.position.y + 56))
	if desktop_background_test: DisplayServer.window_set_position(Vector2i(700,300))
	tasks = JSON.parse_string(FileAccess.get_file_as_string("res://comparison/tasks.json"))["tasks"]
	_build_ui()
	_load_route()
	get_viewport().size_changed.connect(_layout)
	_layout()
	_refresh("虚构样例 · 任务结果不会写入真实记录")
	await get_tree().process_frame
	await get_tree().process_frame
	_layout()
	room.apply_phase(phase)
	if capture_requested or proof_requested or desktop_requested:
		for i in range(12): await get_tree().process_frame
		await _capture("idle")
		if proof_requested: await _proof()
		if desktop_requested: await _desktop_proof()
		_write_observations()
		if quit_requested: get_tree().quit()

func _label(value: String, size_value: int) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_size_override("font_size",size_value)
	label.add_theme_color_override("font_color",INK)
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(label)
	return label

func _button(value: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = value
	button.add_theme_font_size_override("font_size",15)
	button.add_theme_color_override("font_color",INK)
	button.add_theme_color_override("font_hover_color",INK)
	var style := StyleBoxFlat.new()
	style.bg_color = Color("e4e9dd")
	style.set_corner_radius_all(8)
	style.set_content_margin_all(8)
	button.add_theme_stylebox_override("normal",style)
	var hover := style.duplicate()
	hover.bg_color = Color("cadaca")
	button.add_theme_stylebox_override("hover",hover)
	button.add_theme_stylebox_override("pressed",hover)
	button.pressed.connect(callback)
	add_child(button)
	return button

func _build_ui() -> void:
	back = ColorRect.new()
	back.color = CREAM
	back.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(back)
	scene_view = SubViewport.new()
	scene_view.own_world_3d = true
	scene_view.msaa_3d = Viewport.MSAA_4X
	scene_view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(scene_view)
	texture = TextureRect.new()
	texture.texture = scene_view.get_texture()
	texture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	texture.stretch_mode = TextureRect.STRETCH_SCALE
	texture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(texture)
	header = _label("今天，留下一点进展",26)
	clock_text = _label("",15)
	route_button = _button(ROUTE_NAMES[route],_cycle_route)
	phase_button = _button("夜晚" if phase == "evening" else "白天",_toggle_phase)
	size_button = _button("小窗",_toggle_size)
	collapse_button = _button("收起",_toggle_collapse)
	pin_button = _button("置顶",_toggle_pin)
	glass_button = _button("半透",_toggle_glass)
	house_button = _button("⌂\n打开",_toggle_collapse)
	house_button.add_theme_font_size_override("font_size",16)
	house_button.hide()
	footer = _label("",14)
	side_title = _label("今日行动 · 3 项",22)
	for i in range(tasks.size()):
		var index := i
		var button := _button("",func(): _select_task(index))
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		list_buttons.append(button)
	status = _label("",14)
	start_button = _button("开始",func(): _action("start"))
	done_button = _button("记录结果",_open_detail)
	defer_button = _button("延期",func(): _action("defer"))
	computer_button = _button("电脑",func(): _open_detail())
	calendar_button = _button("日历",func(): _select_task((selected_index + 1) % tasks.size()))
	detail = Panel.new()
	var paper := StyleBoxFlat.new()
	paper.bg_color = Color("fff9ec")
	paper.set_corner_radius_all(12)
	paper.set_border_width_all(2)
	paper.border_color = Color("7c9688")
	detail.add_theme_stylebox_override("panel",paper)
	add_child(detail)
	detail_title = Label.new()
	detail_title.add_theme_font_size_override("font_size",19)
	detail_title.add_theme_color_override("font_color",INK)
	detail.add_child(detail_title)
	detail_hint = Label.new()
	detail_hint.add_theme_font_size_override("font_size",13)
	detail_hint.add_theme_color_override("font_color",INK)
	detail_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	detail.add_child(detail_hint)
	note = LineEdit.new()
	note.placeholder_text = "输入一条虚构结果"
	note.add_theme_font_size_override("font_size",16)
	detail.add_child(note)
	confirm_button = _button("保存演示结果",func(): _action("complete"))
	confirm_button.reparent(detail)
	close_button = _button("收起",func(): detail.hide())
	close_button.reparent(detail)
	detail.hide()

func _load_route() -> void:
	if room:
		scene_view.remove_child(room)
		room.queue_free()
	if route in ["baseline", "3d"]:
		room = load("res://comparison/room_3d.gd").new()
		room.refined = route == "3d"
	else:
		room = load("res://comparison/room_2d.gd").new()
	scene_view.add_child(room)
	room.apply_phase(phase)
	room.task_kind = tasks[selected_index]["kind"]
	room.apply_state(tasks[selected_index]["state"])
	texture.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST if route == "pixel" else CanvasItem.TEXTURE_FILTER_LINEAR
	route_button.text = ROUTE_NAMES[route]
	get_window().title = "目标书桌 · " + ROUTE_NAMES[route]

func _process(delta: float) -> void:
	frame_clock += delta
	frames.append(delta)
	if frames.size() > 1800: frames.pop_front()
	if telemetry:
		telemetry_clock += delta
		if telemetry_clock >= 1.0:
			telemetry_clock = 0.0
			var sorted := frames.duplicate()
			sorted.sort()
			var total := 0.0
			for value in frames: total += value
			var file := FileAccess.open(output_dir + "/" + route + "-idle-frames.json",FileAccess.WRITE)
			file.store_string(JSON.stringify({"frame_samples":frames.size(),"mean_frame_ms":total / frames.size() * 1000,"p95_frame_ms":sorted[int(sorted.size()*0.95)]*1000,"fps":Engine.get_frames_per_second(),"elapsed_ms":(Time.get_ticks_usec()-started_usec)/1000.0},"  "))
	if frame_clock >= 0.25:
		frame_clock = 0
		var now := Time.get_datetime_dict_from_system()
		clock_text.text = "%02d:%02d · 系统时间" % [now.hour,now.minute]
		_position_hotspots()

func _rect(control: Control, x: float, y: float, w: float, h: float) -> void:
	control.position = Vector2(x,y)
	control.size = Vector2(w,h)

func _layout() -> void:
	var s := Vector2(logical_size)
	if collapsed:
		_rect(house_button,8,8,64,64)
		return
	compact = s.x <= 420
	get_window().borderless = compact
	pin_button.text = "置顶 ✓" if get_window().always_on_top else "普通窗"
	_rect(back,0,0,s.x,s.y)
	if compact:
		header.hide()
		clock_text.hide()
		side_title.hide()
		_rect(route_button,8,8,124,32)
		_rect(phase_button,138,8,50,32)
		_rect(size_button,194,8,70,32)
		_rect(collapse_button,270,8,s.x-278,32)
		pin_button.hide()
		glass_button.hide()
		size_button.text = "展开"
		_rect(texture,8,46,s.x-16,141)
		for i in range(3):
			list_buttons[i].visible = i == selected_index
			_rect(list_buttons[i],8,193,s.x-16,34)
		_rect(status,10,229,s.x-20,22)
		_rect(start_button,8,257,76,34)
		_rect(done_button,90,257,142,34)
		_rect(defer_button,238,257,s.x-246,34)
		_rect(footer,10,294,s.x-20,20)
		footer.add_theme_font_size_override("font_size",11)
	else:
		header.show()
		clock_text.show()
		side_title.show()
		size_button.text = "小窗"
		pin_button.show()
		glass_button.show()
		_rect(pin_button,s.x-380,64,104,30)
		_rect(glass_button,s.x-268,64,104,30)
		_rect(collapse_button,s.x-156,64,134,30)
		var side := 310.0 if s.x >= 1000 else 290.0
		_rect(header,22,18,maxf(280,s.x-600),40)
		_rect(clock_text,22,59,250,24)
		_rect(route_button,s.x-380,22,150,36)
		_rect(phase_button,s.x-222,22,116,36)
		_rect(size_button,s.x-98,22,76,36)
		_rect(texture,16,94,s.x-side-48,s.y-170)
		_rect(side_title,s.x-side-16,101,side,38)
		for i in range(3):
			list_buttons[i].show()
			_rect(list_buttons[i],s.x-side-16,154+i*70,side,58)
		_rect(status,s.x-side-16,376,side,50)
		_rect(start_button,s.x-side-16,443,82,40)
		_rect(done_button,s.x-side+74,443,126,40)
		_rect(defer_button,s.x-118,492,102,38)
		_rect(footer,22,s.y-51,s.x-44,34)
		footer.add_theme_font_size_override("font_size",14)
	var render_size := Vector2i(texture.size * display_scale)
	if route == "pixel": render_size = Vector2i(maxi(1,int(texture.size.x/3)), maxi(1,int(texture.size.y/3)))
	scene_view.size = render_size
	var dw := minf(430,s.x-24)
	_rect(detail,(s.x-dw)/2,maxf(46,(s.y-230)/2),dw,230)
	_rect(detail_title,16,14,dw-32,32)
	_rect(detail_hint,16,52,dw-32,64)
	_rect(note,16,120,dw-32,36)
	_rect(confirm_button,16,171,dw-115,38)
	_rect(close_button,dw-91,171,75,38)
	_position_hotspots()

func _position_hotspots() -> void:
	if not room or not room.is_node_ready(): return
	var points: Dictionary = room.hotspot_points()
	for key in ["computer","calendar"]:
		var button := computer_button if key == "computer" else calendar_button
		if not points.has(key): continue
		var point: Vector2 = points[key] / Vector2(scene_view.size) * texture.size + texture.position
		var width := 54.0 if compact else 64.0
		var height := 32.0 if compact else 30.0
		button.add_theme_font_size_override("font_size",11 if compact else 13)
		if compact:
			_rect(button,texture.position.x + (8 if key == "computer" else texture.size.x-width-8),texture.position.y+texture.size.y-height-5,width,height)
			continue
		_rect(button,clampf(point.x-width/2,texture.position.x,texture.position.x+texture.size.x-width),clampf(point.y-height,texture.position.y,texture.position.y+texture.size.y-height),width,height)

func _refresh(message: String) -> void:
	var state_names := {"scheduled":"待开始", "in_progress":"进行中", "completed":"已记录结果", "deferred":"已延期"}
	var icons := {"scheduled":"○", "in_progress":"●", "completed":"✓", "deferred":"↗"}
	for i in range(tasks.size()):
		var t: Dictionary = tasks[i]
		list_buttons[i].text = icons[t.state] + "  " + t.title
		list_buttons[i].tooltip_text = t.completion_rule
		var row_style := list_buttons[i].get_theme_stylebox("normal").duplicate() as StyleBoxFlat
		row_style.set_border_width_all(2 if i == selected_index else 0)
		row_style.border_color = Color("799182")
		list_buttons[i].add_theme_stylebox_override("normal",row_style)
	var task: Dictionary = tasks[selected_index]
	status.text = state_names[task.state] + "  ·  截止未知"
	start_button.disabled = task.state in ["completed", "in_progress"]
	defer_button.disabled = task.state == "completed"
	done_button.disabled = task.state == "completed"
	footer.text = message
	detail_title.text = task.title
	detail_hint.text = "虚构演示 · " + task.completion_rule + "\n先开始，输入结果，再保存。"
	room.task_kind = task.kind
	room.apply_state(task.state)

func _select_task(index: int) -> void:
	selected_index = index
	note.text = ""
	_refresh("虚构任务 · 选择今天要投入的事")
	_layout()

func _open_detail() -> void:
	detail.show()
	note.grab_focus()

func _action(command: String) -> void:
	var task: Dictionary = tasks[selected_index]
	if command == "start" and task.state != "completed":
		task.state = "in_progress"
		_refresh("开始了 · 角色正在投入当前任务")
	elif command == "defer" and task.state != "completed":
		task.state = "deferred"
		_refresh("已延期 · 演示未自动编造新的截止时间")
	elif command == "complete":
		if task.state != "in_progress" or note.text.strip_edges().is_empty():
			detail_hint.text = "先开始任务并填写虚构结果，才可保存。\n这不是投递成功或掌握能力的证明。"
			observations.append({"action":"blocked_completion","state":task.state})
			return
		task.state = "completed"
		detail.hide()
		_refresh("结果已记录 · 虚构演示，未证明投递或掌握")
	observations.append({"action":command,"task":task.id,"state":task.state})

func _cycle_route() -> void:
	route = ROUTES[(ROUTES.find(route)+1)%ROUTES.size()]
	_load_route()
	_layout()
	_refresh("相同任务和界面 · 切换画面方向")

func _toggle_phase() -> void:
	phase = "evening" if phase == "day" else "day"
	phase_button.text = "夜晚" if phase == "evening" else "白天"
	room.apply_phase(phase)
	footer.text = "光照为对照设置 · 时钟仍读取系统时间"

func _set_logical_size(value: Vector2i) -> void:
	logical_size = value
	get_window().content_scale_size = value
	DisplayServer.window_set_size(Vector2i(Vector2(value)*display_scale))
	print("DISPLAY logical=",value," pixels=",get_window().size," scale=",display_scale)

func _toggle_size() -> void:
	var to_small := not compact
	_set_logical_size(Vector2i(360,320) if to_small else Vector2i(1280,720))
	get_window().always_on_top = to_small
	if to_small:
		var screen := DisplayServer.screen_get_usable_rect()
		DisplayServer.window_set_position(Vector2i(screen.end.x-int(378*display_scale),screen.position.y+56))
	else:
		var screen := DisplayServer.screen_get_usable_rect()
		DisplayServer.window_set_position(screen.position + (screen.size-Vector2i(Vector2(1280,720)*display_scale))/2)
	_layout.call_deferred()

func _toggle_pin() -> void:
	get_window().always_on_top = not get_window().always_on_top
	_layout()

func _toggle_glass() -> void:
	glass = not glass
	get_window().transparent = glass
	get_window().transparent_bg = glass
	back.color = Color(CREAM,0.78 if glass else 1.0)
	glass_button.text = "实色" if glass else "半透"

func _toggle_collapse() -> void:
	collapsed = not collapsed
	if collapsed:
		restore_size = logical_size
		detail.hide()
		for child in get_children():
			if child is Control: child.hide()
		house_button.show()
		get_window().borderless = true
		get_window().transparent = true
		get_window().transparent_bg = true
		get_window().always_on_top = true
		get_window().mouse_passthrough_polygon = PackedVector2Array([Vector2(8,8)*display_scale,Vector2(72,8)*display_scale,Vector2(72,72)*display_scale,Vector2(8,72)*display_scale])
		_set_logical_size(Vector2i(80,80))
		scene_view.render_target_update_mode = SubViewport.UPDATE_DISABLED
		Engine.max_fps = 5
	else:
		for child in get_children():
			if child is Control: child.show()
		house_button.hide()
		detail.hide()
		get_window().mouse_passthrough_polygon = PackedVector2Array()
		get_window().transparent = glass
		get_window().transparent_bg = glass
		_set_logical_size(restore_size)
		scene_view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		Engine.max_fps = 30
	var screen := DisplayServer.screen_get_usable_rect()
	var w := 80 if collapsed else restore_size.x
	DisplayServer.window_set_position(Vector2i(700,300) if desktop_background_test else Vector2i(screen.end.x-int((w+18)*display_scale),screen.position.y+56))
	_layout()

func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE: detail.hide()
		elif event.keycode == KEY_H: _toggle_collapse()
		elif event.keycode == KEY_T: _toggle_pin()
		elif event.keycode == KEY_O: _toggle_glass()
		elif event.keycode == KEY_M: _cycle_route()
		elif event.keycode == KEY_N: _toggle_phase()
		elif event.keycode == KEY_F12: _capture("manual")

func _capture(label: String) -> void:
	if output_dir.is_empty(): output_dir = ProjectSettings.globalize_path("res://../comparison/evidence")
	DirAccess.make_dir_recursive_absolute(output_dir)
	await RenderingServer.frame_post_draw
	var s := Vector2(logical_size)
	var file := "%s/%s-%dx%d-%s-%s.png" % [output_dir,route,int(s.x),int(s.y),phase,label]
	assert(get_viewport().get_texture().get_image().save_png(file) == OK)
	print("CAPTURE ",file)

func _click(control: Control) -> void:
	var point := control.get_global_rect().get_center()
	var motion := InputEventMouseMotion.new()
	motion.position = point
	get_viewport().push_input(motion, true)
	# Deliver the pair together so native mouse movement cannot split the pair.
	for pressed in [true,false]:
		var event := InputEventMouseButton.new()
		event.position = point
		event.global_position = point
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = pressed
		get_viewport().push_input(event, true)
	await get_tree().process_frame
	await get_tree().process_frame

func _proof() -> void:
	if film_requested: await _film(8)
	await _click(list_buttons[0])
	await _click(start_button)
	assert(tasks[0].state == "in_progress")
	if film_requested: await _film(18)
	else:
		for i in range(36): await get_tree().process_frame
	await _capture("started")
	await _click(done_button)
	if film_requested: await _film(5)
	await _click(confirm_button)
	if film_requested: await _film(5)
	assert(tasks[0].state == "in_progress")
	note.text = "虚构核验结果；来源 example.invalid/demo；仅供界面验证。"
	await _click(confirm_button)
	assert(tasks[0].state == "completed")
	if film_requested: await _film(34)
	else:
		for i in range(8): await get_tree().process_frame
	await _capture("completed")
	_select_task(1)
	await _click(defer_button)
	assert(tasks[1].state == "deferred")
	await _capture("deferred")
	if film_requested: await _film(8)
	observations.append({"check":"proof_pass","route":route,"size":str(get_viewport_rect().size)})
	print("COMPARISON_PROOF_PASS ",route)

func _film(count: int) -> void:
	for i in range(count):
		await _capture("motion-%03d" % film_index)
		film_index += 1
		await get_tree().create_timer(0.07).timeout

func _desktop_proof() -> void:
	await _click(collapse_button)
	for i in range(4): await get_tree().process_frame
	assert(collapsed and get_window().size == Vector2i(Vector2(80,80)*display_scale))
	await _capture("collapsed")
	await _click(house_button)
	for i in range(4): await get_tree().process_frame
	assert(not collapsed and get_window().size == Vector2i(Vector2(360,320)*display_scale))
	await _capture("restored")
	observations.append({"check":"collapse_restore","window_transparency_supported":DisplayServer.has_feature(DisplayServer.FEATURE_WINDOW_TRANSPARENCY),"always_on_top":get_window().always_on_top})
	print("DESKTOP_UI_PROOF_PASS")

func _write_observations() -> void:
	var s := Vector2(logical_size)
	var path := "%s/%s-%dx%d-%s%s.json" % [output_dir,route,int(s.x),int(s.y),phase,"-desktop" if desktop_requested else ""]
	var file := FileAccess.open(path,FileAccess.WRITE)
	file.store_string(JSON.stringify({"route":route,"phase":phase,"viewport":[s.x,s.y],"window_pixels":[get_window().size.x,get_window().size.y],"display_scale":display_scale,"fictional":true,"engine":Engine.get_version_info().string,"elapsed_ms":(Time.get_ticks_usec()-started_usec)/1000.0,"frame_count":frames.size(),"events":observations},"  "))
