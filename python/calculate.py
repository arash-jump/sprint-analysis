import json
import sys
import math
import cv2
import mediapipe as mp

def main():
    #Checking submition number
    if len(sys.argv)< 2:
        print(json.dumps({"error" : "no input"}))
        return
    
    #sys.arcv[1] means second argument from PHP
    payload_json = sys.argv[1]
    #loads = Converting JSON into dict
    payload = json.loads(payload_json)

    movie_path = payload.get("movie_path")
    fps = float(payload.get("fps") or 0)
    run_distance = float(payload.get("run_distance") or 0)
    calibration_distance = float(payload.get("calibration_distance") or 0)

    calibration_points = payload.get("calibration_point") or []

    scale_m_per_px = None
    pixel_distance = None

    if isinstance(calibration_points, list) and len(calibration_points) >= 2:
        p1 = calibration_points[0]
        p2 = calibration_points[1]

        x1, y1 = float(p1["x"]), float(p1["y"])
        x2, y2 = float(p2["x"]), float(p2["y"])

        dx = abs(x2 - x1)
        dy = abs(y2 - y1)

        pixel_distance = math.hypot(dx, dy)

        if pixel_distance > 0 and calibration_distance > 0:
            scale_m_per_px = calibration_distance/pixel_distance

    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose()

    cap = cv2.VideoCapture(movie_path)

    frame_count = 0
    hip_positions_px = []
    detected_hips=[]
    timestamps = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        h, w, _ = frame.shape

        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        results = pose.process(image_rgb)

        if results.pose_landmarks:
            hip = results.pose_landmarks.landmark[28]
            x_px = hip.x * w 
            y_px = hip.y * h

            detected_hips.append({
                "frame": frame_count,
                "x": x_px,
                "y": y_px
            })

            hip_positions_px.append((x_px, y_px))

            if fps > 0:
                t = frame_count / fps
            else:
                t = frame_count
            timestamps.append(t)
   
    cap.release()
    pose.close()

    if len(detected_hips) >= 2 and fps > 0:
        detected_hips.sort(key=lambda d: d["frame"])

        start_frame = detected_hips[0]["frame"]
        end_frame  = detected_hips[-1]["frame"]

        j = 0  # detected_hips の現在インデックス

        for f in range(start_frame, end_frame + 1):
            # j, j+1 が f をまたぐように調整
            while j + 1 < len(detected_hips) and detected_hips[j + 1]["frame"] < f:
                j += 1

            if detected_hips[j]["frame"] == f:
                # ちょうど検出されたフレーム
                x = detected_hips[j]["x"]
                y = detected_hips[j]["y"]
            elif j + 1 < len(detected_hips) and detected_hips[j]["frame"] < f < detected_hips[j + 1]["frame"]:
                # 中間フレーム → 線形補間
                f0 = detected_hips[j]["frame"]
                f1 = detected_hips[j + 1]["frame"]
                t  = (f - f0) / (f1 - f0)  # 0〜1 の割合

                x0, y0 = detected_hips[j]["x"], detected_hips[j]["y"]
                x1, y1 = detected_hips[j + 1]["x"], detected_hips[j + 1]["y"]

                x = x0 + t * (x1 - x0)
                y = y0 + t * (y1 - y0)
            else:
                # 検出が飛びすぎている・末尾などはスキップでもOK
                continue

        hip_positions_px.append((x, y))
        timestamps.append(f / fps)

    segment_length = 10.0
    segment_sums = {}
    segment_counts = {}
    cum_distance = 0.0

    velocities = []
    if scale_m_per_px and fps > 0 and len(hip_positions_px) >= 2:
        for i in range(1, len(hip_positions_px)):
            x_prev, y_prev = hip_positions_px[i-1]
            x_curr, y_curr = hip_positions_px[i]

            dx_px = x_curr - x_prev

            distance_m = abs(dx_px) * scale_m_per_px

            dt = 1.0 / fps
            v = distance_m /dt
            velocities.append(v)

            cum_distance += distance_m
            segment_index = int(cum_distance // segment_length)

            if segment_index not in segment_sums:
                segment_sums[segment_index] = 0.0
                segment_counts[segment_index] = 0
            
            segment_sums[segment_index] += v
            segment_counts[segment_index] +=1

            print(f"frame {i}, dx_px={dx_px:.2f}, distance_m={distance_m:.3f}, cum_distance={cum_distance:.3f}, segment_index={segment_index}")
            

    if velocities:
        max_v = max(velocities)
        avg_v = sum(velocities)/len(velocities)
    else:
        max_v = 0.0
        avg_v = 0.0

    segment_speeds = []
    for idx in sorted(segment_sums.keys()):
        if segment_counts[idx] > 0:
            avg_seg_v = segment_sums[idx] / segment_counts[idx]
        else:
            avg_seg_v = 0.0
        start_m = idx * segment_length
        end_m = start_m + segment_length
        segment_speeds.append({
            "start":start_m,
            "end":end_m,
            "avg_velocity": avg_seg_v
        })

    result = {
        "fps" : fps,
        "run_distance" : run_distance,
        "calibration_distance" : calibration_distance,
        "pixel_distance" : pixel_distance,
        "scale_m_per_px" : scale_m_per_px,
        "frame_count" : len(hip_positions_px),
        "velocity_max": max_v,
        "velocity_avg": avg_v,
        "segment_length":segment_length,
        "segment_speeds":segment_speeds
    }

    print(json.dumps(result))

if __name__ == "__main__":
    main()