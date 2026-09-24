extends "res://comparison/room_3d.gd"

# K1 replaces exactly one baseline scene node. The scene, lights, camera,
# character, chair, desk, screen, task fixture and UI remain A's baseline.
func _ready() -> void:
	super._ready()
	assert(not refined)
	var original := get_node("Keyboard") as MeshInstance3D
	var original_position := original.position
	remove_child(original)
	original.queue_free()
	var asset: PackedScene = load("res://comparison/assets/keyboard_contact.glb")
	assert(asset != null)
	var replacement := asset.instantiate() as Node3D
	replacement.name = "Blender keyboard contact"
	replacement.position = original_position
	add_child(replacement)
	var meshes := replacement.find_children("*", "MeshInstance3D", true, false)
	assert(meshes.size() > 0)
	print("KEYBOARD_CONTACT_IMPORTED mesh_count=", meshes.size(),
		" position=", replacement.position)
