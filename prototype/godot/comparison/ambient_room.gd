extends "res://comparison/room_3d.gd"

# A-only experiment. The sole scene parameter changed is ambient light energy.
var ambient_multiplier := 1.0

func apply_phase(value: String) -> void:
	super.apply_phase(value)
	if not is_node_ready():
		return
	for child in get_children():
		if child is WorldEnvironment:
			child.environment.ambient_light_energy *= ambient_multiplier
			print("AMBIENT_ACTUAL phase=", value, " multiplier=", ambient_multiplier, " energy=", child.environment.ambient_light_energy)
			return
