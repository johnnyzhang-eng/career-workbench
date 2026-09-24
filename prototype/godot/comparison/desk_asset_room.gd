extends "res://comparison/room_3d.gd"

# M2 changes only the desk mesh/material in the original A scene. The model's
# 1.13 m width is stretched to A's 3.55 m desk footprint to isolate appearance;
# this does not fix A's room scale and is not a production placement.
func _ready() -> void:
	super._ready()
	for child in get_children():
		if child.name.begins_with("Desk top") or child.name.begins_with("Desk leg"):
			child.hide()
	var source: PackedScene = load("res://comparison/assets/polyhaven_wooden_table_02_1k.glb")
	assert(source != null)
	var desk := source.instantiate() as Node3D
	desk.name = "Poly Haven Wooden Table 02 trial"
	desk.position = Vector3(-0.65, 0.0, -1.55)
	desk.scale = Vector3(3.13, 1.56, 1.91)
	add_child(desk)
	print("DESK_ASSET", desk.name, "scale=", desk.scale)
