import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend to avoid thread issues
import matplotlib.pyplot as plt
import re
import os
import math
import numpy as np

class STPViewer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.points = [] # list of (x, y, z)
        self.circles = [] # list of dicts: {'center': (x,y,z), 'radius': r, 'axis': (dx,dy,dz), 'ref_dir': (rx,ry,rz)}
        
        # Internal maps for parsing
        self._lines_map = {} # line_id -> raw_line_string
        self._parsed_cache = {} # id -> parsed_object

    def _parse_id(self, ref_str):
        """Extract id from #123"""
        if ref_str.startswith('#'):
            return int(ref_str[1:])
        return None

    def _get_entity(self, entity_id):
        if entity_id in self._parsed_cache:
            return self._parsed_cache[entity_id]
        
        if entity_id not in self._lines_map:
            return None
            
        line = self._lines_map[entity_id]
        
        # Parse CARTESIAN_POINT
        if 'CARTESIAN_POINT' in line:
            # #123=CARTESIAN_POINT('Name',(x,y,z))
            m = re.search(r"=\s*CARTESIAN_POINT\s*\([^,]*,\s*\(\s*([-\d\.eE+]+)\s*,\s*([-\d\.eE+]+)\s*,\s*([-\d\.eE+]+)\s*\)\s*\)", line)
            if m:
                pt = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
                self._parsed_cache[entity_id] = {'type': 'POINT', 'coords': pt}
                return {'type': 'POINT', 'coords': pt}

        # Parse DIRECTION
        elif 'DIRECTION' in line:
            # #123=DIRECTION('Name',(x,y,z))
            m = re.search(r"=\s*DIRECTION\s*\([^,]*,\s*\(\s*([-\d\.eE+]+)\s*,\s*([-\d\.eE+]+)\s*,\s*([-\d\.eE+]+)\s*\)\s*\)", line)
            if m:
                vec = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
                self._parsed_cache[entity_id] = {'type': 'DIRECTION', 'vector': vec}
                return {'type': 'DIRECTION', 'vector': vec}

        # Parse AXIS2_PLACEMENT_3D
        elif 'AXIS2_PLACEMENT_3D' in line:
            # #123=AXIS2_PLACEMENT_3D('Name',#Location,#Axis,#RefDir)
            m = re.search(r"=\s*AXIS2_PLACEMENT_3D\s*\([^,]*,\s*#(\d+)\s*,\s*(#\d+|\$)\s*,\s*(#\d+|\$)\s*\)", line)
            if m:
                loc_id = int(m.group(1))
                axis_id_str = m.group(2)
                ref_id_str = m.group(3)
                
                loc = self._get_entity(loc_id)
                axis = {'vector': (0,0,1)} # Default Z
                ref = {'vector': (1,0,0)} # Default X
                
                if axis_id_str != '$':
                    axis_obj = self._get_entity(int(axis_id_str[1:]))
                    if axis_obj: axis = axis_obj
                
                if ref_id_str != '$':
                    ref_obj = self._get_entity(int(ref_id_str[1:]))
                    if ref_obj: ref = ref_obj
                
                placement = {
                    'type': 'PLACEMENT',
                    'center': loc['coords'] if loc else (0,0,0),
                    'axis': axis['vector'],
                    'ref_dir': ref['vector']
                }
                self._parsed_cache[entity_id] = placement
                return placement

        # Parse CIRCLE
        elif 'CIRCLE' in line:
            # #123=CIRCLE('Name',#Placement,Radius)
            m = re.search(r"=\s*CIRCLE\s*\([^,]*,\s*#(\d+)\s*,\s*([-\d\.eE+]+)\s*\)", line)
            if m:
                placement_id = int(m.group(1))
                radius = float(m.group(2))
                placement = self._get_entity(placement_id)
                
                if placement and 'center' in placement:
                    circle = {
                        'type': 'CIRCLE',
                        'center': placement['center'],
                        'radius': radius,
                        'axis': placement.get('axis', (0,0,1)),
                        'ref_dir': placement.get('ref_dir', (1,0,0))
                    }
                    self._parsed_cache[entity_id] = circle
                    return circle
                # If placement exists but is malformed or missing keys
                elif placement:
                    # Try to be resilient
                    if 'coords' in placement: # Maybe it was a POINT?
                         circle = {
                            'type': 'CIRCLE',
                            'center': placement['coords'],
                            'radius': radius,
                            'axis': (0,0,1),
                            'ref_dir': (1,0,0)
                        }
                         self._parsed_cache[entity_id] = circle
                         return circle
                    
        return {'type': 'UNKNOWN'}

    def extract_features(self):
        """解析 STP 文件并提取点云和曲线特征"""
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        # 1. Build Index Map
        full_stmt = ""
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            full_stmt += line
            if not line.endswith(';'):
                continue
                
            # Extract ID if present: #123=...
            if full_stmt.startswith('#'):
                try:
                    eq_idx = full_stmt.find('=')
                    if eq_idx > 0:
                        entity_id = int(full_stmt[1:eq_idx])
                        self._lines_map[entity_id] = full_stmt
                except:
                    pass
            
            full_stmt = ""

        # 2. Iterate and Parse
        for eid, line in self._lines_map.items():
            # Extract Points
            if 'CARTESIAN_POINT' in line:
                pt = self._get_entity(eid)
                if pt and pt['type'] == 'POINT':
                    x, y, z = pt['coords']
                    # Relaxed filtering: only filter true infinities/NaNs or extreme outliers
                    if abs(x) < 1e10 and abs(y) < 1e10 and abs(z) < 1e10:
                        self.points.append((x, y, z))
            
            # Extract Circles
            elif 'CIRCLE' in line:
                circle = self._get_entity(eid)
                if circle and circle['type'] == 'CIRCLE':
                    self.circles.append(circle)
        
        # Fallback: if points list is empty (maybe regex failed on complex format), try simple scan
        if not self.points:
            self._simple_scan_points()

    def _simple_scan_points(self):
        """Fallback method using simple regex scan"""
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        pattern = re.compile(r"=\s*CARTESIAN_POINT\s*\([^,]*,\s*\(\s*([-\d\.eE+]+)\s*,\s*([-\d\.eE+]+)\s*,\s*([-\d\.eE+]+)\s*\)\s*\)")
        matches = pattern.findall(content)
        for match in matches:
            try:
                x, y, z = map(float, match)
                if abs(x) < 1e10 and abs(y) < 1e10 and abs(z) < 1e10:
                    self.points.append((x, y, z))
            except: pass

    def _generate_circle_points(self, circle, num_points=36):
        """Discretize a circle into points"""
        center = np.array(circle['center'])
        radius = circle['radius']
        axis = np.array(circle['axis'])
        norm = np.linalg.norm(axis)
        if norm < 1e-9: axis = np.array([0,0,1])
        else: axis = axis / norm
        
        # Create basis vectors
        major_axis = np.array([1, 0, 0])
        if abs(np.dot(major_axis, axis)) > 0.9:
            major_axis = np.array([0, 1, 0])
            
        u = np.cross(axis, major_axis)
        u = u / np.linalg.norm(u)
        v = np.cross(axis, u)
        
        points = []
        for i in range(num_points):
            theta = 2 * math.pi * i / num_points
            pt = center + radius * (math.cos(theta) * u + math.sin(theta) * v)
            points.append(pt)
        return points

    def generate_multiview(self, output_dir="."):
        if not self.points:
            self.extract_features()
            
        # Collect all drawing points (raw points + discretized curves)
        draw_points = list(self.points)
        
        # Discretize circles
        for circle in self.circles:
            circle_pts = self._generate_circle_points(circle)
            draw_points.extend([tuple(p) for p in circle_pts])

        if not draw_points:
            return "No geometry points found in STP file."

        xs = [p[0] for p in draw_points]
        ys = [p[1] for p in draw_points]
        zs = [p[2] for p in draw_points]
        
        def get_limits(data):
            if not data: return -1, 1
            sorted_data = sorted(data)
            n = len(data)
            if n < 20: return min(data), max(data)
            lower = sorted_data[int(n * 0.05)]
            upper = sorted_data[int(n * 0.95)]
            margin = (upper - lower) * 0.2
            return lower - margin, upper + margin

        x_lim = get_limits(xs)
        y_lim = get_limits(ys)
        z_lim = get_limits(zs)

        fig = plt.figure(figsize=(18, 6))
        scatter_kwargs = {'s': 1.0, 'alpha': 0.6, 'edgecolors': 'none'}
        
        def plot_view(ax, x_data, y_data, title, xlabel, ylabel, xlim, ylim, color):
            ax.scatter(x_data, y_data, c=color, **scatter_kwargs)
            ax.set_title(title, fontsize=12, fontweight='bold')
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_aspect('equal', adjustable='datalim')
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            ax.grid(True, linestyle=':', alpha=0.6)

        # XY View (Top)
        ax1 = fig.add_subplot(131)
        plot_view(ax1, xs, ys, 'Top View (XY)', 'X', 'Y', x_lim, y_lim, 'blue')

        # XZ View (Front)
        ax2 = fig.add_subplot(132)
        plot_view(ax2, xs, zs, 'Front View (XZ)', 'X', 'Z', x_lim, z_lim, 'red')

        # YZ View (Side)
        ax3 = fig.add_subplot(133)
        plot_view(ax3, ys, zs, 'Side View (YZ)', 'Y', 'Z', y_lim, z_lim, 'green')

        output_path = os.path.join(output_dir, f"{os.path.basename(self.file_path)}_multiview.png")
        plt.tight_layout()
        plt.savefig(output_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        
        return output_path

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python stp_viewer.py <path_to_stp_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"Processing {file_path}...")
    try:
        viewer = STPViewer(file_path)
        viewer.extract_features()
        print(f"Extracted {len(viewer.points)} points and {len(viewer.circles)} circles.")
        
        output = viewer.generate_multiview()
        print(f"Successfully generated multiview: {output}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
