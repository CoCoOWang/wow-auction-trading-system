# 图像特征点对齐工具（备用）
# magic_wow_automation/utils/image_alignment.py
import cv2
import numpy as np


def preprocess_image(img):
    """
    图像预处理：增强灰度图 → 再转换回 BGR，供 YOLOv8 使用
    """
    if len(img.shape) == 3:
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        img_gray = img.copy()

    # 直方图均衡化 + 模糊 + 锐化
    enhanced_image = cv2.equalizeHist(img_gray)
    blurred_image = cv2.GaussianBlur(enhanced_image, (5, 5), 0)
    sharpened_image = cv2.addWeighted(enhanced_image, 1.5, blurred_image, -0.5, 0)

    # 转回 3 通道供 YOLOv8 使用
    final_image = cv2.cvtColor(sharpened_image, cv2.COLOR_GRAY2BGR)

    return final_image


def align_images(image1, image2):
    """
    使用SIFT+FLANN特征点检测进行图像对齐
    """
    sift = cv2.SIFT_create()

    keypoint1, descriptors1 = sift.detectAndCompute(preprocess_image(image1), None)
    keypoint2, descriptors2 = sift.detectAndCompute(preprocess_image(image2), None)

    flann = cv2.FlannBasedMatcher()
    matches = flann.knnMatch(descriptors1, descriptors2, k=2)

    good_matches = []
    for m, n in matches:
        if m.distance < 0.75 * n.distance:
            good_matches.append(m)

    if len(good_matches) > 4:
        points1 = np.float32([keypoint1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        points2 = np.float32([keypoint2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        M, mask = cv2.findHomography(points2, points1, cv2.RANSAC, 5.0)
        height, width = image1.shape[:2]
        aligned_image = cv2.warpPerspective(image2, M, (width, height))
        return aligned_image
    else:
        return None

