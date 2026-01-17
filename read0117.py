import cv2
import numpy as np

def detect_black_squares(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    squares = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 300:
            continue
        x, y, w, h = cv2.boundingRect(c)
        ratio = w / float(h)
        if 0.8 < ratio < 1.2:
            squares.append((x, y, w, h))
    return squares


def detect_circles(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 1.5)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=25,
        param1=100,
        param2=25,
        minRadius=5,
        maxRadius=40
    )

    if circles is None:
        return []
    return np.uint16(np.around(circles[0]))
