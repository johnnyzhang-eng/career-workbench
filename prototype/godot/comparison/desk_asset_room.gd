extends "res://comparison/room_3d.gd"

# M2 changes only the desk mesh/material in the original A scene. The model's
# 1.13 m width is stretched to A's 3.55 m desk footprint to isolate appearance;
# this does not fix A's room scale and is not a production placement.
func _ready() -> void:
	super._ready()
	var hidden_original_parts := 0
	for child in get_children():
		if child.name == "Desk top" or _is_original_desk_leg(child):
			child.hide()
			hidden_original_parts += 1
	assert(hidden_original_parts == 5)
	var source: PackedScene = load("res://comparison/assets/polyhaven_wooden_table_02_1k.glb")
	assert(source != null)
	var desk := source.instantiate() as Node3D
	desk.name = "Poly Haven Wooden Table 02 trial"
	desk.position = Vector3(-0.65, 0.0, -1.55)
	desk.scale = Vector3(3.13, 1.56, 1.91)
	add_child(desk)
	print("DESK_ASSET", desk.name, "scale=", desk.scale)


func _is_original_desk_leg(child: Node) -> bool:
	# Godot auto-renames duplicate "Desk leg" nodes after the first one.
	# Match the controlled source geometry, not the generated node name.
	if not child is MeshInstance3D:
		return false
	var box := (child as MeshInstance3D).mesh as BoxMesh
	return box != null and box.size.distance_to(Vector3(0.18, 1.14, 0.18)) < 0.001 \
		and absf((child as MeshInstance3D).position.y - 0.57) < 0.001
