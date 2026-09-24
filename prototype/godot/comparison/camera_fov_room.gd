extends "res://comparison/room_3d.gd"

# A-only experiment: perspective field of view is the sole changed parameter.
var experiment_fov_degrees := 45.0

func _ready() -> void:
	super._ready()
	assert(not refined)
	# Leave C0's original camera untouched, including float rounding.
	if not is_equal_approx(experiment_fov_degrees, 45.0):
		camera.fov = experiment_fov_degrees

func apply_phase(value: String) -> void:
	super.apply_phase(value)
	if not is_node_ready():
		return
	var ambient_energy := -1.0
	for child in get_children():
		if child is WorldEnvironment:
			ambient_energy = child.environment.ambient_light_energy
			break
	print("CAMERA_ACTUAL phase=", value,
		" fov=", camera.fov,
		" posx=", camera.position.x,
		" posy=", camera.position.y,
		" posz=", camera.position.z,
		" main_energy=", light.light_energy,
		" ambient=", ambient_energy)
