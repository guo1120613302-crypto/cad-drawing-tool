# Bugfix Requirements Document

## Introduction

修复多段线工具中圆弧段的位置、方向和形状计算错误。当用户在多段线绘制过程中按 'A' 键切换到圆弧模式后，生成的圆弧段与 CAD 标准行为不符，表现为圆弧位置偏移、弯曲方向错误、以及曲率和半径计算不准确。此 bug 影响用户绘制符合 CAD 标准的多段线图形。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN 用户在多段线绘制中切换到圆弧模式并移动鼠标时 THEN 圆弧的起始位置不在前一段的端点上

1.2 WHEN 用户在多段线绘制中切换到圆弧模式并移动鼠标时 THEN 圆弧的起始切线方向与前一段的终止方向不一致

1.3 WHEN 用户在多段线绘制中绘制圆弧段时 THEN 圆弧的弯曲方向（顺时针/逆时针）与鼠标位置的关系不符合 CAD 标准

1.4 WHEN 用户在多段线绘制中绘制圆弧段时 THEN 圆弧的半径和曲率计算错误，导致圆弧形状不正确

1.5 WHEN 用户在多段线绘制中绘制标准 90 度圆弧时 THEN 生成的圆弧角度不是 90 度，且半径值不正确

### Expected Behavior (Correct)

2.1 WHEN 用户在多段线绘制中切换到圆弧模式并移动鼠标时 THEN 圆弧 SHALL 从前一段的端点开始绘制

2.2 WHEN 用户在多段线绘制中切换到圆弧模式并移动鼠标时 THEN 圆弧的起始切线方向 SHALL 与前一段的终止方向保持一致（切线连续）

2.3 WHEN 用户在多段线绘制中绘制圆弧段时 THEN 圆弧的弯曲方向 SHALL 根据鼠标相对于前一段切线的位置确定（鼠标在切线左侧=逆时针，右侧=顺时针）

2.4 WHEN 用户在多段线绘制中绘制圆弧段时 THEN 圆弧的半径和曲率 SHALL 根据起点、终点和切线约束正确计算

2.5 WHEN 用户在多段线绘制中绘制标准 90 度圆弧时 THEN 生成的圆弧 SHALL 是精确的 90 度圆弧，半径值符合几何计算

2.6 WHEN 用户在多段线绘制中绘制圆弧段并点击确认时 THEN bulge 值 SHALL 正确存储并用于后续渲染

### Unchanged Behavior (Regression Prevention)

3.1 WHEN 用户在多段线绘制中使用直线模式（未按 'A' 键）时 THEN 系统 SHALL CONTINUE TO 正确绘制直线段

3.2 WHEN 用户在多段线绘制中输入距离、角度等数值时 THEN 系统 SHALL CONTINUE TO 正确处理键盘输入

3.3 WHEN 用户在多段线绘制中使用捕捉功能时 THEN 系统 SHALL CONTINUE TO 正确捕捉到目标点

3.4 WHEN 用户完成多段线绘制后 THEN 系统 SHALL CONTINUE TO 正确保存和渲染已确认的直线段

3.5 WHEN 用户在多段线绘制中按 'L' 键切换回直线模式时 THEN 系统 SHALL CONTINUE TO 正确切换模式

3.6 WHEN 用户在多段线绘制中按 Esc 或右键结束绘制时 THEN 系统 SHALL CONTINUE TO 正确完成或取消多段线
