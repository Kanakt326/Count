import streamlit as st
import yaml
import numpy as np
import cv2
from datetime import datetime
import openpyxl
import os

def start_counting():
    start_time = datetime.now()
    last_time = datetime.now()

    ct = 0
    total_output = 0
    ppm = 0
    ppm_average = 0

    rec_qty = 8
    qty = 0

    # Update the path for the Excel output file
    path = os.path.join(os.getcwd(), "output.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(("datetime", "total_output", "minute", "average ppm", "ct", "ppm"))

    # Update the paths for YAML and video output files
    fn_yaml = os.path.join(os.path.dirname(__file__), "area.yml")
    fn_out = os.path.join(os.getcwd(), "count", "output.avi")

    # Check if the YAML file exists
    if not os.path.isfile(fn_yaml):
        st.error(f"Configuration file {fn_yaml} not found. Please ensure it exists in the same directory as the script.")
        return

    with open(fn_yaml, 'r') as stream:
        object_area_data = yaml.safe_load(stream)

    config = {
        'save_video': False,
        'text_overlay': True,
        'object_overlay': True,
        'object_id_overlay': False,
        'object_detection': True,
        'min_area_motion_contour': 60,
        'park_sec_to_wait': 0.001,
        'start_frame': 0
    }

    cap = cv2.VideoCapture(0)

    if config['save_video']:
        fourcc = cv2.VideoWriter_fourcc('D', 'I', 'V', 'X')
        out = cv2.VideoWriter(fn_out, fourcc, 25.0, (640, 480))

    object_status = [False] * len(object_area_data)
    object_buffer = [None] * len(object_area_data)

    frames = []
    while cap.isOpened():
        try:
            video_cur_pos = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            ret, frame = cap.read()
            if not ret:
                st.error("Capture Error")
                break

            frame_blur = cv2.GaussianBlur(frame.copy(), (5, 5), 3)
            frame_gray = cv2.cvtColor(frame_blur, cv2.COLOR_BGR2GRAY)
            frame_out = frame.copy()

            if config['object_detection']:
                for ind, park in enumerate(object_area_data):
                    points = np.array(park['points'])
                    rect = cv2.boundingRect(points)
                    roi_gray = frame_gray[rect[1]:(rect[1] + rect[3]), rect[0]:(rect[0] + rect[2])]

                    points[:, 0] = points[:, 0] - rect[0]
                    points[:, 1] = points[:, 1] - rect[1]

                    status = np.std(roi_gray) < 20 and np.mean(roi_gray) > 56

                    if status != object_status[ind] and object_buffer[ind] is None:
                        object_buffer[ind] = video_cur_pos
                    elif status != object_status[ind] and object_buffer[ind] is not None:
                        if video_cur_pos - object_buffer[ind] > config['park_sec_to_wait']:
                            if not status:
                                qty += 1
                                total_output += 1

                                current_time = datetime.now()
                                diff = current_time - last_time
                                ct = diff.total_seconds()
                                ppm = round(60 / ct, 2)
                                last_time = current_time

                                diff = current_time - start_time
                                minutes = diff.total_seconds() / 60
                                ppm_average = round(total_output / minutes, 2)

                                data = (current_time, total_output, minutes, ppm_average, ct, ppm)
                                ws.append(data)

                                if qty > rec_qty:
                                    data = (current_time, total_output, minutes, ppm_average, ct, ppm)
                                    ws.append(data)
                                    qty = 0

                            object_status[ind] = status
                            object_buffer[ind] = None

                    elif status == object_status[ind] and object_buffer[ind] is not None:
                        object_buffer[ind] = None

            if config['object_overlay']:
                for ind, park in enumerate(object_area_data):
                    points = np.array(park['points'])
                    color = (0, 255, 0) if object_status[ind] else (0, 0, 255)
                    cv2.drawContours(frame_out, [points], contourIdx=-1, color=color, thickness=2, lineType=cv2.LINE_8)

            if config['text_overlay']:
                cv2.rectangle(frame_out, (1, 5), (350, 70), (0, 255, 0), 2)
                cv2.putText(frame_out, "Object Counting:", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
                cv2.putText(frame_out, f'Total Output: {total_output}', (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
                cv2.putText(frame_out, f'PPM: {ppm}', (5, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

            if config['save_video']:
                out.write(frame_out)

            # Convert frame to bytes for Streamlit
            _, buffer = cv2.imencode('.jpg', frame_out)
            frames.append(buffer.tobytes())

            # Display the current frame in Streamlit
            if frames:
                st.image(frames[-1], channels="RGB")

            # Check for keyboard input to stop counting
            if st.session_state.stop_counting:
                break

        except Exception as e:
            print(e)
            break

    wb.save(path)
    cap.release()
    cv2.destroyAllWindows()  # This can be removed if running in non-GUI mode
    return total_output

def main():
    st.title("Object Counting Application")

    if "stop_counting" not in st.session_state:
        st.session_state.stop_counting = False

    # Display urgent stop button at the top right corner
    col1, col2 = st.columns([5, 1])  # Adjusted column width for layout
    with col2:
        urgent_stop = st.button("❌ Urgent Stop", key="urgent_stop")

    if urgent_stop:
        st.session_state.stop_counting = True

    if st.button("Start Counting"):
        st.session_state.stop_counting = False
        with st.spinner("Counting in progress..."):
            total_count = start_counting()
            st.success("Counting completed!")
            st.write(f"Total Count: {total_count}")

if __name__ == "__main__":
    main()
