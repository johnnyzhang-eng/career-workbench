extends "res://comparison/room_3d.gd"

# A-only experiment. Pitch is the sole changed light parameter.
var key_pitch_degrees := -55.0

func _ready() -> void:
	super._ready()
	assert(not refined)
	# K0 must leave the original transform untouched, including float rounding.
	if not is_equal_approx(key_pitch_degrees, -55.0):
		light.rotation_degrees.x = key_pitch_degrees

func apply_phase(value: String) -> void:
	super.apply_phase(value)
	if not is_node_ready():
		return
	var ambient_energy := -1.0
	for child in get_children():
		if child is WorldEnvironment:
			ambient_energy = child.environment.ambient_light_energy
			break
	print("KEY_LIGHT_ACTUAL phase=", value,
		" pitch=", light.rotation_degrees.x,
		" yaw=", light.rotation_degrees.y,
		" roll=", light.rotation_degrees.z,
		" energy=", light.light_energy,
		" ambient=", ambient_energy)
