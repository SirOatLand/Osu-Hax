import cv2
import os
import time

def save_image(img, folder_names=['img1', 'img2', 'img3', 'img4'], img_count=250, delay=0.5):
    
    current_folder = None
    for folder in folder_names:
        folder_path = './screenshot/' + folder
        file_count = len(os.listdir(folder_path))
        if  file_count < img_count:
            current_folder = folder_path
            break
    
    if current_folder is None:
        print("All folders are full!")
        return
    
    current_file_count = len(os.listdir(current_folder))
    current_filename = f"{current_folder}/img_{current_file_count:04d}.png"

    cv2.imwrite(current_filename, img)
    print("Saved:", current_filename)
    time.sleep(delay)