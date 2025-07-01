import cv2
import os
import glob

def images_to_video(image_folder, output_video, fps=240):
    # Get list of JPEG files
    images = sorted(glob.glob(os.path.join(image_folder, "*.jpeg")))
    
    if not images:
        print("No JPEG images found in the specified folder.")
        return
    
    # Read the first image to get dimensions
    frame = cv2.imread(images[0])
    height, width, layers = frame.shape
    
    # Define the codec and create VideoWriter object
    # Using 'mp4v' codec for Mac compatibility
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video = cv2.VideoWriter(output_video, fourcc, fps, (width, height))
    
    # Write each image to the video
    for image in images:
        frame = cv2.imread(image)
        video.write(frame)
    
    # Release the video writer
    video.release()
    print(f"Video saved as {output_video}")

# Example usage
if __name__ == "__main__":
    image_folder = "data/images/"  # Replace with your folder path
    output_video = "output_video_240fps.mp4"     # Output video file name
    images_to_video(image_folder, output_video, fps=240)