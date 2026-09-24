extends Node3D

# A room-only visual adapter. The workbench owns tasks, evidence and completion.
# JavaScript can only set this scene's visual state through a validated DTO.
const MODES := ["idle", "desk", "study", "interview", "rest"]
const PHASES := ["day", "evening"]
const ACTIVITY_STATES := ["unknown", "planned", "declared_active", "observed", "self_selected"]

var room: Node3D
var mode_props: Dictionary = {}
var callback_ref: JavaScriptObject
var last_phase := "day"
var last_mode := "idle"
var last_activity_state := "unknown"


func _ready() -> void:
	Engine.max_fps = 20
	room = load("res://comparison/room_3d.gd").new()
	room.refined = false
	add_child(room)
	room.apply_phase("day")
	_build_mode_props()
	if OS.has_feature("web"):
		callback_ref = JavaScriptBridge.create_callback(_accept_scene_json)
		JavaScriptBridge.get_interface("window").careerRoomSetScene = callback_ref
	print("ROOM_SCENE_READY")


func _accept_scene_json(args: Array) -> void:
	if args.size() != 1 or not args[0] is String:
		return
	var payload = JSON.parse_string(args[0])
	if not payload is Dictionary:
		return
	var phase = payload.get("phase")
	var mode = payload.get("mode")
	var activity_state = payload.get("activity_state")
	if phase not in PHASES or mode not in MODES or activity_state not in ACTIVITY_STATES:
		return
	_apply_scene(phase, mode, activity_state)


func _apply_scene(phase: String, mode: String, activity_state: String) -> void:
	last_phase = phase
	last_mode = mode
	last_activity_state = activity_state
	room.apply_phase(phase)
	room.task_kind = mode
	var active := activity_state in ["declared_active", "observed"] and mode != "idle"
	room.apply_state("in_progress" if active else "scheduled")
	# A plan is a preview only. Self-selected mode is visible without claiming work.
	var visible_mode: String = mode if active or activity_state == "self_selected" else "idle"
	for key in mode_props:
		mode_props[key].visible = key == visible_mode
	print("ROOM_SCENE_APPLIED phase=", phase, " mode=", mode, " activity=", activity_state,
		" visible_mode=", visible_mode)


func _box(parent: Node3D, name: String, position_3d: Vector3, size_3d: Vector3, color: Color) -> void:
	var mesh := BoxMesh.new()
	mesh.size = size_3d
	var node := MeshInstance3D.new()
	node.name = name
	node.mesh = mesh
	node.position = position_3d
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.8
	node.material_override = material
	parent.add_child(node)


func _build_mode_props() -> void:
	for mode in ["desk", "study", "interview", "rest"]:
		var prop := Node3D.new()
		prop.name = mode.capitalize() + " visual cue"
		add_child(prop)
		mode_props[mode] = prop
		prop.visible = false
	# These small reversible markers prove state mapping, not final art direction.
	_box(mode_props["desk"], "Monitor glow", Vector3(-0.85, 1.73, -1.845),
		Vector3(0.97, 0.56, 0.018), Color("80d4cf"))
	_box(mode_props["study"], "Open book left page", Vector3(0.89, 0.08, 1.36),
		Vector3(0.42, 0.04, 0.57), Color("fff9df"))
	_box(mode_props["study"], "Open book right page", Vector3(1.34, 0.08, 1.36),
		Vector3(0.42, 0.04, 0.57), Color("f4e3b9"))
	_box(mode_props["study"], "Book spine", Vector3(1.11, 0.11, 1.36),
		Vector3(0.025, 0.06, 0.58), Color("bd7258"))
	_box(mode_props["interview"], "Interview camera stand", Vector3(2.05, 0.55, 0.42),
		Vector3(0.08, 1.07, 0.08), Color("526d83"))
	_box(mode_props["interview"], "Interview camera", Vector3(2.05, 1.15, 0.42),
		Vector3(0.55, 0.36, 0.30), Color("607f9c"))
	_box(mode_props["rest"], "Tea cup", Vector3(1.95, 0.28, 1.54),
		Vector3(0.31, 0.45, 0.31), Color("d69a68"))
	_box(mode_props["rest"], "Tea surface", Vector3(1.95, 0.52, 1.54),
		Vector3(0.25, 0.02, 0.25), Color("78523d"))
