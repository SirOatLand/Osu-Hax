import bisect
import math

def point_at_progress(pts, dists, p):
    """p in [0,1] -> returns point at arc-length progress p"""
    if not pts:
        return (0,0)
    target = dists[-1] * p
    i = bisect.bisect_left(dists, target)
    if i == 0:
        return pts[0]
    if i >= len(pts):
        return pts[-1]
    a, b = dists[i-1], dists[i]
    frac = (target - a) / (b - a) if b > a else 0.0
    x = pts[i-1][0] + (pts[i][0] - pts[i-1][0]) * frac
    y = pts[i-1][1] + (pts[i][1] - pts[i-1][1]) * frac
    return x, y

def sample_polyline(poly_pts, n_per_segment=8):
    """
    Produces sampled points and cumulative distances for a polyline defined
    by poly_pts = [(x0,y0), (x1,y1), ..., (xn,yn)].
    n_per_segment controls smoothness per straight segment.
    """
    if len(poly_pts) == 0:
        return [], [0.0]
    samples = []
    dists = [0.0]

    # start with the first point
    samples.append(poly_pts[0])

    for i in range(len(poly_pts)-1):
        a = poly_pts[i]
        b = poly_pts[i+1]
        # sample the segment excluding the first endpoint (already added)
        for s in range(1, n_per_segment+1):
            t = s / (n_per_segment + 0)  # s/(n) gives n samples including endpoint
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            samples.append((x,y))
            # compute cumulative dist
            prev = samples[-2]
            segd = math.hypot(x - prev[0], y - prev[1])
            dists.append(dists[-1] + segd)

    return samples, dists

def bezier_point(points, t):
    """Evaluate Bezier curve of any degree using De Casteljau."""
    pts = list(points)
    n = len(pts)
    for r in range(1, n):
        for i in range(n - r):
            x = (1-t)*pts[i][0] + t*pts[i+1][0]
            y = (1-t)*pts[i][1] + t*pts[i+1][1]
            pts[i] = (x, y)
    return pts[0]

def sample_curve(eval_fn, n=250):
    pts = [eval_fn(i/(n-1)) for i in range(n)]
    dists = [0.0]
    for i in range(1, n):
        dx = pts[i][0] - pts[i-1][0]
        dy = pts[i][1] - pts[i-1][1]
        dists.append(dists[-1] + math.hypot(dx, dy))
    return pts, dists

def point_at_progress(pts, dists, p):
    target = dists[-1] * p
    i = bisect.bisect_left(dists, target)
    if i == 0:
        return pts[0]
    if i >= len(pts):
        return pts[-1]
    a, b = dists[i-1], dists[i]
    frac = (target - a) / (b - a) if b > a else 0
    x = pts[i-1][0] + (pts[i][0] - pts[i-1][0]) * frac
    y = pts[i-1][1] + (pts[i][1] - pts[i-1][1]) * frac
    return x, y


class SliderAction:
    def __init__(self, obj):
        self.obj = obj
        self.done = False
        self.type = 2
        self.endTime = obj.time + obj.duration_ms

        # --- Build full curve control points ---
        cp = [(obj.x, obj.y)] + obj.points

        # --- L-type: simple lerp between endpoints ---
        if obj.curveType == "L":
            self.samples, self.dists = sample_polyline(cp, n_per_segment=12)
            return

        # --- B-type: sample full bezier ---
        if obj.curveType == "B":
            eval_fn = lambda t: bezier_point(cp, t)
            self.samples, self.dists = sample_curve(eval_fn, n=300)
            return

        print("Unsupported curve type:", obj.curveType)

    def update(self, t):
        if self.done:
            return

        start_t = self.obj.time / 1000
        end_t = self.endTime / 1000

        # raw slider progress
        progress_raw = (t - start_t) / (end_t - start_t)
        progress_raw = max(0, min(progress_raw, 1))

        # slidebacks
        total = progress_raw * self.obj.slides
        slide_index = int(total)
        slide_pos = total - slide_index

        if slide_index % 2 == 0:
            progress = slide_pos
        else:
            progress = 1 - slide_pos

        # get arc-length-correct point
        px, py = point_at_progress(self.samples, self.dists, progress)

        sx, sy = osu_to_screen(px, py)
        set_cursor(sx, sy)
        # mouse_leftdown()
        if progress_raw  >= 1:
            # mouse_leftup()
            self.done = True

    def changedone(self):
        self.done = False

if __name__ == "__main__":
     
    from read_map import Slider, compute_slider_timings
    from osu_input import osu_to_screen, set_cursor
    import time as ttime

    # OBJ=Slider(x=288, y=160, time=5000, type=2, hitSound=0, 
    #         curveType='B', points=[(512, 160)], slides=3, 
    #         length=192.0, edgeSounds=[], edgeSets=[], extras='', 
    #         duration_ms=499.991753436068, end_time=69029)
    
    parts="288,64,160027,6,0,L|352:64|352:224,2,192,2|8|2"

    parts = parts.split(",")

    x = int(parts[0])
    y = int(parts[1])
    time = int(parts[2])
    type_ = int(parts[3])
    hitSound = int(parts[4])
    curve_raw = parts[5]
    slides = int(parts[6])
    length = float(parts[7])

    # parse curve type and control points
    curveType, *point_strs = curve_raw.split("|")
    points = []
    for p in point_strs:
        if p == "":
            continue
        px, py = map(int, p.split(":"))
        points.append((px, py))

    edgeSounds = []
    if len(parts) > 8 and parts[8]:
        edgeSounds = list(map(int, parts[8].split("|")))

    edgeSets = []
    if len(parts) > 9 and parts[9]:
        raw = parts[9].split("|")
        for es in raw:
            if es:
                a, b = es.split(":")
                edgeSets.append((int(a), int(b)))

    extras = parts[10] if len(parts) > 10 else ""

    OBJ = Slider(x, y, time, type_, hitSound, 
                      curveType, points, slides, length, 
                      edgeSounds, edgeSets, extras)

    OBJ.time = 1000

    OBJ.duration_ms = 2000
    OBJ.end_time = int(round(OBJ.time + OBJ.duration_ms))
    print(OBJ)
    ACTION = SliderAction(OBJ)

    initial_timestamp = ttime.perf_counter()
    while True:
         now_t = ttime.perf_counter() - initial_timestamp
         ACTION.update(now_t)
         print(f"time - {now_t:.5}, OBJtime - {OBJ.time / 1000}")

         if ACTION.done:
             break
         ttime.sleep(0.05)
    

