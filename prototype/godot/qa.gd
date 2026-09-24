extends SceneTree


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var scene: PackedScene = load("res://main.tscn")
	var game := scene.instantiate()
	root.add_child(game)
	await process_frame
	assert(game.task["id"] == "DEMO-TASK-001")
	assert(game.preview_state == "scheduled")
	assert(game.get_node("computer").get_meta("hotspot") == "computer")
	assert(game.get_node("calendar").get_meta("hotspot") == "calendar")
	assert(game.has_node("Blender desk lamp"), "Imported Blender GLB is not in the scene")
	game._complete_task()
	assert(game.preview_state == "scheduled", "Cannot complete before start")
	game._start_task()
	assert(game.preview_state == "in_progress")
	game._complete_task()
	assert(game.preview_state == "in_progress", "Evidence gate did not block completion")
	game.note_input.text = "Fictional requirement reviewed"
	game.url_input.text = "https://example.invalid/demo-job-001"
	game._complete_task()
	assert(game.preview_state == "completed")
	game._defer_task()
	assert(game.preview_state == "completed", "Completed task was deferred")
	game.queue_free()
	await process_frame
	var second := scene.instantiate()
	root.add_child(second)
	await process_frame
	second._defer_task()
	assert(second.preview_state == "deferred")
	assert(second.task["due_verified"] == false)
	print("SCENE_QA_OK fixture, Blender import, hotspots, completion gate, defer feedback")
	quit()
