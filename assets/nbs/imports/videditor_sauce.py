import os
from pathlib import Path
from moviepy.editor import VideoFileClip, concatenate_videoclips

def concatenate_videos(video_paths: list, output_filename: str = "output.mp4") -> str:
    """
    Takes a list of video file paths, concatenates them, and saves the result.
    
    Args:
        video_paths (list): List of string paths to video files.
        output_filename (str): Name of the output file (saved in current directory).
        
    Returns:
        str: The absolute path to the created video file, or None if failed.
    """
    print(f"🎬 Starting video concatenation...")
    
    valid_clips = []
    loaded_objects = [] # Keep track to close them later

    # 1. Validation and Loading
    for p in video_paths:
        path_obj = Path(p)
        if not path_obj.exists():
            print(f"❌ File not found: {p}")
            continue
            
        try:
            print(f"  -> Loading: {path_obj.name}")
            clip = VideoFileClip(str(path_obj))
            loaded_objects.append(clip)
            valid_clips.append(clip)
        except Exception as e:
            print(f"❌ Error loading {p}: {e}")

    if not valid_clips:
        print("⚠️ No valid clips to process.")
        return None

    # 2. Concatenation
    try:
        print(f"🔗 Concatenating {len(valid_clips)} clips...")
        final_clip = concatenate_videoclips(valid_clips)
        
        output_path = Path.cwd() / output_filename
        print(f"💾 Writing to: {output_path}")
        
        # Write file (using libx264 for high compatibility)
        final_clip.write_videofile(
            str(output_path), 
            codec="libx264", 
            audio_codec="aac",
            temp_audiofile='temp-audio.m4a', 
            remove_temp=True,
            fps=30
        )
        
        print("✅ Done!")
        return str(output_path)

    except Exception as e:
        print(f"❌ Error during concatenation: {e}")
        return None
        
    finally:
        # 3. Cleanup (Crucial for MoviePy to release file locks)
        print("🧹 Cleaning up resources...")
        for clip in loaded_objects:
            clip.close()
        if 'final_clip' in locals():
            final_clip.close()