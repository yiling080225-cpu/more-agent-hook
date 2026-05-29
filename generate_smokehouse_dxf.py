#!/usr/bin/env python3
"""
商用烟熏腊肉香肠炉 — DXF 工程三视图生成脚本
输出：preview/smokehouse_3view.dxf — 可直接用中望CAD打开
"""

import ezdxf
from ezdxf import units
from ezdxf.enums import TextEntityAlignment
import math
import os

# ============================================================
# 全局参数 (mm)
# ============================================================
BOX_W = 1200
BOX_D = 800
BOX_H = 1800
INSULATION = 50
INNER_W = BOX_W - 2 * INSULATION
INNER_D = BOX_D - 2 * INSULATION
INNER_H = 1400
WHEEL_R = 65
WHEEL_H = 120

# 视图偏移
FRONT_ORG = (0, 0)
SIDE_ORG = (1800, 0)
TOP_ORG = (0, 2400)
SMOKEGEN_ORG = (1800, 2400)
TITLE_ORG = (3500, 2400)

# 颜色
COL_OUTLINE = 7
COL_HIDDEN = 8
COL_DIM = 1
COL_TEXT = 4
COL_CENTER = 1
COL_HATCH = 8
COL_SMOKE = 5
COL_HEAT = 2
COL_CTRL = 3
COL_ENV = 130
COL_TITLE = 7

# ============================================================
# 创建 DXF 文档
# ============================================================
doc = ezdxf.new(setup=True, units=units.MM)
doc.header['$INSUNITS'] = 4
doc.header['$DWGCODEPAGE'] = 'ANSI_936'
msp = doc.modelspace()

# ---- 图层 ----
doc.layers.add('OUTLINE', dxfattribs={'color': COL_OUTLINE, 'lineweight': 50})
doc.layers.add('THIN', dxfattribs={'color': COL_OUTLINE, 'lineweight': 18})
doc.layers.add('HIDDEN', dxfattribs={'color': COL_HIDDEN, 'linetype': 'DASHED', 'lineweight': 18})
doc.layers.add('DIMENSIONS', dxfattribs={'color': COL_DIM, 'lineweight': 18})
doc.layers.add('TEXT', dxfattribs={'color': COL_TEXT, 'lineweight': 18})
doc.layers.add('CENTER', dxfattribs={'color': COL_CENTER, 'linetype': 'CENTER', 'lineweight': 18})
doc.layers.add('HATCH', dxfattribs={'color': COL_HATCH, 'lineweight': 13})
doc.layers.add('SMOKE_FLOW', dxfattribs={'color': COL_SMOKE, 'lineweight': 30})
doc.layers.add('HEATING', dxfattribs={'color': COL_HEAT, 'linetype': 'DASHED2', 'lineweight': 25})
doc.layers.add('CONTROL', dxfattribs={'color': COL_CTRL, 'lineweight': 25})
doc.layers.add('ENVIRONMENT', dxfattribs={'color': COL_ENV, 'lineweight': 25})
doc.layers.add('TITLE', dxfattribs={'color': COL_TITLE, 'lineweight': 35})

# ---- 文字样式 ----
try:
    doc.styles.add('CN', dxfattribs={'font': 'simhei.ttf', 'last_height': 3.5})
except Exception:
    try:
        doc.styles.add('CN', dxfattribs={'font': 'simsun.ttf', 'last_height': 3.5})
    except Exception:
        pass

# ============================================================
# 辅助函数
# ============================================================
def add_rect(x, y, w, h, layer='OUTLINE'):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': layer})

def add_line(x1, y1, x2, y2, layer='THIN'):
    msp.add_line((x1, y1), (x2, y2), dxfattribs={'layer': layer})

def add_text(x, y, content, h=3.5, layer='TEXT', align=None):
    """align 使用 TextEntityAlignment 枚举值"""
    attribs = {'layer': layer, 'style': 'CN', 'height': h}
    t = msp.add_text(content, dxfattribs=attribs)
    if align is not None:
        t.set_placement((x, y), align=align)
    else:
        t.set_placement((x, y))
    return t

def dim_horiz(x1, y1, x2, y2, offset_y, layer='DIMENSIONS'):
    """水平尺寸标注"""
    dl_y = offset_y
    add_line(x1, y1, x1, dl_y, layer)
    add_line(x2, y2, x2, dl_y, layer)
    add_line(x1, dl_y, x2, dl_y, layer)
    # 箭头
    s = 4
    msp.add_line((x1, dl_y), (x1 + s, dl_y - s / 2), dxfattribs={'layer': layer})
    msp.add_line((x1, dl_y), (x1 + s, dl_y + s / 2), dxfattribs={'layer': layer})
    msp.add_line((x2, dl_y), (x2 - s, dl_y - s / 2), dxfattribs={'layer': layer})
    msp.add_line((x2, dl_y), (x2 - s, dl_y + s / 2), dxfattribs={'layer': layer})
    val = abs(x2 - x1) if abs(x2 - x1) > 0 else abs(y2 - y1)
    add_text((x1 + x2) / 2, dl_y + 5, str(val), h=3, layer=layer)
    return val

def dim_vert(x, y1, y2, offset_x, layer='DIMENSIONS'):
    """垂直尺寸标注"""
    dl_x = offset_x
    add_line(x, y1, dl_x, y1, layer)
    add_line(x, y2, dl_x, y2, layer)
    add_line(dl_x, y1, dl_x, y2, layer)
    s = 4
    msp.add_line((dl_x, y1), (dl_x - s / 2, y1 + s), dxfattribs={'layer': layer})
    msp.add_line((dl_x, y1), (dl_x + s / 2, y1 + s), dxfattribs={'layer': layer})
    msp.add_line((dl_x, y2), (dl_x - s / 2, y2 - s), dxfattribs={'layer': layer})
    msp.add_line((dl_x, y2), (dl_x + s / 2, y2 - s), dxfattribs={'layer': layer})
    val = abs(y2 - y1)
    add_text(dl_x - 5, (y1 + y2) / 2, str(val), h=3, layer=layer)
    return val

def add_arrow(x1, y1, x2, y2, layer='SMOKE_FLOW'):
    msp.add_line((x1, y1), (x2, y2), dxfattribs={'layer': layer})
    angle = math.atan2(y2 - y1, x2 - x1)
    al = 10
    aa = math.radians(25)
    msp.add_line((x2, y2), (x2 - al * math.cos(angle - aa), y2 - al * math.sin(angle - aa)), dxfattribs={'layer': layer})
    msp.add_line((x2, y2), (x2 - al * math.cos(angle + aa), y2 - al * math.sin(angle + aa)), dxfattribs={'layer': layer})

def add_circle(x, y, r, layer='THIN'):
    msp.add_circle((x, y), r, dxfattribs={'layer': layer})

def add_hatch(x, y, w, h, layer='HATCH', pattern='ANSI31', scale=15):
    hatch = msp.add_hatch(dxfattribs={'layer': layer, 'color': COL_HATCH})
    hatch.set_pattern_fill(pattern, scale=scale)
    hatch.paths.add_polyline_path([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], is_closed=True)

def add_leader(x, y, tx, ty, label, layer='TEXT'):
    add_line(x, y, tx, ty, 'THIN')
    msp.add_line((tx, ty), (tx + 15, ty), dxfattribs={'layer': 'THIN'})
    add_text(tx + 17, ty - 2, label, h=3.5, layer=layer)

# ============================================================
# 1. 正视图 FRONT VIEW
# ============================================================
ox, oy = FRONT_ORG

# 箱体外轮廓
add_rect(ox, oy + WHEEL_H, BOX_W, BOX_H, 'OUTLINE')

# 双开门
door_gap = 6
door_w = (BOX_W - door_gap) / 2
door_h = BOX_H - 40
door_y = oy + WHEEL_H + 20
add_rect(ox + 4, door_y, door_w - 7, door_h, 'THIN')
add_rect(ox + door_w + 3, door_y, door_w - 7, door_h, 'THIN')
add_line(ox + door_w, door_y + 20, ox + door_w, door_y + door_h - 20, 'CENTER')

# 把手
hy = door_y + door_h * 0.55
hw = 60
add_line(ox + door_w - hw - 15, hy, ox + door_w - 15, hy, 'THIN')
add_line(ox + door_w + 3 + 15, hy, ox + door_w + 3 + 15 + hw, hy, 'THIN')

# 观察窗
ww = 200
wh = 150
wy = door_y + door_h * 0.6
wxl = ox + door_w / 2 - ww / 2
wxr = ox + door_w + door_w / 2 - ww / 2
add_rect(wxl, wy, ww, wh, 'HIDDEN')
add_rect(wxr, wy, ww, wh, 'HIDDEN')
add_text(wxl + ww / 2, wy + wh / 2 - 3, '观察窗', h=3, align=TextEntityAlignment.MIDDLE_CENTER)
add_text(wxr + ww / 2, wy + wh / 2 - 3, '观察窗', h=3, align=TextEntityAlignment.MIDDLE_CENTER)

# 控制面板
cw = 180
ch = 300
cx = ox + BOX_W + 15
cy = oy + WHEEL_H + BOX_H * 0.5
add_rect(cx, cy, cw, ch, 'CONTROL')
add_text(cx + cw / 2, cy + ch - 15, '控制面板', h=4, layer='CONTROL', align=TextEntityAlignment.MIDDLE_CENTER)

# PID
py = cy + ch - 50
add_text(cx + cw / 2, py, 'PID温控器', h=3, layer='CONTROL', align=TextEntityAlignment.MIDDLE_CENTER)
add_rect(cx + 20, py - 25, cw - 40, 20, 'CONTROL')
# 定时器
ty = py - 45
add_text(cx + cw / 2, ty, '定时器', h=3, layer='CONTROL', align=TextEntityAlignment.MIDDLE_CENTER)
add_rect(cx + 20, ty - 25, cw - 40, 20, 'CONTROL')
# 指示灯
iy = ty - 45
for i, lb in enumerate(['电源', '加热', '风机']):
    ix = cx + 25 + i * 55
    add_circle(ix, iy, 8, 'CONTROL')
    add_text(ix, iy - 15, lb, h=2.5, layer='CONTROL', align=TextEntityAlignment.MIDDLE_CENTER)
# 急停
add_circle(cx + cw / 2, iy - 35, 14, 'CONTROL')
add_text(cx + cw / 2, iy - 52, '急停', h=2.5, layer='CONTROL', align=TextEntityAlignment.MIDDLE_CENTER)

# 排烟管
cr = 40
ctop = oy + WHEEL_H + BOX_H + 10
cpx = ox + BOX_W / 2
add_line(cpx - cr, ctop, cpx - cr, ctop + 300, 'OUTLINE')
add_line(cpx + cr, ctop, cpx + cr, ctop + 300, 'OUTLINE')
vy = ctop + 150
add_line(cpx - cr - 15, vy, cpx + cr + 15, vy, 'THIN')
add_text(cpx + cr + 25, vy, 'DN80蝶阀', h=3)

# 水幕过滤箱
env_bx = cpx + cr + 60
env_by = ctop + 80
add_rect(env_bx, env_by, 300, 200, 'ENVIRONMENT')
add_text(env_bx + 150, env_by + 210, '水幕过滤箱', h=4, layer='ENVIRONMENT', align=TextEntityAlignment.MIDDLE_CENTER)
add_text(env_bx + 150, env_by + 180, '(三级水洗+活性炭)', h=3, layer='ENVIRONMENT', align=TextEntityAlignment.MIDDLE_CENTER)
add_arrow(cpx + cr + 30, vy, env_bx - 5, vy, 'SMOKE_FLOW')
# 净化排放
clean_y = env_by + 100
add_arrow(env_bx + 300, clean_y, env_bx + 400, clean_y + 200, 'ENVIRONMENT')
add_text(env_bx + 350, clean_y - 20, '净化排放', h=3, layer='ENVIRONMENT')

# 外置发烟器
sgx = ox - 400
sgy = oy + WHEEL_H + 200
add_rect(sgx, sgy, 350, 500, 'THIN')
add_text(sgx + 175, sgy + 520, '外置发烟器', h=4, align=TextEntityAlignment.MIDDLE_CENTER)
add_text(sgx + 175, sgy + 490, '(304不锈钢/5L)', h=3, align=TextEntityAlignment.MIDDLE_CENTER)
sp_y = sgy + 400
add_arrow(sgx + 355, sp_y, ox - 5, sp_y, 'SMOKE_FLOW')
add_text(sgx + 350 + (ox - sgx - 350) / 2, sp_y + 12, 'DN50烟管', h=3, layer='SMOKE_FLOW', align=TextEntityAlignment.MIDDLE_CENTER)
# 发烟器内部
add_rect(sgx + 50, sgy + 50, 250, 250, 'HIDDEN')
add_text(sgx + 175, sgy + 180, '木屑料斗', h=3, align=TextEntityAlignment.MIDDLE_CENTER)
add_text(sgx + 175, sgy + 130, '1kW电热板', h=3, align=TextEntityAlignment.MIDDLE_CENTER)
add_circle(sgx + 175, sgy + 380, 15, 'THIN')
add_text(sgx + 175, sgy + 405, '进风口', h=2.5, align=TextEntityAlignment.MIDDLE_CENTER)

# 万向轮
for wx in [ox + 100, ox + BOX_W - 100]:
    add_circle(wx, oy + WHEEL_R, WHEEL_R, 'THIN')
    if wx == ox + 100:
        add_line(wx - WHEEL_R - 5, oy + WHEEL_R - 15, wx - WHEEL_R - 5, oy + WHEEL_R + 15, 'THIN')
        add_text(wx - WHEEL_R - 5, oy + WHEEL_R - 22, '刹', h=2.5, align=TextEntityAlignment.MIDDLE_CENTER)

# 排污阀
dx = ox + BOX_W / 2
dy = oy + WHEEL_H - 30
add_line(dx, dy, dx, dy - 40, 'THIN')
add_circle(dx, dy - 48, 10, 'THIN')
add_text(dx + 20, dy - 48, '1/2"排污阀', h=3)

# 正面尺寸
dim_horiz(ox, oy - 10, ox + BOX_W, oy - 10, oy - 30)
dim_vert(ox - 15, oy + WHEEL_H, oy + WHEEL_H + BOX_H, ox - 55)
dim_horiz(ox + 4, door_y + door_h + 15, ox + door_w - 7, door_y + door_h + 15, door_y + door_h + 40)
dim_horiz(wxl, wy - 10, wxl + ww, wy - 10, wy - 30)
dim_vert(ox + BOX_W + 25, oy, oy + WHEEL_H + BOX_H + 300, ox + BOX_W + 75)
dim_horiz(cx, cy + ch + 10, cx + cw, cy + ch + 10, cy + ch + 35)
dim_vert(cx + cw + 15, cy, cy + ch, cx + cw + 50)

add_text(ox + BOX_W / 2, oy + WHEEL_H + BOX_H + 340, '正视图（主视图）', h=6, align=TextEntityAlignment.MIDDLE_CENTER)
add_text(ox + BOX_W + 20, oy - 50, '单位: mm', h=3.5)

# ============================================================
# 2. 侧剖视图 SIDE SECTION VIEW
# ============================================================
sx, sy = SIDE_ORG

add_rect(sx, sy + WHEEL_H, BOX_D, BOX_H, 'OUTLINE')

# 保温层剖面填充
add_hatch(sx, sy + WHEEL_H, INSULATION, BOX_H)
add_hatch(sx + BOX_D - INSULATION, sy + WHEEL_H, INSULATION, BOX_H)
add_hatch(sx, sy + WHEEL_H + BOX_H - INSULATION, BOX_D, INSULATION)
add_hatch(sx, sy + WHEEL_H, BOX_D, INSULATION)

add_text(sx + INSULATION / 2, sy + WHEEL_H + BOX_H / 2, '岩棉保温50mm', h=3, align=TextEntityAlignment.MIDDLE_CENTER)

# 内胆
add_rect(sx + INSULATION, sy + WHEEL_H + INSULATION, BOX_D - 2 * INSULATION, BOX_H - 2 * INSULATION, 'THIN')

# 4层挂架
rack_y_list = []
for i in range(4):
    ry = sy + WHEEL_H + INSULATION + 250 + i * 350
    add_line(sx + INSULATION, ry, sx + BOX_D - INSULATION, ry, 'THIN')
    add_line(sx + INSULATION + 20, ry, sx + INSULATION + 20, ry - 25, 'THIN')
    add_line(sx + BOX_D - INSULATION - 20, ry, sx + BOX_D - INSULATION - 20, ry - 25, 'THIN')
    add_text(sx + INSULATION + 35, ry + 4, f'挂架层{i+1}', h=2.5)
    rack_y_list.append(ry)

# 顶部挂轨
rail_y = sy + WHEEL_H + BOX_H - INSULATION - 80
add_line(sx + INSULATION + 20, rail_y, sx + BOX_D - INSULATION - 20, rail_y, 'OUTLINE')
for hi in range(6):
    hx = sx + INSULATION + 80 + hi * 100
    if hx < sx + BOX_D - INSULATION - 50:
        add_line(hx, rail_y, hx, rail_y - 30, 'THIN')
        add_circle(hx, rail_y - 35, 5, 'THIN')

# 电加热管
heater_y = sy + WHEEL_H + INSULATION + 100
for hx_off in [sx + INSULATION + 80, sx + BOX_D - INSULATION - 80]:
    add_circle(hx_off, heater_y, 18, 'HEATING')
    add_circle(hx_off, heater_y, 8, 'HEATING')
add_line(sx + INSULATION + 100, heater_y, sx + INSULATION + 250, heater_y, 'HEATING')
add_line(sx + BOX_D - INSULATION - 250, heater_y, sx + BOX_D - INSULATION - 100, heater_y, 'HEATING')
# 防护罩
add_line(sx + INSULATION + 40, heater_y - 30, sx + INSULATION + 280, heater_y - 30, 'THIN')
add_line(sx + BOX_D - INSULATION - 280, heater_y - 30, sx + BOX_D - INSULATION - 40, heater_y - 30, 'THIN')
add_leader(sx + INSULATION + 150, heater_y + 25, sx - 50, heater_y + 40, 'U型加热管 3kWx2', 'HEATING')

# 循环风机
fan_x = sx + BOX_D - INSULATION - 30
fan_y = sy + WHEEL_H + BOX_H - INSULATION - 400
add_circle(fan_x, fan_y, 35, 'THIN')
add_circle(fan_x, fan_y, 10, 'THIN')
for ang in [0, 120, 240]:
    rad = math.radians(ang)
    add_line(fan_x, fan_y, fan_x + 30 * math.cos(rad), fan_y + 30 * math.sin(rad), 'THIN')
add_text(fan_x + 45, fan_y + 8, '循环风机60W', h=3)

# 气流箭头
airs = [
    (sx + INSULATION + 100, heater_y + 80),
    (sx + INSULATION + 100, rail_y - 100),
    (sx + INSULATION + 300, rail_y - 100),
    (fan_x - 40, fan_y),
    (sx + INSULATION + 300, heater_y + 80),
    (sx + INSULATION + 150, heater_y + 80),
]
for i in range(len(airs) - 1):
    add_arrow(airs[i][0], airs[i][1], airs[i+1][0], airs[i+1][1], 'SMOKE_FLOW')
add_text(sx + INSULATION + 200, rail_y - 85, '热风循环', h=3, layer='SMOKE_FLOW')

# 进烟口
sin_y = sy + WHEEL_H + INSULATION + 60
sin_x = sx + BOX_D / 2
add_line(sx - 50, sin_y, sx + INSULATION, sin_y, 'SMOKE_FLOW')
add_line(sx - 50, sin_y - 5, sx - 90, sin_y - 80, 'SMOKE_FLOW')
add_arrow(sx - 40, sin_y, sx + INSULATION, sin_y, 'SMOKE_FLOW')
add_text(sx - 60, sin_y + 12, 'DN50进烟', h=3, layer='SMOKE_FLOW')

# 排烟口
ex_x = sx + BOX_D / 2
ex_y = sy + WHEEL_H + BOX_H - INSULATION - 20
add_line(ex_x - 40, ex_y + 40, ex_x - 40, ex_y + 150, 'SMOKE_FLOW')
add_line(ex_x + 40, ex_y + 40, ex_x + 40, ex_y + 150, 'SMOKE_FLOW')
add_arrow(ex_x, ex_y + 60, ex_x, ex_y + 135, 'SMOKE_FLOW')
add_text(ex_x - 80, ex_y + 100, 'DN80排烟', h=3, layer='SMOKE_FLOW')

# 集油盘
ot_y = sy + WHEEL_H + INSULATION + 20
add_line(sx + INSULATION, ot_y, sx + BOX_D - INSULATION, ot_y, 'THIN')
add_line(sx + INSULATION - 10, ot_y, sx + INSULATION, ot_y + 10, 'THIN')
add_line(sx + BOX_D - INSULATION + 10, ot_y, sx + BOX_D - INSULATION, ot_y + 10, 'THIN')
add_text(sx + BOX_D / 2 + 10, ot_y + 4, '304集油盘(可抽拉)', h=2.5)

# 温湿度探头
pb_x = sx + BOX_D / 2
pb_y = sy + WHEEL_H + BOX_H / 2
add_circle(pb_x, pb_y, 8, 'THIN')
add_circle(pb_x, pb_y, 2, 'THIN')
add_leader(pb_x + 8, pb_y + 8, pb_x + 30, pb_y + 30, 'PT100温湿度探头')

# 剖面尺寸
dim_horiz(sx, sy - 10, sx + BOX_D, sy - 10, sy - 35)
dim_vert(sx - 25, sy + WHEEL_H, sy + WHEEL_H + BOX_H, sx - 65)
dim_horiz(sx + INSULATION, sy + WHEEL_H + BOX_H + 20, sx + BOX_D - INSULATION, sy + WHEEL_H + BOX_H + 20, sy + WHEEL_H + BOX_H + 50)
for i in range(3):
    dim_vert(sx + BOX_D + 20, rack_y_list[i], rack_y_list[i+1], sx + BOX_D + 60)
dim_horiz(sx + INSULATION, sy + WHEEL_H + BOX_H + 30, sx, sy + WHEEL_H + BOX_H + 30, sy + WHEEL_H + BOX_H + 70)

add_text(sx + BOX_D / 2, sy + WHEEL_H + BOX_H + 95, '侧剖视图（A-A剖面）', h=6, align=TextEntityAlignment.MIDDLE_CENTER)

# ============================================================
# 3. 俯视图 TOP VIEW
# ============================================================
tx, ty = TOP_ORG

add_rect(tx, ty, BOX_W, BOX_D, 'OUTLINE')
add_rect(tx + INSULATION, ty + INSULATION, BOX_W - 2 * INSULATION, BOX_D - 2 * INSULATION, 'HIDDEN')

# 排烟口
ex_top_x = tx + BOX_W / 2
ex_top_y = ty + BOX_D / 2
add_circle(ex_top_x, ex_top_y, 40, 'OUTLINE')
add_circle(ex_top_x, ex_top_y, 36, 'HIDDEN')
add_text(ex_top_x, ex_top_y - 55, 'DN80排烟口', h=3.5, align=TextEntityAlignment.MIDDLE_CENTER)

# 挂架透视线
for i in range(4):
    by_ = ty + 100 + i * 180
    add_line(tx + INSULATION + 30, by_, tx + BOX_W - INSULATION - 30, by_, 'HIDDEN')
    add_text(tx + INSULATION + 10, by_ + 1, f'挂架{i+1}', h=2)

add_arrow(ex_top_x, ex_top_y + 45, ex_top_x, ex_top_y + 5, 'SMOKE_FLOW')

# 俯视尺寸
dim_horiz(tx, ty - 15, tx + BOX_W, ty - 15, ty - 40)
dim_vert(tx - 15, ty, ty + BOX_D, tx - 55)
dim_horiz(tx + INSULATION, ty + BOX_D + 30, tx + BOX_W - INSULATION, ty + BOX_D + 30, ty + BOX_D + 60)

add_text(tx + BOX_W / 2, ty + BOX_D + 85, '俯视图', h=6, align=TextEntityAlignment.MIDDLE_CENTER)

# ============================================================
# 4. 水幕过滤箱详图
# ============================================================
ex, ey = SMOKEGEN_ORG

add_rect(ex, ey, 300, 400, 'ENVIRONMENT')
add_rect(ex + 10, ey + 10, 280, 380, 'ENVIRONMENT')

levels = ['一级水洗', '二级水洗', '三级水洗']
for idx, lb in enumerate(levels):
    ly = ey + 40 + idx * 110
    add_rect(ex + 20, ly, 260, 90, 'ENVIRONMENT')
    add_text(ex + 150, ly + 55, lb, h=3.5, layer='ENVIRONMENT', align=TextEntityAlignment.MIDDLE_CENTER)
    for spx in [60, 150, 240]:
        add_circle(ex + spx, ly + 75, 8, 'ENVIRONMENT')
    add_line(ex + 20, ly + 20, ex + 280, ly + 20, 'ENVIRONMENT')
    add_text(ex + 140, ly + 28, '= 水位线', h=2, layer='ENVIRONMENT', align=TextEntityAlignment.MIDDLE_CENTER)

# 活性炭
carbon_y = ey + 380
add_rect(ex + 20, carbon_y, 260, 20, 'ENVIRONMENT')
add_hatch(ex + 20, carbon_y, 260, 20, 'HATCH', 'ANSI37', 8)
add_text(ex + 150, carbon_y - 10, '活性炭过滤层', h=3, layer='ENVIRONMENT', align=TextEntityAlignment.MIDDLE_CENTER)

add_arrow(ex - 40, ey + 374, ex, ey + 374, 'SMOKE_FLOW')
add_text(ex - 42, ey + 382, '烟气入口', h=3, layer='SMOKE_FLOW')
add_arrow(ex + 300, ey + 374, ex + 340, ey + 374, 'ENVIRONMENT')
add_text(ex + 302, ey + 382, '净化出口', h=3, layer='ENVIRONMENT')

# 水泵
pump_x = ex + 320
pump_y = ey + 200
add_rect(pump_x, pump_y, 80, 100, 'ENVIRONMENT')
add_circle(pump_x + 40, pump_y + 60, 20, 'ENVIRONMENT')
add_text(pump_x + 40, pump_y + 20, '循环水泵50W', h=3, layer='ENVIRONMENT', align=TextEntityAlignment.MIDDLE_CENTER)
add_line(pump_x, pump_y + 50, ex + 300, pump_y + 50, 'ENVIRONMENT')
add_line(ex + 150, ey + 20, pump_x + 40, pump_y + 100, 'ENVIRONMENT')
add_arrow(ex + 150, ey + 20, pump_x + 40, pump_y + 95, 'ENVIRONMENT')
add_text(pump_x - 28, pump_y + 38, '回水', h=2.5, layer='ENVIRONMENT')

# 废水收集
waste_x = ex + 320
waste_y = ey + 20
add_rect(waste_x, waste_y, 80, 80, 'ENVIRONMENT')
add_text(waste_x + 40, waste_y + 40, '废水收集槽', h=3, layer='ENVIRONMENT', align=TextEntityAlignment.MIDDLE_CENTER)
add_text(waste_x + 40, waste_y + 25, '定期清运', h=2.5, layer='ENVIRONMENT', align=TextEntityAlignment.MIDDLE_CENTER)

add_text(ex + 150, ey + 420, '水幕过滤箱详图（环保系统）', h=5, layer='ENVIRONMENT', align=TextEntityAlignment.MIDDLE_CENTER)

# ============================================================
# 5. 标题栏
# ============================================================
tbx, tby = TITLE_ORG
tb_w = 600
tb_h = 350
add_rect(tbx, tby, tb_w, tb_h, 'TITLE')
for split_y in [tby + tb_h - 50, tby + tb_h - 100, tby + tb_h - 150, tby + tb_h - 200, tby + tb_h - 250]:
    add_line(tbx, split_y, tbx + tb_w, split_y, 'TITLE')
add_line(tbx + 200, tby + tb_h - 250, tbx + 200, tby + tb_h, 'TITLE')
add_line(tbx + 400, tby + tb_h - 200, tbx + 400, tby + tb_h, 'TITLE')

tdata = [
    (tbx + 20, tby + tb_h - 30, '商用烟熏腊肉香肠炉', 5),
    (tbx + 20, tby + tb_h - 80, '设计阶段', 3.5),
    (tbx + 100, tby + tb_h - 80, '方案设计', 3.5),
    (tbx + 20, tby + tb_h - 130, '图纸名称', 3.5),
    (tbx + 100, tby + tb_h - 130, '三视图(正视/侧剖/俯视)', 3.5),
    (tbx + 20, tby + tb_h - 180, '版本', 3.5),
    (tbx + 100, tby + tb_h - 180, 'V1.0 - 含环保水幕过滤', 3.5),
    (tbx + 20, tby + tb_h - 230, '材质', 3.5),
    (tbx + 100, tby + tb_h - 230, '304/201不锈钢', 3.5),
    (tbx + 210, tby + tb_h - 80, '比例', 3.5),
    (tbx + 280, tby + tb_h - 80, '1:1 (模型空间)', 3.5),
    (tbx + 210, tby + tb_h - 130, '单位', 3.5),
    (tbx + 280, tby + tb_h - 130, 'mm (毫米)', 3.5),
    (tbx + 210, tby + tb_h - 180, '图号', 3.5),
    (tbx + 280, tby + tb_h - 180, 'SMK-001', 3.5),
    (tbx + 210, tby + tb_h - 230, '日期', 3.5),
    (tbx + 280, tby + tb_h - 230, '2026-05-29', 3.5),
    (tbx + 410, tby + tb_h - 80, '预算', 3.5),
    (tbx + 480, tby + tb_h - 80, '< 30000 CNY', 3.5),
    (tbx + 410, tby + tb_h - 130, '批次容量', 3.5),
    (tbx + 480, tby + tb_h - 130, '50-80 kg', 3.5),
    (tbx + 410, tby + tb_h - 180, '环保标准', 3.5),
    (tbx + 480, tby + tb_h - 180, 'GB 18483-2001', 3.5),
    (tbx + 410, tby + tb_h - 230, '总功率', 3.5),
    (tbx + 480, tby + tb_h - 230, '7.06 kW (380V)', 3.5),
]
for x, y, content, h in tdata:
    add_text(x, y, content, h=h, layer='TITLE')

# 图例
leg_x = 3600
leg_y = 50
add_rect(leg_x, leg_y, 420, 290, 'TITLE')
add_text(leg_x + 210, leg_y + 270, '图 例', h=5, layer='TITLE', align=TextEntityAlignment.MIDDLE_CENTER)
leg_items = [
    ('OUTLINE', '外轮廓/结构线', 245),
    ('HIDDEN', '隐藏线/透视线', 215),
    ('HATCH', '剖面填充(岩棉/保温)', 185),
    ('SMOKE_FLOW', '烟气流向', 155),
    ('HEATING', '加热元件', 125),
    ('CONTROL', '控制面板/器件', 95),
    ('ENVIRONMENT', '环保设备/水幕过滤', 65),
]
for ln, lb, yy in leg_items:
    add_line(leg_x + 30, leg_y + yy, leg_x + 80, leg_y + yy, ln)
    add_text(leg_x + 90, leg_y + yy - 2, lb, h=3)

# ============================================================
# 保存
# ============================================================
output_dir = r'd:\multimodal_agent_federation_mvp\preview'
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, 'smokehouse_3view.dxf')
doc.saveas(output_path)

print(f'[OK] DXF 工程图已生成: {output_path}')
print(f'     可用中望CAD(ZWCAD)直接打开')
print(f'     包含: 正视图 + 侧剖图(A-A) + 俯视图 + 水幕过滤详图 + 标题栏 + 图例')
print(f'     比例: 1:1 (模型空间, mm)')
print(f'     图层: OUTLINE/HIDDEN/HATCH/SMOKE_FLOW/HEATING/CONTROL/ENVIRONMENT/DIMENSIONS/TEXT')
