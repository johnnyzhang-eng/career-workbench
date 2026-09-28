extends "res://comparison/room_3d.gd"

# Keep the original A geometry, camera, lights, and materials unchanged.
var experiment_ssao := false

func _ready() -> void:
	super._ready()
	for child in get_children():
		if child is WorldEnvironment:
			child.environment.ssao_enabled = experiment_ssao
			print("SSAO_ENABLED ", child.environment.ssao_enabled)
			return
	push_error("SSAO experiment cannot find WorldEnvironment")
