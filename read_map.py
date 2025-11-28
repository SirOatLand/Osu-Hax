from dataclasses import dataclass, field
from typing import List, Tuple, Optional

@dataclass
class TimingPoint:
    time: int                # offset (ms)
    beat_length: float       # ms per beat (positive for uninherited; negative for inherited)
    meter: int
    sample_set: int
    sample_index: int
    volume: int
    uninherited: bool        # True if uninherited, False if inherited
    effects: int

@dataclass
class HitCircle:
    x: int
    y: int
    time: int
    type: int
    hitSound: int

@dataclass
class Spinner:
    x: int
    y: int
    time: int
    type: int
    hitSound: int
    endTime: int
    additions: str = ""

@dataclass
class Slider:
    x: int
    y: int
    time: int
    type: int
    hitSound: int
    curveType: str
    points: List[Tuple[int,int]]
    slides: int
    length: float
    edgeSounds: List[int] = field(default_factory=list)
    edgeSets: List[Tuple[int,int]] = field(default_factory=list)
    extras: str = ""
    # computed fields (will be set after knowing timing/sliderMultiplier)
    duration_ms: Optional[float] = None
    end_time: Optional[int] = None

def parse_hitobject(line: str):
    parts = line.split(",")

    x = int(parts[0])
    y = int(parts[1])
    time = int(parts[2])
    type_ = int(parts[3])
    hitSound = int(parts[4])

    # BITMASK TYPE CHECKS
    is_circle = (type_ & 1) > 0
    is_slider = (type_ & 2) > 0
    is_spinner = (type_ & 8) > 0

    if is_circle:
        return HitCircle(x, y, time, type_, hitSound)

    if is_spinner:
        endTime = int(parts[5])
        additions = parts[6] if len(parts) > 6 else ""
        return Spinner(x, y, time, type_, hitSound, endTime, additions)

    if is_slider:
        # slider: x,y,time,type,hitSound,curve|points,slides,length,edgeSounds?,edgeSets?,extras?-
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

        return Slider(x, y, time, type_, hitSound, 
                      curveType, points, slides, length, 
                      edgeSounds, edgeSets, extras)

    print("Unknown hitobject type:", line)
    return None

def get_active_uninherited_timing(timing_points: List[TimingPoint], ms_time: int) -> Optional[TimingPoint]:
    """
    Return the last uninherited timing point whose time <= ms_time.
    If none exist, return the first uninherited found as fallback or None.
    """
    last: Optional[TimingPoint] = None
    for tp in timing_points:
        if not tp.uninherited:
            continue
        if tp.time <= ms_time:
            last = tp
        else:
            break
    if last is not None:
        return last
    # fallback: first uninherited
    for tp in timing_points:
        if tp.uninherited:
            return tp
    return None

def get_active_inherited_timing(timing_points: List[TimingPoint], ms_time: int) -> Optional[TimingPoint]:
    """
    Return the last inherited timing point (green line) whose time <= ms_time.
    If none, return None.
    """
    last: Optional[TimingPoint] = None
    for tp in timing_points:
        if tp.uninherited:
            continue
        if tp.time <= ms_time:
            last = tp
        else:
            break
    return last

def compute_slider_timings(hitobjects: List, timing_points: List[TimingPoint], slider_multiplier: float):
    """
    For each Slider object in hitobjects, compute:
      - slider.duration_ms (total ms across all repeats)
      - slider.end_time (ms absolute, start_time + duration)
    This modifies the Slider objects in-place.
    Formula source: osu! wiki & community (see links in code comments).
    """
    for obj in hitobjects:
        if isinstance(obj, Slider):
            start_ms = obj.time

            # get uninherited (red) timing point for beatLength (ms per beat)
            utp = get_active_uninherited_timing(timing_points, start_ms)
            if utp is None:
                # fallback default 500ms per beat (120 BPM)
                beat_length = 500.0
            else:
                beat_length = utp.beat_length

            # get inherited (green) timing point for slider velocity (SV)
            itp = get_active_inherited_timing(timing_points, start_ms)

            if itp is None:
                sv = 1.0
            else:
                # inherited timing points store a negative beat_length representing SV.
                # SV = 100 / abs(inherited_beat_length)
                # (equivalently SV = -(1 / inherited_beat_length) * 100)
                inherited_bl = itp.beat_length
                if inherited_bl == 0:
                    sv = 1.0
                else:
                    sv = 100.0 / abs(inherited_bl)

            # pxPerBeat = slider_multiplier * 100 * SV
            px_per_beat = slider_multiplier * 100.0 * sv

            # number of traversals is obj.slides (this is the 'slides' field from .osu)
            traversals = obj.slides

            # total beats covered by slider = (pixelLength * traversals) / pxPerBeat
            beats = (obj.length * traversals) / px_per_beat

            # total ms = beats * beat_length
            duration_ms = beats * beat_length

            obj.duration_ms = duration_ms
            obj.end_time = int(round(obj.time + duration_ms))

    return hitobjects


def read_osu_file(filepath):
    """
    Parses the osu file and returns:
      - hitobjects: list of HitCircle|Slider|Spinner instances (in file order)
      - timing_points: list of TimingPoint (in file order)
      - slider_multiplier: float from [Difficulty] (SliderMultiplier)
    """
    hitobjects = []
    timing_points: List[TimingPoint] = []
    slider_multiplier = 1.0
    approach_rate = None

    section = None
    with open(filepath, "r", encoding="utf8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Section headers
            if line.startswith("["):
                section = line
                continue

            # ---------- Difficulty ----------
            if section == "[Difficulty]":
                if line.startswith("SliderMultiplier:"):
                    try:
                        slider_multiplier = float(line.split(":", 1)[1].strip())
                    except Exception:
                        pass
                elif line.startswith("OverallDifficulty:"):
                    try:
                        overall_dificulty = float(line.split(":", 1)[1].strip())
                    except Exception:
                        pass
                elif line.startswith("ApproachRate:"):
                    try:
                        approach_rate = float(line.split(":", 1)[1].strip())
                    except Exception:
                        pass

            # ---------- Timing Points ----------
            elif section == "[TimingPoints]":
                parts = line.split(",")
                # time, beatLength, meter, sampleSet, sampleIndex, volume, uninherited, effects
                if len(parts) >= 8:
                    tp_time = int(float(parts[0]))
                    beat_length = float(parts[1])
                    meter = int(float(parts[2])) if parts[2] else 4
                    sample_set = int(parts[3]) if parts[3] else 0
                    sample_index = int(parts[4]) if parts[4] else 0
                    volume = int(parts[5]) if parts[5] else 100
                    uninherited_flag = int(parts[6])
                    effects = int(parts[7]) if parts[7] else 0
                    tp = TimingPoint(
                        time=tp_time,
                        beat_length=beat_length,
                        meter=meter,
                        sample_set=sample_set,
                        sample_index=sample_index,
                        volume=volume,
                        uninherited=(uninherited_flag == 1),
                        effects=effects
                    )
                    timing_points.append(tp)

            # ---------- Hit Objects ----------
            elif section == "[HitObjects]":
                hitobjects.append(parse_hitobject(line))

    return hitobjects, timing_points, slider_multiplier, overall_dificulty, approach_rate

def prep_osu_objects(filepath):
    # Read file
    hitobjects, timing_points, slider_multiplier, overall_dificulty, approach_rate = read_osu_file(filepath)


    # calculate AR delay based on https://osu.ppy.sh/wiki/en/Beatmap/Approach_rate
    if approach_rate is None:
        approach_rate = overall_dificulty

    if approach_rate <= 5: 
        AR_delay = 1200 + 120 * (5 - approach_rate)
    elif approach_rate:
        AR_delay = 1200 - 150 * (approach_rate - 5)

    # calculate hit delay for perfect hit
    time_delay_300 =  ((80 - (6 * overall_dificulty)) / 1000)

    # Get Slider timing (duration + end_time)
    hitobjects = compute_slider_timings(hitobjects, timing_points, slider_multiplier)

    return hitobjects, timing_points, slider_multiplier, time_delay_300 

if __name__ == "__main__":
    osu_objects = read_osu_file('./test_songs/cin1.osu')
    circles = [obj for obj in osu_objects if isinstance(obj, HitCircle)]
    sliders = [obj for obj in osu_objects if isinstance(obj, Slider)]
    spinners = [obj for obj in osu_objects if isinstance(obj, Spinner)]

    print(len(circles), len(sliders), len(spinners))
