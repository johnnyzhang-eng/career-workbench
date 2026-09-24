extends "res://main.gd"

# Same baseline geometry; this file keeps the control scene untouched.
var refined := true
var phase := "day"
var task_state := "scheduled"
var task_kind := "verify_job"
var elapsed := 0.0
var transition := 0.0
var home := Vector3(1.25, 0, 0.7)
var working := Vector3(-0.50, 0, -0.36)
var light: DirectionalLight3D
var desk_light: OmniLight3D

func _ready() -> void:
	_build_room()
	for child in get_children():
		if child is DirectionalLight3D:
			light = child
	if refined:
		_refine_room()
	apply_phase(phase)
	apply_state(task_state)

func _process(delta: float) -> void:
	elapsed += delta
	transition += delta
	if refined:
		var aspect: float = float(get_viewport().size.x) / get_viewport().size.y
		camera.size = 6.7 if aspect > 2.0 else (10.8 if aspect < 1.3 else 8.7)
	if not refined:
		hand.rotation.z = 0.12 * sin(elapsed * 7) if task_state == "in_progress" else 0.0
		return
	if task_state == "in_progress":
		character.position = home.lerp(working, smoothstep(0, 1, minf(transition, 1.0)))
		character.rotation.y = PI * smoothstep(0, 1, minf(transition, 1.0))
		hand.rotation = Vector3(-0.65 + sin(elapsed * 4) * 0.05, 0, 0)
		character.position.y = absf(sin(elapsed * 9)) * 0.04 if transition < 1 else 0.0
	elif task_state == "completed":
		character.position = home
		character.rotation.y = 0
		hand.rotation = Vector3(0, 0, 1.9 + 0.20 * sin(elapsed * 5)) if transition < 2 else Vector3.ZERO
	else:
		character.position = home
		character.rotation.y = 0
		hand.rotation = Vector3.ZERO

func _unhandled_input(_event: InputEvent) -> void:
	pass

func apply_state(value: String) -> void:
	task_state = value
	transition = 0.0

func apply_phase(value: String) -> void:
	phase = value
	if not is_node_ready():
		return
	var environment: Environment
	for child in get_children():
		if child is WorldEnvironment:
			environment = child.environment
	if phase == "evening":
		light.light_color = Color("b9c5ed")
		light.light_energy = 0.35
		environment.background_color = Color("29394b")
		environment.ambient_light_color = Color("9cacca")
		environment.ambient_light_energy = 0.48
	else:
		light.light_color = Color("ffe9cc")
		light.light_energy = 0.42 if refined else 0.65
		environment.background_color = Color("dedfd4")
		environment.ambient_light_color = Color("e0e9dc")
		environment.ambient_light_energy = 0.65 if refined else 0.36
	if desk_light:
		desk_light.light_energy = 0.9 if phase == "evening" else 0.15

func hotspot_points() -> Dictionary:
	if not camera:
		return {}
	return {"computer":camera.unproject_position(Vector3(-0.85, 2.20, -1.9)), "calendar":camera.unproject_position(Vector3(1.1, 3.15, -2.85))}

func _refine_room() -> void:
	# Preserve the baseline cutaway and identity, move chair clear of the working pose.
	for child in get_children():
		if child.name.begins_with("Chair"):
			child.position += Vector3(-0.92,0,0.25)
	get_node("Left wall").material_override = _material(Color("bbcbb7"))
	get_node("Rug").material_override = _material(Color("b6c7a8"))
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-35,125,0)
	fill.light_color = Color("d3e1e4")
	fill.light_energy = 0.22
	fill.shadow_enabled = false
	add_child(fill)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 8.7
	camera.position = Vector3(7.5, 6.2, 9)
	camera.look_at(Vector3(-0.1, 1.25, -0.4))
	for i in range(8):
		_box(self, "Floor seam", Vector3(-3.1 + i * 0.88, 0.006, 0), Vector3(0.012, 0.012, 6.0), Color("bd986f"))
	# Original study props, available to recruiting and learning goals alike.
	_box(self, "Open notebook", Vector3(0.25, 1.27, -1.24), Vector3(0.63, 0.035, 0.35), Color("f4e6c9"))
	_box(self, "Notebook spine", Vector3(0.25, 1.295, -1.24), Vector3(0.014, 0.008, 0.32), Color("bca782"))
	for i in range(3):
		_box(self, "Note line", Vector3(0.08, 1.296, -1.33 + i * 0.07), Vector3(0.17, 0.007, 0.007), Color("a8aaa0"))
	_cylinder(self, "Cup", Vector3(-1.89, 1.39, -1.34), 0.105, 0.25, Color("f1cc9f"))
	_cylinder(self, "Tea", Vector3(-1.89, 1.521, -1.34), 0.083, 0.01, Color("735440"))
	_cylinder(self, "Plant pot", Vector3(-2.64, 1.66, -2.64), 0.18, 0.27, Color("bd745c"))
	for i in range(5):
		var leaf := _sphere(self, "Leaf", Vector3(-2.64 + sin(i * 1.7) * 0.19, 1.91 + (i % 2) * 0.12, -2.64 + cos(i * 1.7) * 0.14), 0.15, Color("6e9272"))
		leaf.scale = Vector3(0.7, 1.4, 0.6)
	var body := character.get_node("Oversized hoodie") as MeshInstance3D
	body.scale = Vector3(0.93, 1.05, 0.83)
	_box(character, "Hoodie pocket", Vector3(0, 0.90, 0.406), Vector3(0.42, 0.22, 0.027), Color("bd6149"))
	for x in [-0.075, 0.075]:
		_box(character, "Drawstring", Vector3(x, 1.30, 0.35), Vector3(0.018, 0.18, 0.02), Color("f6d2ad"))
	for x in [-0.44, 0.44]:
		_sphere(character, "Ear", Vector3(x, 1.80, 0.03), 0.095, Color("deb191"))
	for x in [-0.17, 0.17]:
		_box(character, "Eyebrow", Vector3(x, 1.99, 0.40), Vector3(0.1, 0.024, 0.027), Color("514440"))
		_sphere(character, "Cheek", Vector3(x * 1.45, 1.73, 0.383), 0.055, Color("de9a83"))
	_box(character, "Smile", Vector3(0, 1.66, 0.432), Vector3(0.075, 0.023, 0.018), Color("986454"))
	for i in range(3):
		var fringe := _sphere(character, "Fringe", Vector3(-0.20 + i * 0.16, 2.075 - i * 0.035, 0.28), 0.14, Color("4d4242"))
		fringe.scale = Vector3(1.0, 0.55, 0.50)
	for x in [-0.22, 0.22]:
		_cylinder(character, "Shoe sole", Vector3(x, 0.035, 0.12), 0.195, 0.05, Color("eadac4"))
	_box(character, "Backpack tag", Vector3(0.14, 1.0, -0.612), Vector3(0.07, 0.08, 0.008), Color("d49360"))
	desk_light = OmniLight3D.new()
	desk_light.position = Vector3(0.46, 2.0, -1.7)
	desk_light.light_color = Color("ffc580")
	desk_light.omni_range = 3.2
	add_child(desk_light)
