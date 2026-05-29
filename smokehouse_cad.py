#!/usr/bin/env python3
"""商用烟熏腊肉香肠炉 — build123d CAD 模型"""

import build123d as bd
from build123d import *
import os

# ============================================================
# 全局参数 (mm)
# ============================================================
BOX_W, BOX_D, BOX_H = 1200, 800, 1800
INS = 50
OUTER_T, INNER_T = 1.0, 1.5
INNER_W = BOX_W - 2*(INS+INNER_T)
INNER_D = BOX_D - 2*(INS+INNER_T)
INNER_H = BOX_H - 2*(INS+INNER_T)
DOOR_W = (BOX_W - 6) / 2
DOOR_H = BOX_H - 40
RACK_LAYERS = 4
RACK_SPACING = 350
RACK_START = INS + INNER_T + 250
HEATER_DIA = 16
HEATER_LEN = 500
SMOKER_DIA, SMOKER_H, PIPE_DN = 180, 250, 50
CHIMNEY_DN, CHIMNEY_H = 80, 300
FAN_DIA, FAN_DEPTH = 120, 60
FILTER_W, FILTER_D, FILTER_H = 300, 200, 400
WHEEL_DIA, WHEEL_OFFSET = 130, 120
CTRL_W, CTRL_H, CTRL_D = 180, 300, 50
OUTPUT_DIR = r'd:\multimodal_agent_federation_mvp\preview'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 零件构建函数
# ============================================================
def make_box(w, d, h, label=""):
    b = Box(w, d, h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    if label: b.label = label
    return b

def make_cyl(r, h, label=""):
    c = Cylinder(r, h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    if label: c.label = label
    return c

# ============================================================
# 全部零件
# ============================================================
parts = []

# 1. 外箱 (201不锈钢)
outer = make_box(BOX_W, BOX_D, BOX_H, "OuterShell_201_1.0mm")
outer.color = (0.47, 0.56, 0.61, 0.6)
parts.append(("OuterShell", outer))

# 2. 保温层空间
insulation = make_box(BOX_W-OUTER_T*2, BOX_D-OUTER_T*2, BOX_H-OUTER_T*2, "Insulation_RockWool_50mm")
insulation.color = (0.98, 0.54, 0.40, 0.5)
parts.append(("Insulation", insulation))

# 3. 内胆 (304不锈钢)
inner = make_box(INNER_W, INNER_D, INNER_H, "InnerChamber_304_1.5mm")
inner.color = (0.69, 0.75, 0.77, 1.0)
parts.append(("InnerChamber", inner))

# 4. 左门
left_door = make_box(DOOR_W-4, 20, DOOR_H-4, "LeftDoor")
left_door.color = (0.55, 0.62, 0.66, 0.8)
parts.append(("LeftDoor", left_door))

# 5. 右门
right_door = make_box(DOOR_W-4, 20, DOOR_H-4, "RightDoor")
right_door.color = (0.55, 0.62, 0.66, 0.8)
parts.append(("RightDoor", right_door))

# 6. 门观察窗 (在门上开矩形孔)
window = make_box(200, 22, 150, "ObservationWindow")
window.color = (0.51, 0.83, 0.98, 0.4)
parts.append(("Window", window))

# 7. 门把手
handle = make_cyl(8, 60, "DoorHandle")
handle.color = (0.81, 0.85, 0.86, 1.0)
parts.append(("Handle", handle))

# 8-11. 4层挂架
for i in range(RACK_LAYERS):
    ry = RACK_START + i * RACK_SPACING
    beam = make_box(INNER_W-20, INNER_D-20, 25, f"Rack_Beam_L{i+1}_y{ry}")
    beam.color = (1.0, 0.84, 0.31, 1.0)
    parts.append((f"RackLayer{i+1}", beam))

    # 支撑角码
    bracket_l = make_box(15, 30, 20, f"RackBracket_L{i+1}")
    bracket_l.color = (1.0, 0.84, 0.31, 1.0)
    parts.append((f"RackBracket_L{i+1}", bracket_l))
    bracket_r = make_box(15, 30, 20, f"RackBracket_R{i+1}")
    bracket_r.color = (1.0, 0.84, 0.31, 1.0)
    parts.append((f"RackBracket_R{i+1}", bracket_r))

# 12. 顶部挂轨
rail = make_cyl(8, INNER_D-40, "TopHangingRail")
rail.color = (1.0, 0.84, 0.31, 1.0)
parts.append(("TopRail", rail))

# 13. 挂肉钩 (10个简化)
for h in range(10):
    hook = make_cyl(3, 40, f"MeatHook_{h+1}")
    hook.color = (0.81, 0.85, 0.86, 1.0)
    parts.append((f"Hook{h+1}", hook))

# 14-15. 加热管 x2
for idx, side in enumerate([-1, 1]):
    hx = (INNER_W * 0.38) * side
    tube = make_cyl(HEATER_DIA/2, HEATER_LEN, f"HeaterTube_{idx+1}_3kW")
    tube.color = (1.0, 0.60, 0.0, 1.0)
    parts.append((f"HeaterTube_{idx+1}", tube))

    guard = make_box(HEATER_LEN+60, HEATER_DIA*4, 40, f"HeaterGuard_{idx+1}")
    guard.color = (1.0, 0.60, 0.0, 0.3)
    parts.append((f"HeaterGuard_{idx+1}", guard))

# 16. 循环风机
fan_housing = make_cyl(FAN_DIA/2, FAN_DEPTH, "CirculationFan_Housing")
fan_housing.color = (0.08, 0.34, 0.75, 1.0)
parts.append(("FanHousing", fan_housing))

# 扇叶
for a in range(3):
    blade = make_box(5, FAN_DIA*0.4, FAN_DEPTH*0.8, f"FanBlade_{a+1}")
    blade.color = (0.39, 0.71, 0.96, 1.0)
    parts.append((f"FanBlade_{a+1}", blade))

fan_motor = make_cyl(25, 40, "FanMotor")
fan_motor.color = (0.22, 0.28, 0.31, 1.0)
parts.append(("FanMotor", fan_motor))

# 17. 发烟器
smoker_body = make_cyl(SMOKER_DIA/2, SMOKER_H, "SmokeGenerator_Body_304")
smoker_body.color = (0.91, 0.27, 0.38, 1.0)
parts.append(("SmokerBody", smoker_body))

smoker_lid = make_cyl(SMOKER_DIA/2+5, 15, "SmokerLid")
smoker_lid.color = (0.78, 0.16, 0.16, 1.0)
parts.append(("SmokerLid", smoker_lid))

smoker_heater = make_box(150, 10, 150, "SmokerHeater_1kW")
smoker_heater.color = (1.0, 0.60, 0.0, 1.0)
parts.append(("SmokerHeater", smoker_heater))

# 18. DN50烟管
smoke_pipe = make_cyl(PIPE_DN/2, 400, "SmokePipe_DN50")
smoke_pipe.color = (1.0, 0.44, 0.26, 1.0)
parts.append(("SmokePipe", smoke_pipe))

smoke_valve = make_box(70, 70, 60, "BallValve_DN50")
smoke_valve.color = (0.81, 0.85, 0.86, 1.0)
parts.append(("SmokeValve", smoke_valve))

# 19. 排烟管 DN80
chimney_pipe = make_cyl(CHIMNEY_DN/2, CHIMNEY_H, "ChimneyPipe_DN80")
chimney_pipe.color = (0.38, 0.49, 0.55, 1.0)
parts.append(("ChimneyPipe", chimney_pipe))

chimney_flange = make_cyl(CHIMNEY_DN/2+15, 8, "ChimneyFlange")
chimney_flange.color = (0.38, 0.49, 0.55, 1.0)
parts.append(("ChimneyFlange", chimney_flange))

butterfly_valve = make_box(CHIMNEY_DN+20, 12, CHIMNEY_DN+20, "ButterflyValve_DN80")
butterfly_valve.color = (0.91, 0.27, 0.38, 1.0)
parts.append(("ButterflyValve", butterfly_valve))

# 20. 水幕过滤箱
filter_box = make_box(FILTER_W, FILTER_D, FILTER_H, "WaterFilterBox_304")
filter_box.color = (0.13, 0.39, 0.75, 1.0)
parts.append(("FilterBox", filter_box))

# 隔板 ×2
for i in range(2):
    baffle = make_box(FILTER_W-10, 5, FILTER_H-20, f"FilterBaffle_{i+1}")
    baffle.color = (0.73, 0.85, 0.95, 1.0)
    parts.append((f"FilterBaffle_{i+1}", baffle))

# 活性炭层
carbon = make_box(FILTER_W-10, FILTER_D-10, 20, "ActivatedCarbon")
carbon.color = (0.26, 0.27, 0.30, 1.0)
parts.append(("Carbon", carbon))

# 循环水泵
water_pump = make_box(80, 60, 100, "WaterPump_50W")
water_pump.color = (0.22, 0.28, 0.31, 1.0)
parts.append(("WaterPump", water_pump))

# 废水收集槽
waste_tank = make_box(FILTER_W, 100, 80, "WasteWaterTank")
waste_tank.color = (0.76, 0.30, 0.30, 1.0)
parts.append(("WasteTank", waste_tank))

# 21. 控制面板
ctrl_box = make_box(CTRL_W, CTRL_D, CTRL_H, "ControlPanel_Enclosure")
ctrl_box.color = (0.30, 0.69, 0.31, 1.0)
parts.append(("ControlPanel", ctrl_box))

pid_unit = make_box(96, 15, 96, "PID_Controller_AI518")
pid_unit.color = (0.10, 0.14, 0.49, 1.0)
parts.append(("PID", pid_unit))

estop = make_cyl(22, 25, "EmergencyStop")
estop.color = (0.82, 0.18, 0.18, 1.0)
parts.append(("EStop", estop))

# 22. 万向轮 (4个)
for idx, (wx, wz) in enumerate([
    (-BOX_W/2+150, -BOX_D/2+100),
    (-BOX_W/2+150,  BOX_D/2-100),
    ( BOX_W/2-150, -BOX_D/2+100),
    ( BOX_W/2-150,  BOX_D/2-100),
]):
    wheel = make_cyl(WHEEL_DIA/2, 32, f"CasterWheel_{idx+1}")
    wheel.color = (0.22, 0.28, 0.31, 1.0)
    parts.append((f"Wheel_{idx+1}", wheel))

    brake = make_box(15, 10, 35, f"Brake_{idx+1}")
    brake.color = (0.82, 0.18, 0.18, 1.0)
    parts.append((f"Brake_{idx+1}", brake))

# 23. 集油盘
oil_tray = make_box(INNER_W-10, INNER_D-10, 15, "OilTray_304")
oil_tray.color = (0.69, 0.75, 0.77, 1.0)
parts.append(("OilTray", oil_tray))

# 24. 排污阀
drain_valve = make_box(30, 30, 50, "DrainValve_1/2inch")
drain_valve.color = (0.81, 0.85, 0.86, 1.0)
parts.append(("DrainValve", drain_valve))

drain_pipe = make_cyl(10, 60, "DrainPipe")
drain_pipe.color = (0.81, 0.85, 0.86, 1.0)
parts.append(("DrainPipe", drain_pipe))

# 25. PT100探头
probe = make_cyl(6, 80, "PT100_Probe")
probe.color = (0.82, 0.18, 0.18, 1.0)
parts.append(("Probe", probe))

# ============================================================
# 导出独立 STEP
# ============================================================
print("=" * 60)
print("商用烟熏腊肉香肠炉 — build123d CAD 模型")
print("=" * 60)
print(f"\n导出 {len(parts)} 个零件到 STEP...\n")

for name, part in parts:
    path = os.path.join(OUTPUT_DIR, f"smokehouse_{name}.step")
    try:
        part.export_step(path)
        print(f"  [{part.label}] -> {name}.step")
    except Exception as e:
        print(f"  [{name}] FAILED: {e}")

# ============================================================
# 装配体 STEP
# ============================================================
print(f"\n生成装配体...")

assembly = []

# 外箱
outer = make_box(BOX_W, BOX_D, BOX_H, "OuterShell")
outer.location = Location((0, 0, WHEEL_OFFSET))
outer.color = (0.47, 0.56, 0.61, 0.4)
assembly.append(outer)

# 保温层
ins = make_box(BOX_W-OUTER_T*2, BOX_D-OUTER_T*2, BOX_H-OUTER_T*2, "Insulation")
ins.location = Location((0, 0, OUTER_T + WHEEL_OFFSET))
ins.color = (0.98, 0.54, 0.40, 0.3)
assembly.append(ins)

# 内胆
inn = make_box(INNER_W, INNER_D, INNER_H, "InnerChamber")
inn.location = Location((0, 0, INS + WHEEL_OFFSET))
inn.color = (0.69, 0.75, 0.77, 1.0)
assembly.append(inn)

# 门 (位于前面，半开)
for door_idx, dx in enumerate([-DOOR_W/2, DOOR_W/2]):
    door = make_box(DOOR_W-4, 20, DOOR_H-4, f"Door_{door_idx+1}")
    door.location = Location((dx, BOX_D/2+15, WHEEL_OFFSET+20+DOOR_H/2))
    door.color = (0.55, 0.62, 0.66, 0.6)
    assembly.append(door)

# 4层挂架 (内部)
for i in range(RACK_LAYERS):
    ry = RACK_START + i * RACK_SPACING
    rack = make_box(INNER_W-20, INNER_D-20, 25, f"Rack_L{i+1}")
    rack.location = Location((0, 0, WHEEL_OFFSET + INS + ry))
    rack.color = (1.0, 0.84, 0.31, 1.0)
    assembly.append(rack)

# 加热管 (内部底部)
for idx, side in enumerate([-1, 1]):
    hx = (INNER_W * 0.38) * side
    ht = make_cyl(HEATER_DIA/2, HEATER_LEN, f"Heater_{idx+1}")
    ht.location = Location((hx, 0, WHEEL_OFFSET + INS + 100))
    ht.color = (1.0, 0.60, 0.0, 1.0)
    assembly.append(ht)

# 风机 (背面内部)
fan = make_cyl(FAN_DIA/2, FAN_DEPTH, "Fan")
fan.location = Location((0, -INNER_D/2 + FAN_DEPTH/2, WHEEL_OFFSET + BOX_H - INS - 400))
fan.color = (0.08, 0.34, 0.75, 1.0)
assembly.append(fan)

# 集油盘 (内部底部)
tray = make_box(INNER_W-10, INNER_D-10, 15, "OilTray")
tray.location = Location((0, 0, WHEEL_OFFSET + INS + 25))
tray.color = (0.69, 0.75, 0.77, 1.0)
assembly.append(tray)

# 发烟器 (左侧外部)
sm = make_cyl(SMOKER_DIA/2, SMOKER_H, "SmokeGen")
sm.location = Location((-BOX_W/2 - SMOKER_DIA/2 - 50, 0, WHEEL_OFFSET + 200))
sm.color = (0.91, 0.27, 0.38, 1.0)
assembly.append(sm)

# 烟管 (发烟器到箱体)
sp = make_cyl(PIPE_DN/2, 300, "SmokePipe")
sp.location = Location((-50, 0, WHEEL_OFFSET + 350))
sp.color = (1.0, 0.44, 0.26, 1.0)
assembly.append(sp)

# 排烟管 (顶部)
ch = make_cyl(CHIMNEY_DN/2, CHIMNEY_H, "Chimney")
ch.location = Location((0, 0, WHEEL_OFFSET + BOX_H))
ch.color = (0.38, 0.49, 0.55, 1.0)
assembly.append(ch)

# 水幕过滤箱 (顶部右侧)
fb = make_box(FILTER_W, FILTER_D, FILTER_H, "FilterBox")
fb.location = Location((BOX_W/2 + FILTER_W/2 + 30, 0, WHEEL_OFFSET + BOX_H - FILTER_H/2))
fb.color = (0.13, 0.39, 0.75, 1.0)
assembly.append(fb)

# 控制面板 (右侧)
cp = make_box(CTRL_W, CTRL_D, CTRL_H, "CtrlPanel")
cp.location = Location((BOX_W/2 + CTRL_W/2 + 15, BOX_D/2 + CTRL_D/2 + 5, WHEEL_OFFSET + BOX_H * 0.55))
cp.color = (0.30, 0.69, 0.31, 1.0)
assembly.append(cp)

# 万向轮
for wx, wz in [(-BOX_W/2+150, -BOX_D/2+100), (-BOX_W/2+150, BOX_D/2-100),
               (BOX_W/2-150, -BOX_D/2+100), (BOX_W/2-150, BOX_D/2-100)]:
    w = make_cyl(WHEEL_DIA/2, 30, "Wheel")
    w.location = Location((wx, wz, WHEEL_DIA/2))
    w.color = (0.22, 0.28, 0.31, 1.0)
    assembly.append(w)

# 导出装配体
asm_path = os.path.join(OUTPUT_DIR, "smokehouse_assembly.step")
try:
    bd.export_step(assembly, asm_path)
    print(f"  Assembly STEP: {asm_path}")
    print(f"  Parts in assembly: {len(assembly)}")
except Exception as e:
    print(f"  Assembly FAILED: {e}")

print(f"\n{'='*60}")
print(f"Done. Files: {OUTPUT_DIR}")
print(f"{'='*60}")
