extends "res://comparison/room_3d.gd"

# Replace only A's single Desk top mesh. Legs and all other nodes stay original.
func _ready() -> void:
	super._ready()
	assert(not refined)
	var original := get_node("Desk top") as MeshInstance3D
	var top_position := original.position
	remove_child(original)
	original.queue_free()
	var asset: PackedScene = load("res://comparison/assets/hero_desk_top.glb")
	assert(asset != null)
	var replacement := asset.instantiate() as Node3D
	replacement.name = "Blender hero desk top"
	replacement.position = top_position
	add_child(replacement)
	var meshes := replacement.find_children("*", "MeshInstance3D", true, false)
	assert(meshes.size() == 1)
	var bounds := (meshes[0] as MeshInstance3D).get_aabb()
	print("HERO_DESK_IMPORTED mesh_count=", meshes.size(),
		" size=", bounds.size,
		" position=", replacement.position)
