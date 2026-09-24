extends Node2D
## Original vector geometry; low resolution presentation is a rendering treatment.
var phase: String = "day"
var task_state: String = "scheduled"
var task_kind: String = "verify_job"
var elapsed := 0.0
var state_elapsed := 0.0
var scale_factor := 1.0
var offset := Vector2.ZERO
const INK := Color("514943")
const WOOD := Color("c39772")
const PAPER := Color("fff2d9")

func apply_state(value: String) -> void:
	task_state = value
	state_elapsed = 0.0
	queue_redraw()

func apply_phase(value: String) -> void:
	phase = value
	queue_redraw()

func _process(delta: float) -> void:
	elapsed += delta
	state_elapsed += delta
	var size := get_viewport_rect().size
	scale_factor = minf(size.x / 960.0, size.y / 600.0)
	offset = (size - Vector2(960, 600) * scale_factor) * 0.5
	queue_redraw()

func hotspot_points() -> Dictionary:
	return {"computer": offset + Vector2(574, 200) * scale_factor, "calendar": offset + Vector2(754, 255) * scale_factor}

func p(x: float, z: float, h: float = 0.0) -> Vector2:
	return Vector2(480 + (x - z) * 55, 235 + (x + z) * 26 - h * 50)

func poly(points: Array, color: Color, edge: bool = true) -> void:
	var vertices := PackedVector2Array(points)
	draw_colored_polygon(vertices, color)
	if edge:
		vertices.append(vertices[0])
		draw_polyline(vertices, INK, 1.8, true)

func line(a: Vector2, b: Vector2, color: Color = INK, width: float = 1.8) -> void:
	draw_line(a, b, color, width, true)

func box(x: float, z: float, w: float, d: float, bottom: float, top: float, color: Color) -> void:
	poly([p(x,z,bottom),p(x+w,z,bottom),p(x+w,z,top),p(x,z,top)],color.darkened(0.13))
	poly([p(x+w,z,bottom),p(x+w,z+d,bottom),p(x+w,z+d,top),p(x+w,z,top)],color.darkened(0.24))
	poly([p(x,z,top),p(x+w,z,top),p(x+w,z+d,top),p(x,z+d,top)],color.lightened(0.1))

func ellipse(center: Vector2, radius: Vector2, color: Color, edge: bool = false) -> void:
	var pts: Array = []
	for i in range(40):
		var angle := float(i) / 40.0 * TAU
		pts.append(center + Vector2(cos(angle),sin(angle)) * radius)
	poly(pts,color,edge)

func _draw() -> void:
	var night := phase == "night" or phase == "evening"
	# Fill the actual viewport before letterboxing the room composition.
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	draw_rect(Rect2(Vector2.ZERO, get_viewport_rect().size),Color("c7c7ca") if night else Color("eee3d1"))
	draw_set_transform(offset,0,Vector2.ONE * scale_factor)
	ellipse(Vector2(492,530),Vector2(343,43),Color(0.24,0.22,0.20,0.13))
	# A complete cutaway: warm plaster, a sage rear wall and timber floor.
	poly([p(0,0),p(0,6),p(0,6,3.8),p(0,0,3.8)],Color("c3d2bc") if not night else Color("879b93"))
	poly([p(0,0),p(6,0),p(6,0,3.8),p(0,0,3.8)],Color("ecd7b7") if not night else Color("aaa292"))
	poly([p(0,0),p(6,0),p(6,6),p(0,6)],Color("cfae88"))
	for n in range(1,12):
		line(p(float(n)*0.5,0),p(float(n)*0.5,6),Color("b79673"),1)
	for n in range(6):
		var x := float(n)+0.5
		line(p(x,2),p(x+0.5,2),Color("b79673"),1)
		line(p(x-0.5,4),p(x,4),Color("b79673"),1)
	line(p(0,0,0.13),p(0,6,0.13),Color("f6e5c8"),7)
	line(p(0,0,0.13),p(6,0,0.13),Color("f6e5c8"),7)
	poly([p(0,6),p(6,6),p(6,6,-0.17),p(0,6,-0.17)],Color("9a775d"))
	poly([p(6,0),p(6,6),p(6,6,-0.17),p(6,0,-0.17)],Color("b08765"))
	# Window on left wall, with structural mullions and a small sill plant.
	poly([p(0,0.8,1.6),p(0,2.75,1.6),p(0,2.75,3.32),p(0,0.8,3.32)],Color("f9eedb"))
	poly([p(0,0.95,1.75),p(0,2.6,1.75),p(0,2.6,3.17),p(0,0.95,3.17)],Color("384961") if night else Color("b5d2cf"))
	line(p(0,1.78,1.75),p(0,1.78,3.17),PAPER,5)
	line(p(0,0.95,2.45),p(0,2.6,2.45),PAPER,5)
	box(0,0.72,0.36,2.12,1.52,1.62,WOOD)
	var plant := p(0.2,2.25,1.65)
	poly([plant+Vector2(-11,0),plant+Vector2(10,5),plant+Vector2(7,22),plant+Vector2(-7,17)],Color("bc785d"))
	for i in range(5):
		var tip := plant+Vector2(float(i-2)*8,-17-absf(float(i-2))*3)
		line(plant+Vector2(0,3),tip,Color("567757"),2)
		ellipse(tip,Vector2(6,11),Color("718b60"))
	# Left shelving: distinct book spines and horizontal shelves.
	box(0.13,3.75,0.67,1.65,0,2.3,WOOD)
	for level in range(3):
		var h := 0.15 + float(level)*0.73
		box(0.81,3.82,0.08,1.52,h,h+0.06,Color("f1d3ac"))
		for book in range(6):
			var book_color: Color = [Color("6c8d88"),Color("cd8c62"),Color("f0d59e"),Color("8a8d9b")][book%4]
			box(0.81,3.89+float(book)*0.22,0.16,0.15,h+0.06,h+0.47+float(book%2)*0.09,book_color)
	# Woven rug anchors the character and chair.
	poly([p(1.3,2.15,0.01),p(4.65,2.15,0.01),p(4.65,5.3,0.01),p(1.3,5.3,0.01)],Color("9aa9a0"))
	poly([p(1.5,2.35,0.02),p(4.45,2.35,0.02),p(4.45,5.1,0.02),p(1.5,5.1,0.02)],Color("c2c8ad"))
	for n in range(8):
		line(p(1.55+float(n)*0.4,2.4,0.03),p(1.55+float(n)*0.4,5,0.03),Color("aeb99f"),1)
	# Desk, solid legs, notebook and a cup.
	for dx in [1.05,3.83]:
		for dz in [0.6,1.59]:
			box(dx,dz,0.12,0.12,0,1.3,Color("826951"))
	box(0.9,0.45,3.2,1.4,1.25,1.4,WOOD)
	box(1.04,0.65,0.72,0.48,1.4,1.45,PAPER)
	line(p(1.4,0.65,1.46),p(1.4,1.13,1.46),Color("b29b7f"),1)
	var cup := p(3.69,1.03,1.42)
	draw_rect(Rect2(cup-Vector2(6,17),Vector2(12,17)),Color("e5e7d2"))
	ellipse(cup-Vector2(0,17),Vector2(6,3),Color("775f4b"),true)
	draw_arc(cup+Vector2(6,-8),5,-PI/2,PI/2,12,PAPER,3,true)
	# Monitor is readable as a monitor at both comparison scales.
	box(2.18,0.82,0.65,0.4,1.4,1.44,Color("454d51"))
	line(p(2.52,0.96,1.42),p(2.52,0.96,1.77),INK,6)
	var screen := p(2.48,0.8,2.06)
	poly([screen+Vector2(-45,-43),screen+Vector2(44,-1),screen+Vector2(44,45),screen+Vector2(-45,3)],Color("424e51"))
	poly([screen+Vector2(-39,-35),screen+Vector2(37,1),screen+Vector2(37,35),screen+Vector2(-39,-1)],Color("badacb"))
	for i in range(3):
		line(screen+Vector2(-27,-21+i*9),screen+Vector2(22,2+i*9),Color("769b92"),2)
	box(2.02,1.36,1.03,0.29,1.41,1.46,Color("e2dfcf"))
	# Calendar on right wall. No text baked into the illustration.
	poly([p(4.43,0,2.82),p(5.55,0,2.82),p(5.55,0,1.62),p(4.43,0,1.62)],PAPER)
	poly([p(4.43,0,2.82),p(5.55,0,2.82),p(5.55,0,2.6),p(4.43,0,2.6)],Color("c87556"))
	for row in range(3):
		for col in range(4):
			var dot := p(4.61+float(col)*0.23,0,2.38-float(row)*0.26)
			draw_circle(dot,2.5,Color("988b78"))
	draw_circle(p(5.07,0,2.12),5,Color("d38358"))
	# Chair behind the student.
	box(2.46,2.7,0.8,0.74,0.65,0.8,Color("778c83"))
	for dx in [2.5,3.16]:
		box(dx,3.34,0.1,0.1,0,1.5,Color("7b6959"))
	box(2.46,3.36,0.8,0.09,0.97,1.5,Color("90a298"))
	_student()
	if night:
		draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		draw_rect(Rect2(Vector2.ZERO, get_viewport_rect().size),Color(0.13,0.19,0.3,0.10))

func _student() -> void:
	var moving := task_state == "in_progress"
	var approach := minf(state_elapsed,1.0) if moving else 0.0
	var c := p(3.68-approach*0.45,3.78-approach*0.4)
	ellipse(c+Vector2(0,5),Vector2(33,12),Color(0.23,0.24,0.21,0.18))
	var bounce := sin(elapsed*2.0)*0.65
	c.y += bounce
	var skin := Color("eab991")
	# Shoes, trousers, green backpack and orange sweatshirt.
	ellipse(c+Vector2(-13,-3),Vector2(13,7),Color("f5e8cc"),true)
	ellipse(c+Vector2(13,-3),Vector2(13,7),Color("f5e8cc"),true)
	poly([c+Vector2(-21,-40),c+Vector2(21,-40),c+Vector2(20,-8),c+Vector2(5,-8),c+Vector2(0,-27),c+Vector2(-5,-8),c+Vector2(-20,-8)],Color("515e66"))
	ellipse(c+Vector2(23,-67),Vector2(17,26),Color("859d83"),true)
	poly([c+Vector2(-24,-90),c+Vector2(16,-90),c+Vector2(26,-48),c+Vector2(20,-35),c+Vector2(-23,-35),c+Vector2(-28,-49)],Color("d98b50"))
	ellipse(c+Vector2(-2,-88),Vector2(18,9),Color("ba7044"),true)
	line(c+Vector2(-7,-80),c+Vector2(-6,-65),PAPER,2)
	line(c+Vector2(6,-80),c+Vector2(7,-65),PAPER,2)
	poly([c+Vector2(-13,-54),c+Vector2(11,-54),c+Vector2(15,-42),c+Vector2(-17,-42)],Color("ce8047"))
	line(c+Vector2(16,-87),c+Vector2(23,-52),Color("6c866f"),5)
	# A short response completes then returns to a still pose.
	var celebrate := task_state == "completed" and state_elapsed < 2.3
	var left_hand := c+Vector2(-31,-51)
	var right_hand := c+Vector2(32,-52)
	if moving:
		left_hand = c+Vector2(-30,-78+sin(elapsed*5.0)*2.2)
	if celebrate:
		right_hand = c+Vector2(40+sin(state_elapsed*12)*5,-107)
	line(c+Vector2(-23,-78),left_hand,INK,15)
	line(c+Vector2(-23,-78),left_hand,Color("dc9256"),12)
	line(c+Vector2(22,-77),right_hand,INK,15)
	line(c+Vector2(22,-77),right_hand,Color("dc9256"),12)
	draw_circle(left_hand,6,skin)
	draw_circle(right_hand,6,skin)
	line(left_hand+Vector2(-5,-3),left_hand+Vector2(5,-3),Color("edd5a9"),3)
	# Strong round silhouette, ears, bangs, eyebrows, eyes and mouth.
	ellipse(c+Vector2(-1,-115),Vector2(34,35),Color("3b3a39"),true)
	draw_circle(c+Vector2(-31,-110),6,skin)
	draw_circle(c+Vector2(29,-110),6,skin)
	ellipse(c+Vector2(-2,-109),Vector2(27,27),skin,true)
	poly([c+Vector2(-30,-117),c+Vector2(-27,-139),c+Vector2(-8,-148),c+Vector2(16,-143),c+Vector2(29,-126),c+Vector2(17,-119),c+Vector2(10,-130),c+Vector2(-1,-118),c+Vector2(-7,-127),c+Vector2(-20,-114)],Color("3b3a39"))
	var gaze := -5.0 if moving else 0.0
	for eye_x in [-12.0,10.0]:
		draw_circle(c+Vector2(eye_x+gaze,-108),2.8,INK)
		line(c+Vector2(eye_x-3+gaze,-115),c+Vector2(eye_x+3+gaze,-115),INK,1.4)
	draw_arc(c+Vector2(gaze,-102),6,0.2,PI-0.2,12,Color("995c4b"),1.5,true)
	ellipse(c+Vector2(-18,-99),Vector2(5,2),Color("dba080"))
	ellipse(c+Vector2(17,-99),Vector2(5,2),Color("dba080"))
	if celebrate:
		for i in range(3):
			var spark := c+Vector2(-45+float(i)*44,-167-absf(float(i-1))*5)
			line(spark-Vector2(0,5),spark+Vector2(0,5),Color("d69d47"),2)
			line(spark-Vector2(5,0),spark+Vector2(5,0),Color("d69d47"),2)
