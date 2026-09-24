extends "res://comparison/room_3d.gd"

# A-only framing experiment. Perspective FOV, target, light, materials and
# geometry stay exactly as in the original baseline room.
var compact_distance_scale := 1.0
const CAMERA_HOME := Vector3(7.5, 6.2, 9.0)
const CAMERA_TARGET := Vector3(0, 1.25, 0)

func apply_compact_framing(enabled: bool) -> void:
	if not camera:
		return
	camera.position = CAMERA_TARGET + (CAMERA_HOME - CAMERA_TARGET) * (compact_distance_scale if enabled else 1.0)
	camera.look_at(CAMERA_TARGET)
	assert(is_equal_approx(camera.fov, 45.0))
