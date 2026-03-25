import sys
import io
import re
import math
from collections import Counter


class STPAnalyzerCN:
    def __init__(self, file_path):
        self.file_path = file_path
        self.stats = Counter()
        self.points = {} # id -> (x, y, z)
        self.cylinder_radii = []
        self.faces_with_holes_count = 0
        self.total_face_bounds = 0
        self.products = set() # 存储唯一零件名称
        self.edges = [] # (p1_id, p2_id) 列表用于长度计算
        self.edges_map = {} # edge_id -> (v1_id, v2_id)
        self.edge_senses = {} # edge_id -> bool (True for .T., False for .F.)
        self.vertices = {} # vertex_id -> point_id
        self.edge_geoms = {} # edge_id -> curve_id
        self.surface_curves = {} # surface_curve_id -> curve_3d_id
        self.b_spline_points = {} # curve_id -> [point_ids]
        self.circles = {} # circle_id -> (placement_id, radius)
        self.placements = {} # placement_id -> (point_id, axis_id, ref_dir_id)
        self.directions = {} # dir_id -> (x, y, z)
        self.faces = {} # face_id -> surface_id
        self.planes = {} # plane_id -> placement_id
        self.cylinders = {} # cylinder_id -> (placement_id, radius)
        
        # 正则表达式模式
        self.patterns = {
            'point': re.compile(r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^,]*,\s*\(\s*([-\d\.eE+]+)\s*,\s*([-\d\.eE+]+)\s*,\s*([-\d\.eE+]+)\s*\)\s*\)"),
            'direction': re.compile(r"#(\d+)\s*=\s*DIRECTION\s*\([^,]*,\s*\(\s*([-\d\.eE+]+)\s*,\s*([-\d\.eE+]+)\s*,\s*([-\d\.eE+]+)\s*\)\s*\)"),
            'cylinder': re.compile(r"#(\d+)\s*=\s*CYLINDRICAL_SURFACE\s*\([^,]*,\s*#(\d+)\s*,\s*([-\d\.eE+]+)\s*\)"),
            'advanced_face': re.compile(r"#(\d+)\s*=\s*ADVANCED_FACE\s*\([^,]*,\s*\(([^)]+)\)\s*,\s*#(\d+)"),
            'product': re.compile(r"#(\d+)\s*=\s*PRODUCT\s*\(\s*'([^']*)'"),
            'edge_curve': re.compile(r"#(\d+)\s*=\s*EDGE_CURVE\s*\([^,]*,\s*#(\d+)\s*,\s*#(\d+)\s*,\s*#(\d+)\s*,\s*(\.[TF]\.)"),
            'vertex_point': re.compile(r"#(\d+)\s*=\s*VERTEX_POINT\s*\([^,]*,\s*#(\d+)\s*\)"),
            'surface_curve': re.compile(r"#(\d+)\s*=\s*SURFACE_CURVE\s*\([^,]*,\s*#(\d+)"),
            'b_spline': re.compile(r"#(\d+)\s*=\s*(?:BOUNDED_CURVE\(\)\s*)?B_SPLINE_CURVE(?:_WITH_KNOTS)?\s*\([^,]*,\s*\d+\s*,\s*\((#[^)]+)\)"),
            'circle': re.compile(r"#(\d+)\s*=\s*CIRCLE\s*\([^,]*,\s*#(\d+)\s*,\s*([-\d\.eE+]+)\s*\)"),
            'axis2_placement_3d': re.compile(r"#(\d+)\s*=\s*AXIS2_PLACEMENT_3D\s*\([^,]*,\s*#(\d+)\s*,\s*(#\d+|\$)\s*,\s*(#\d+|\$)\s*\)"),
            'plane': re.compile(r"#(\d+)\s*=\s*PLANE\s*\([^,]*,\s*#(\d+)\s*\)")
        }

    def run(self):
        print(f"============================================================")
        print(f"   STP 几何特征综合分析报告 (中文版)")
        print(f"   文件路径: {self.file_path}")
        print(f"============================================================\n")
        
        self.parse_file()
        self.report_complexity()
        self.report_geometry()
        #self.report_topology()
        #self.report_small_features()
        self.report_boundaries()

    def parse_file(self):
        print("[状态] 正在解析文件结构...")
        current_stmt = []
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    
                    current_stmt.append(line)
                    if not line.endswith(';'):
                        continue
                        
                    # 拼接行以形成完整语句
                    full_line = "".join(current_stmt)
                    current_stmt = [] # 重置缓冲区
                    
                    # 1. 统计实体类型
                    if 'ADVANCED_FACE' in full_line:
                        self.stats['ADVANCED_FACE'] += 1
                        self._analyze_face_complexity(full_line)
                    elif 'CLOSED_SHELL' in full_line:
                        self.stats['CLOSED_SHELL'] += 1
                    elif 'CARTESIAN_POINT' in full_line:
                        self.stats['CARTESIAN_POINT'] += 1
                        self._extract_point(full_line)
                    elif 'DIRECTION' in full_line:
                        self._extract_direction(full_line)
                    elif 'PRODUCT(' in full_line:
                        self._extract_product(full_line)
                    elif 'EDGE_CURVE(' in full_line:
                        self._extract_edge(full_line)
                    elif 'VERTEX_POINT(' in full_line:
                        self._extract_vertex(full_line)
                    elif 'SURFACE_CURVE(' in full_line:
                        self._extract_surface_curve(full_line)
                    elif 'B_SPLINE_CURVE' in full_line:
                        self._extract_b_spline(full_line)
                    elif 'CIRCLE(' in full_line:
                        self._extract_circle(full_line)
                    elif 'AXIS2_PLACEMENT_3D' in full_line:
                        self._extract_axis2_placement_3d(full_line)

                    # 曲面类型
                    if 'PLANE(' in full_line: 
                        self.stats['PLANE'] += 1
                        self._extract_plane(full_line)
                    elif 'CYLINDRICAL_SURFACE' in full_line: 
                        self.stats['CYLINDRICAL_SURFACE'] += 1
                        self._extract_cylinder(full_line)
                    elif 'CONICAL_SURFACE' in full_line: self.stats['CONICAL_SURFACE'] += 1
                    elif 'SPHERICAL_SURFACE' in full_line: self.stats['SPHERICAL_SURFACE'] += 1
                    elif 'TOROIDAL_SURFACE' in full_line: self.stats['TOROIDAL_SURFACE'] += 1
                    elif 'B_SPLINE_SURFACE' in full_line: self.stats['B_SPLINE_SURFACE'] += 1
                    elif 'SURFACE_OF_LINEAR_EXTRUSION' in full_line: self.stats['SURFACE_OF_LINEAR_EXTRUSION'] += 1
                    elif 'SURFACE_OF_REVOLUTION' in full_line: self.stats['SURFACE_OF_REVOLUTION'] += 1

        except Exception as e:
            print(f"[错误] 读取文件失败: {e}")

    def _extract_product(self, line):
        match = self.patterns['product'].search(line)
        if match:
            self.products.add(match.group(2))

    def _extract_edge(self, line):
        match = self.patterns['edge_curve'].search(line)
        if match:
            eid = int(match.group(1))
            v1, v2 = int(match.group(2)), int(match.group(3))
            self.edges.append((v1, v2))
            self.edges_map[eid] = (v1, v2)
            self.edge_geoms[eid] = int(match.group(4))
            self.edge_senses[eid] = (match.group(5) == '.T.')

    def _extract_surface_curve(self, line):
        match = self.patterns['surface_curve'].search(line)
        if match:
            self.surface_curves[int(match.group(1))] = int(match.group(2))

    def _extract_b_spline(self, line):
        match = self.patterns['b_spline'].search(line)
        if match:
            cid = int(match.group(1))
            points_str = match.group(2)
            # points_str looks like "#28,#29,#30"
            pids = [int(p.replace('#', '')) for p in points_str.split(',') if '#' in p]
            self.b_spline_points[cid] = pids

    def _extract_circle(self, line):
        match = self.patterns['circle'].search(line)
        if match:
            cid = int(match.group(1))
            placement_id = int(match.group(2))
            radius = float(match.group(3))
            self.circles[cid] = (placement_id, radius)

    def _extract_axis2_placement_3d(self, line):
        match = self.patterns['axis2_placement_3d'].search(line)
        if match:
            pid = int(match.group(1))
            location_id = int(match.group(2))
            axis_id = match.group(3)
            ref_dir_id = match.group(4)
            
            axis_id = int(axis_id.replace('#', '')) if axis_id != '$' else None
            ref_dir_id = int(ref_dir_id.replace('#', '')) if ref_dir_id != '$' else None
            
            self.placements[pid] = (location_id, axis_id, ref_dir_id)

    def _extract_direction(self, line):
        match = self.patterns['direction'].search(line)
        if match:
            did = int(match.group(1))
            x = float(match.group(2))
            y = float(match.group(3))
            z = float(match.group(4))
            # Normalize direction
            length = math.sqrt(x*x + y*y + z*z)
            if length > 1e-9:
                self.directions[did] = (x/length, y/length, z/length)
            else:
                self.directions[did] = (0, 0, 1) # Default Z

    def _extract_vertex(self, line):
        match = self.patterns['vertex_point'].search(line)
        if match:
            pid = int(match.group(2))
            self.vertices[int(match.group(1))] = pid

    def report_complexity(self):
        print("0. 模型复杂度与结构统计")
        print("-------------------------------")
        print(f"   独立零件数量 (Products) : {len(self.products)}")
        if self.products:
            examples = list(self.products)[:5]
            print(f"   零件名称示例          : {', '.join(examples)}{'...' if len(self.products) > 5 else ''}")
        
        complexity = "低 (Low)"
        if self.stats['ADVANCED_FACE'] > 5000: complexity = "极高 (Very High)"
        elif self.stats['ADVANCED_FACE'] > 1000: complexity = "高 (High)"
        elif self.stats['ADVANCED_FACE'] > 200: complexity = "中 (Medium)"
        
        print(f"   复杂度评级           : {complexity} (共 {self.stats['ADVANCED_FACE']} 个面)")
        print("")

    def report_small_features(self):
        print("5. 仿真前处理预检 (细小特征)")
        print("---------------------------------------")
        small_edges = 0
        for v1_id, v2_id in self.edges:
            p1_id = self.vertices.get(v1_id)
            p2_id = self.vertices.get(v2_id)
            if p1_id in self.points and p2_id in self.points:
                p1 = self.points[p1_id]
                p2 = self.points[p2_id]
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))
                if 0 < dist < 0.1:
                    small_edges += 1
        
        if small_edges > 0:
            print(f"   [!] 警告: 检测到 {small_edges} 条细小边缘 (长度 < 0.1mm)")
            print(f"       这可能会在自动划分网格时导致几何畸变或失败。")
        else:
            print(f"   [OK] 未检测到极小边缘 (< 0.1mm)。")
        print(f"   [注] 面面积分析需要几何内核支持，此处跳过 < 1mm^2 检查。")
        print("")

    def _extract_point(self, line):
        match = self.patterns['point'].search(line)
        if match:
            try:
                pid = int(match.group(1))
                x = float(match.group(2))
                y = float(match.group(3))
                z = float(match.group(4))
                self.points[pid] = (x, y, z)
            except: pass

    def _extract_cylinder(self, line):
        match = self.patterns['cylinder'].search(line)
        if match:
            try:
                cid = int(match.group(1))
                placement_id = int(match.group(2))
                r = float(match.group(3))
                self.cylinder_radii.append(r)
                self.cylinders[cid] = (placement_id, r)
            except: pass

    def _extract_plane(self, line):
        match = self.patterns['plane'].search(line)
        if match:
            try:
                pid = int(match.group(1))
                placement_id = int(match.group(2))
                self.planes[pid] = placement_id
            except: pass

    def _analyze_face_complexity(self, line):
        match = self.patterns['advanced_face'].search(line)
        if match:
            fid = int(match.group(1))
            bounds_str = match.group(2)
            surface_id = int(match.group(3))
            
            self.faces[fid] = surface_id
            
            num_bounds = bounds_str.count('#')
            if num_bounds > 1:
                self.faces_with_holes_count += 1

    def report_geometry(self):
        print(f"[Debug] Edge Geoms: {len(self.edge_geoms)}")
        print(f"[Debug] Surface Curves: {len(self.surface_curves)}")
        print(f"[Debug] B-Spline Points: {len(self.b_spline_points)}")
        
        print("1. 几何尺寸")
        print("-----------------------")
        
        # 1. 基础顶点 (VERTEX_POINT)
        vertex_pids = set(self.vertices.values())
        
        # 2. 曲线控制点 (B-Spline Control Points)
        # 通过 EDGE_CURVE -> (SURFACE_CURVE) -> B_SPLINE_CURVE 链路查找
        curve_pids = set()
        for edge_id, curve_id in self.edge_geoms.items():
            # 解析 curve_id
            target_curve_id = curve_id
            # 如果引用的是 SURFACE_CURVE，则取其 3D 曲线
            if curve_id in self.surface_curves:
                target_curve_id = self.surface_curves[curve_id]
            
            # 如果是 B-Spline，加入其所有控制点
            if target_curve_id in self.b_spline_points:
                curve_pids.update(self.b_spline_points[target_curve_id])

        all_valid_pids = vertex_pids.union(curve_pids)
        
        print(f"[Debug] Vertices: {len(vertex_pids)}, Curve Points: {len(curve_pids)}, Total Unique: {len(all_valid_pids)}")
        
        geo_points = {pid: self.points[pid] for pid in all_valid_pids if pid in self.points}
        
        print(f"[Debug] Points found in self.points: {len(geo_points)}")
        
        if not geo_points and not self.circles:
            # 如果没有找到顶点且没有圆，回退到统计所有点（对于合法的实体模型这种情况很少见）
            geo_points = self.points

        if not geo_points and not self.circles:
            print("   未发现几何点数据。")
            return

        all_coords = list(geo_points.values())
        xs = [p[0] for p in all_coords]
        ys = [p[1] for p in all_coords]
        zs = [p[2] for p in all_coords]
        
        # 3. 处理圆 (CIRCLE) 的边界
        # 圆的边界计算: 检查 0, 90, 180, 270 度点是否在圆弧范围内
        print(f"[Debug] Analyzing edges for curved boundaries...")
        
        # Helper for vector operations
        def vec_sub(v1, v2): return (v1[0]-v2[0], v1[1]-v2[1], v1[2]-v2[2])
        def vec_dot(v1, v2): return v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]
        def vec_cross(v1, v2):
            return (v1[1]*v2[2] - v1[2]*v2[1],
                    v1[2]*v2[0] - v1[0]*v2[2],
                    v1[0]*v2[1] - v1[1]*v2[0])
        def vec_norm(v):
            l = math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
            return (v[0]/l, v[1]/l, v[2]/l) if l > 0 else (0,0,1)

        for edge_id, curve_id in self.edge_geoms.items():
             target_curve_id = curve_id
             if curve_id in self.surface_curves:
                 target_curve_id = self.surface_curves[curve_id]
             
             if target_curve_id in self.circles:
                 # It's a circle!
                 placement_id, radius = self.circles[target_curve_id]
                 if placement_id not in self.placements: continue
                 
                 loc_id, axis_id, ref_dir_id = self.placements[placement_id]
                 if loc_id not in self.points: continue
                 
                 center = self.points[loc_id]
                 axis = (0, 0, 1)
                 if axis_id and axis_id in self.directions:
                     axis = self.directions[axis_id]
                 
                 ref_dir = (1, 0, 0)
                 if ref_dir_id and ref_dir_id in self.directions:
                     ref_dir = self.directions[ref_dir_id]
                 else:
                     # Create orthogonal ref_dir if missing
                     if abs(axis[0]) < 0.9: ref_dir = (1, 0, 0)
                     else: ref_dir = (0, 1, 0)
                     # Orthogonalize
                     proj = vec_dot(ref_dir, axis)
                     ref_dir = vec_sub(ref_dir, (axis[0]*proj, axis[1]*proj, axis[2]*proj))
                     ref_dir = vec_norm(ref_dir)

                 # Local Basis
                 x_loc = ref_dir
                 y_loc = vec_cross(axis, x_loc)
                 
                 # Get Edge Vertices
                 if edge_id not in self.edges_map: continue
                 v1_id, v2_id = self.edges_map[edge_id]
                 
                 p1_id = self.vertices.get(v1_id)
                 p2_id = self.vertices.get(v2_id)
                 
                 if p1_id not in self.points or p2_id not in self.points: continue
                 
                 p1 = self.points[p1_id]
                 p2 = self.points[p2_id]
                 
                 # Calculate Angles
                 def get_angle(p):
                     u = vec_sub(p, center)
                     x_comp = vec_dot(u, x_loc)
                     y_comp = vec_dot(u, y_loc)
                     ang = math.atan2(y_comp, x_comp)
                     if ang < 0: ang += 2*math.pi
                     return ang
                 
                 ang1 = get_angle(p1)
                 ang2 = get_angle(p2)
                 
                 same_sense = self.edge_senses.get(edge_id, True)
                 
                 # Determine Interval [start, end] (CCW)
                 if same_sense:
                     start_ang, end_ang = ang1, ang2
                 else:
                     start_ang, end_ang = ang2, ang1
                     
                 # Check Cardinals (0, PI/2, PI, 3PI/2)
                 cardinals = [0, math.pi/2, math.pi, 3*math.pi/2]
                 
                 for ang in cardinals:
                     in_interval = False
                     if start_ang <= end_ang:
                         if start_ang <= ang <= end_ang: in_interval = True
                     else:
                         if start_ang <= ang <= 2*math.pi or 0 <= ang <= end_ang: in_interval = True
                     
                     if in_interval:
                         # Add Point
                         c_val = math.cos(ang)
                         s_val = math.sin(ang)
                         px = center[0] + radius * (c_val * x_loc[0] + s_val * y_loc[0])
                         py = center[1] + radius * (c_val * x_loc[1] + s_val * y_loc[1])
                         pz = center[2] + radius * (c_val * x_loc[2] + s_val * y_loc[2])
                         
                         xs.append(px)
                         ys.append(py)
                         zs.append(pz)

        if not xs:
             print("   未发现有效几何数据。")
             return

        print(f"[Debug] Pre-filter X range: {min(xs)} - {max(xs)}")
        print(f"[Debug] Pre-filter Y range: {min(ys)} - {max(ys)}")
        print(f"[Debug] Pre-filter Z range: {min(zs)} - {max(zs)}")

        # 离群点过滤逻辑 (使用 IQR 方法)
        def filter_outliers(data):
            if not data: return data
            sorted_data = sorted(data)
            n = len(sorted_data)
            q1 = sorted_data[int(n * 0.25)]
            q3 = sorted_data[int(n * 0.75)]
            iqr = q3 - q1
            lower_bound = q1 - 10 * iqr
            upper_bound = q3 + 10 * iqr
            filtered = [x for x in data if lower_bound <= x <= upper_bound]
            return filtered if filtered else data

        f_xs = filter_outliers(xs)
        f_ys = filter_outliers(ys)
        f_zs = filter_outliers(zs)

        min_x, max_x = min(f_xs), max(f_xs)
        min_y, max_y = min(f_ys), max(f_ys)
        min_z, max_z = min(f_zs), max(f_zs)

        is_filtered = len(f_xs) < len(xs) or len(f_ys) < len(ys) or len(f_zs) < len(zs)

        if is_filtered:
            print(f"   [注] 检测并过滤了离群点 (排除 X:{len(xs)-len(f_xs)}, Y:{len(ys)-len(f_ys)}, Z:{len(zs)-len(f_zs)} 个点)")
            print(f"   外接矩形 X : {min_x:10.4f} 至 {max_x:10.4f} (长度: {max_x - min_x:.4f} mm)")
            print(f"   外接矩形 Y : {min_y:10.4f} 至 {max_y:10.4f} (宽度: {max_y - min_y:.4f} mm)")
            print(f"   外接矩形 Z : {min_z:10.4f} 至 {max_z:10.4f} (高度: {max_z - min_z:.4f} mm)")
        else:
            print(f"   外接矩形 X : {min_x:10.4f} 至 {max_x:10.4f} (长度: {max_x - min_x:.4f} mm)")
            print(f"   外接矩形 Y : {min_y:10.4f} 至 {max_y:10.4f} (宽度: {max_y - min_y:.4f} mm)")
            print(f"   外接矩形 Z : {min_z:10.4f} 至 {max_z:10.4f} (高度: {max_z - min_z:.4f} mm)")
        
        print(f"   对角线长度: {math.sqrt((max_x-min_x)**2 + (max_y-min_y)**2 + (max_z-min_z)**2):.4f} mm")
        self.filtered_bounds = ((min_x, max_x), (min_y, max_y), (min_z, max_z))
        print("")

    def report_topology(self):
        print("2. 拓扑结构与表面类型")
        print("----------------------")
        shells = self.stats['CLOSED_SHELL']
        faces = self.stats['ADVANCED_FACE']
        vertices = len(self.vertices)
        
        print(f"   实体数量 (Shells)    : {shells}")
        
        # --- 几何健康度诊断 (基于用户建议的顶点复用率逻辑) ---
        if faces > 0:
            ratio = vertices / faces
            print(f"   顶点/面比率 (Ratio)  : {ratio:.2f} (V:{vertices} / F:{faces})")
            
            print(f"   [诊断] 几何健康度    : ", end="")
            if ratio > 2.8:
                print("⚠️ 离散曲面 (DISCRETE SURFACES)")
                print(f"          原因: 顶点复用率极低，模型极大概率已“炸开”或由独立面片组成。")
                print(f"          建议: 在仿真前需要进行“几何缝合 (Stitch/Sew)”操作。")
            else:
                if shells == 0:
                    print("🔸 开放壳体 (OPEN SHELL)")
                    print(f"          原因: 顶点有复用但未形成封闭实体。")
                    print(f"          建议: 检查是否存在几何缝隙或未闭合的孔洞。")
                elif shells == 1:
                    print("✅ 单实体 (SOLID SINGLE)")
                    print(f"          状态: 拓扑连接良好，理想的单体分析模型。")
                else:
                    print("🟦 多体实体 (SOLID MULTI-BODY)")
                    print(f"          状态: 包含 {shells} 个独立连通的实体。")
                    if len(self.products) == 1:
                        print(f"          提示: 属于单零件多实体结构，可能包含未合并的内部组件。")
        
        print(f"   总面数 (Faces)       : {faces}")
        pct_holes = (self.faces_with_holes_count / max(1, faces)) * 100
        print(f"   含孔洞面数           : {self.faces_with_holes_count} (占比 {pct_holes:.1f}%)")
        
        if pct_holes > 15:
            print(f"   [!] 提示: 含孔面占比较高，模型可能包含复杂的内部特征或属于薄壁镂空件。")
        print("   表面类型分布:")
        print(f"     - 平面 (Planes)     : {self.stats['PLANE']}")
        print(f"     - 圆柱面 (Cylinders) : {self.stats['CYLINDRICAL_SURFACE']}")
        print(f"     - 自由曲面 (B-Spline): {self.stats['B_SPLINE_SURFACE']}")
        print(f"     - 圆锥面 (Cones)    : {self.stats['CONICAL_SURFACE']}")
        print(f"     - 球面 (Spheres)    : {self.stats['SPHERICAL_SURFACE']}")
        print(f"     - 其他类型          : {self.stats['TOROIDAL_SURFACE'] + self.stats['SURFACE_OF_LINEAR_EXTRUSION'] + self.stats['SURFACE_OF_REVOLUTION']}")
        print("")

    def report_features(self):
        print("3. 制造特征统计 (孔与轴)")
        print("------------------------------------------")
        if not self.cylinder_radii:
            print("   未检测到圆柱特征。")
            return

        max_dim = 1000.0
        min_dim = 10.0
        if hasattr(self, 'filtered_bounds'):
            (min_x, max_x), (min_y, max_y), (min_z, max_z) = self.filtered_bounds
            dims = [max_x - min_x, max_y - min_y, max_z - min_z]
            max_dim = max(dims)
            min_dim = min(dims) if min(dims) > 1.0 else 10.0

        radii_map = Counter()
        for r in self.cylinder_radii:
            r_rounded = round(r, 2)
            radii_map[r_rounded] += 1

        print("   检测到的圆柱特征 (按数量排序):")
        print("   -----------------------------------------------------------------------")
        print("   |  直径 (mm)      |  数量   |  几何分类 (可能性提示)                  |")
        print("   |-----------------|---------|-----------------------------------------|")
        
        sorted_radii = sorted(radii_map.items(), key=lambda x: x[1], reverse=True)
        displayed_count = 0
        skipped_count = 0
        
        for r, count in sorted_radii:
            dia = r * 2
            
            # --- 优化后的过滤逻辑 ---
            # 1. 彻底过滤物理逻辑错误的特征 (直径 > 最大维度)
            if dia > max_dim:
                continue
                
            # 2. 识别并过滤掉外部大圆弧残余 (通常不是孔或轴)
            if dia > max_dim * 0.8:
                continue
            
            # 3. 临界区标记 (直径较大，接近包围盒尺寸)
            is_suspicious_residue = False
            if dia > max_dim * 0.45:
                is_suspicious_residue = True
            
            # 4. 限制显示行数，防止过度解读琐碎特征
            if displayed_count >= 10:
                skipped_count += 1
                continue

            f_type = "普通圆柱几何 (General Cyl)"
            
            # 基于尺寸的启发式判断 (改为更中性的描述)
            if is_suspicious_residue:
                f_type = "大尺寸面 (需警惕是否为外部轮廓)"
            elif dia > min_dim * 2.0:
                f_type = "中大型结构 (可能为轴向主体)"
            elif dia > min_dim * 0.9 and count < 5:
                 f_type = "低频特征 (可能是主轴/定位面)"
            elif count > 100 and dia > 0.5 * max_dim:
                f_type = "高频碎片 (可能是复杂铸造面)"
            elif count > 20 and dia < 100:
                f_type = "阵列特征 (可能是螺栓组/散热孔)"
            elif count == 1:
                f_type = "孤立特征 (可能是非标接口)"
            elif count > 50:
                f_type = "高频阵列 (需关注重复性)"

            print(f"   | {dia:15.2f} | {count:7d} | {f_type:39s} |")
            displayed_count += 1
        
        if skipped_count > 0:
            print(f"   | ...             | ...     | 已省略 {skipped_count} 项次要/琐碎特征           |")
        
        print("\n   [注] 系统已自动合并重复特征，并过滤了直径超过 80% 包围盒跨度的外部轮廓残余。")
        print("")

    def report_boundaries(self):
        """分析所有轴向并报告最可能的几何接口。"""
        print("4. 主轴预测")
        print("-----------------------------------------------------")
        if not self.points:
            print("   未发现用于边界分析的点数据。")
            return

        # 1. 准备并过滤点云数据
        all_coords = list(self.points.values())
        valid_points = all_coords

        if hasattr(self, 'filtered_bounds'):
            bounds = self.filtered_bounds
            (min_x, max_x), (min_y, max_y), (min_z, max_z) = bounds
            # 仅保留在包围盒范围内(稍微放宽容差)的点
            tol = 1.0 
            valid_points = [
                p for p in all_coords 
                if (min_x - tol <= p[0] <= max_x + tol) and
                   (min_y - tol <= p[1] <= max_y + tol) and
                   (min_z - tol <= p[2] <= max_z + tol)
            ]
        else:
            bounds = (
                (min(p[0] for p in all_coords), max(p[0] for p in all_coords)),
                (min(p[1] for p in all_coords), max(p[1] for p in all_coords)),
                (min(p[2] for p in all_coords), max(p[2] for p in all_coords))
            )
            
        if not valid_points:
            print("   [警告] 过滤后无有效点数据，跳过边界分析。")
            return

        def analyze_plane(axis_idx, val, threshold=1.0):
            # axis_idx: 0=X, 1=Y, 2=Z
            pts = [p for p in valid_points if abs(p[axis_idx] - val) < threshold]
            if not pts: return None
            
            # 投影到二维平面进行形状分析
            other_indices = [i for i in range(3) if i != axis_idx]
            coords_2d = [(p[other_indices[0]], p[other_indices[1]]) for p in pts]
            
            u_vals = [p[0] for p in coords_2d]
            v_vals = [p[1] for p in coords_2d]
            cu, cv = sum(u_vals)/len(pts), sum(v_vals)/len(pts)
            
            radii = [math.sqrt((p[0]-cu)**2 + (p[1]-cv)**2) for p in coords_2d]
            avg_r = sum(radii)/len(radii) if radii else 0
            rounded_radii = [round(r) for r in radii]
            most_common_r, freq = Counter(rounded_radii).most_common(1)[0] if rounded_radii else (0,0)
            circularity_ratio = freq / len(pts)
            std_dev = math.sqrt(sum((r - avg_r)**2 for r in radii)/len(radii)) if len(radii) > 1 else 0
            
            span_u = max(u_vals) - min(u_vals)
            span_v = max(v_vals) - min(v_vals)
            max_span = max(span_u, span_v)
            tol = max(0.01, max_span * 0.001)
            
            shape = "复杂/不规则 (Complex/Irregular)"
            score = 10 # 基础分
            
            if len(pts) < 3:
                shape = "单点/顶点/稀疏 (Single Point/Vertex/Sparse)"
                score = 5
            elif (std_dev < 0.05 * avg_r and avg_r > tol) or (circularity_ratio > 0.6 and most_common_r > tol):
                shape = "圆环/接口 (Circular Ring/Interface)"
                score = 90
                if circularity_ratio < 0.9: shape += " (带有加筋肋/不对称性)"
            elif span_u < tol and span_v < tol:
                shape = "点/小型支撑 (Point/Small Support)"
                score = 20
            elif abs(span_u - span_v) < tol:
                shape = "对称框架 (类正方形/Symmetric Frame)"
                score = 80
            elif span_u > tol and span_v > tol:
                shape = "矩形接口/板 (Rectangular Interface)"
                score = 70
            
            # 点云密度加分
            if len(pts) > 20: score += 10
            
            return {
                'axis': ['X', 'Y', 'Z'][axis_idx],
                'val': val,
                'count': len(pts),
                'span': (span_u, span_v),
                'center': (cu, cv),
                'shape': shape,
                'score': score,
                'radius': most_common_r if circularity_ratio > 0.6 else avg_r
            }

        # 1. 扫描所有 6 个极限面
        results = []
        for i, axis in enumerate(['X', 'Y', 'Z']):
            # 每个轴向检查最小和最大边界
            for val in [bounds[i][0], bounds[i][1]]:
                res = analyze_plane(i, val)
                if res:
                    # 纯几何启发式过滤：
                    # 1. 如果点数太少（< 10），通常只是几何极值点而非接口
                    if res['count'] < 10:
                        res['score'] -= 50
                    
                    # 2. 点云密度加分（如果该平面上的点非常多，说明是一个显著特征面）
                    if res['count'] > 50:
                        res['score'] += 20
                    
                    # 确保评分不溢出
                    res['score'] = max(0, min(100, res['score']))
                        
                    results.append(res)

        # 2. 排序并过滤低分项
        results = [r for r in results if r['score'] > 40]
        results.sort(key=lambda x: x['score'], reverse=True)

        if not results:
            print("   未发现明显的平面或圆环接口。模型可能具有全曲面边界。")
            return

        axis_index = {"X": 0, "Y": 1, "Z": 2}
        spans = {
            "X": bounds[0][1] - bounds[0][0],
            "Y": bounds[1][1] - bounds[1][0],
            "Z": bounds[2][1] - bounds[2][0],
        }
        max_span = max(spans.values()) if spans else 1.0

        axis_end_scores = {
            "X": {"min": 0, "max": 0},
            "Y": {"min": 0, "max": 0},
            "Z": {"min": 0, "max": 0},
        }
        end_tol = 1.5
        for r in results:
            axis = r.get("axis")
            if axis not in axis_index:
                continue
            idx = axis_index[axis]
            if abs(r.get("val", 0) - bounds[idx][0]) <= end_tol:
                axis_end_scores[axis]["min"] = max(axis_end_scores[axis]["min"], r.get("score", 0))
            if abs(r.get("val", 0) - bounds[idx][1]) <= end_tol:
                axis_end_scores[axis]["max"] = max(axis_end_scores[axis]["max"], r.get("score", 0))

        axis_scores = {}
        for axis in ["X", "Y", "Z"]:
            bbox_component = (spans.get(axis, 0) / max_span) * 100.0 if max_span > 1e-9 else 0.0
            a_min = axis_end_scores[axis]["min"]
            a_max = axis_end_scores[axis]["max"]
            if a_min > 0 and a_max > 0:
                interface_component = (a_min + a_max) / 2.0
            else:
                interface_component = max(a_min, a_max) * 0.5
            axis_scores[axis] = 0.55 * bbox_component + 0.45 * interface_component

        main_axis = max(axis_scores.items(), key=lambda x: x[1])[0] if axis_scores else "Z"
        main_min = axis_end_scores[main_axis]["min"]
        main_max = axis_end_scores[main_axis]["max"]
        if main_min >= 80 and main_max >= 80:
            confidence = "高"
        elif main_min > 0 or main_max > 0:
            confidence = "中"
        else:
            confidence = "低"

        print(f"   主轴判定: {main_axis}轴 (置信度: {confidence})")
        print(f"       - 包围盒跨度: X={spans['X']:.2f}mm, Y={spans['Y']:.2f}mm, Z={spans['Z']:.2f}mm")
        if axis_end_scores[main_axis]["min"] > 0 or axis_end_scores[main_axis]["max"] > 0:
            print(f"       - 端面接口证据: {main_axis}_min={main_min}/100, {main_axis}_max={main_max}/100 (阈值±{end_tol}mm)")
        print("")

    def report_geometric_relations(self):
        print("6. 几何关系与加工特征分析")
        print("---------------------------------------")
        
        # 1. 主加工方向分析 (基于平面法向量)
        normal_groups = Counter()
        
        for fid, sid in self.faces.items():
            if sid in self.planes:
                pid = self.planes[sid]
                if pid in self.placements:
                    _, axis_id, _ = self.placements[pid]
                    if axis_id and axis_id in self.directions:
                        nx, ny, nz = self.directions[axis_id]
                    else:
                        nx, ny, nz = (0.0, 0.0, 1.0)
                        
                    # Round to avoid float noise
                    nx, ny, nz = round(nx, 3), round(ny, 3), round(nz, 3)
                    normal_groups[(nx, ny, nz)] += 1
        
        if normal_groups:
            print("   [A] 主加工平面方向分布:")
            sorted_normals = sorted(normal_groups.items(), key=lambda x: x[1], reverse=True)
            for normal, count in sorted_normals[:5]:
                direction_name = ""
                if abs(normal[0]) > 0.9: direction_name = " (X轴向)"
                elif abs(normal[1]) > 0.9: direction_name = " (Y轴向)"
                elif abs(normal[2]) > 0.9: direction_name = " (Z轴向)"
                print(f"       - 方向 {normal}: {count} 个面{direction_name}")
        else:
            print("   [A] 未检测到显著平面特征 (可能为全曲面模型)。")
            
        # 2. 孔系同轴度分析
        print("\n   [B] 孔系同轴度与阵列分析:")
        coaxial_groups = []
        
        # 获取尺寸限制
        max_dim = 1000.0
        if hasattr(self, 'filtered_bounds'):
            (min_x, max_x), (min_y, max_y), (min_z, max_z) = self.filtered_bounds
            max_dim = max(max_x - min_x, max_y - min_y, max_z - min_z)
        
        # list of (cid, radius, axis_vec, center_pt)
        cyl_data = []
        for cid, (pid, r) in self.cylinders.items():
            # 过滤掉显然是外部大曲面的特征 (直径 > 最大维度的 80%)
            if r * 2 > max_dim * 0.8:
                continue
                
            if pid in self.placements:
                loc_id, axis_id, _ = self.placements[pid]
                if loc_id in self.points:
                    center = self.points[loc_id]
                    if axis_id and axis_id in self.directions:
                        axis = self.directions[axis_id]
                    else:
                        axis = (0.0, 0.0, 1.0)
                    cyl_data.append({'id': cid, 'r': r, 'c': center, 'a': axis})
        
        # Simple clustering: Same axis, Same projected center
        processed = set()
        for i, c1 in enumerate(cyl_data):
            if c1['id'] in processed: continue
            
            group = [c1]
            processed.add(c1['id'])
            
            for j, c2 in enumerate(cyl_data):
                if i == j or c2['id'] in processed: continue
                
                # Check axis alignment (dot product ~ 1 or -1)
                dot = c1['a'][0]*c2['a'][0] + c1['a'][1]*c2['a'][1] + c1['a'][2]*c2['a'][2]
                if abs(abs(dot) - 1.0) < 0.01:
                    # Check center distance perpendicular to axis
                    # Vector between centers
                    v = (c2['c'][0]-c1['c'][0], c2['c'][1]-c1['c'][1], c2['c'][2]-c1['c'][2])
                    # Project v onto axis
                    proj = v[0]*c1['a'][0] + v[1]*c1['a'][1] + v[2]*c1['a'][2]
                    # Perpendicular component
                    perp_dist_sq = (v[0]-proj*c1['a'][0])**2 + (v[1]-proj*c1['a'][1])**2 + (v[2]-proj*c1['a'][2])**2
                    
                    if perp_dist_sq < 0.1: # < 0.3mm distance
                        group.append(c2)
                        processed.add(c2['id'])
            
            if len(group) > 1:
                coaxial_groups.append(group)
        
        if coaxial_groups:
            print(f"       检测到 {len(coaxial_groups)} 组同轴特征 (如沉头孔/多级轴):")
            for idx, group in enumerate(coaxial_groups):
                # 统计各半径出现的次数
                r_counts = Counter([round(g['r'], 2) for g in group])
                # 按半径从大到小排序
                sorted_r = sorted(r_counts.items(), key=lambda x: x[0], reverse=True)
                
                # 构建精简的半径字符串
                summary_parts = []
                for r, count in sorted_r:
                    if count > 1:
                        summary_parts.append(f"R{r:.1f} (x{count})")
                    else:
                        summary_parts.append(f"R{r:.1f}")
                
                # 如果部分太多，进行截断处理
                if len(summary_parts) > 8:
                    radii_str = ", ".join(summary_parts[:6]) + " ... " + ", ".join(summary_parts[-2:])
                else:
                    radii_str = ", ".join(summary_parts)
                    
                print(f"       - 组 {idx+1:2d}: 包含 {len(group):3d} 个面 [{radii_str}]")
        else:
            print("       未检测到多级同轴特征。")
            
        print("")
