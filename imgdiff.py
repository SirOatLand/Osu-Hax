from skimage.metrics import structural_similarity
import cv2
import numpy as np

def detect_imgdiff(image1, image2, threshold_val):

    diff_image = cv2.absdiff(image1, image2)
    diff_image = cv2.cvtColor(diff_image, cv2.COLOR_BGR2GRAY)
    ret, diff_image = cv2.threshold(diff_image, threshold_val, 255, cv2.THRESH_BINARY)

    return diff_image

