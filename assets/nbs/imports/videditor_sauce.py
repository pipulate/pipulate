import os
from pathlib import Path
from moviepy import VideoFileClip, concatenate_videoclips

def concatenate_videos(source_directory: str, output_filename: str = "output.mp4") -> str:
    """
    Scans a directory for video files, sorts them by name, concatenates them, and saves the result.
    
    Args:
        source_directory (str): Path to the directory containing video clips.
        output_filename (str): Name of the output file (saved in current directory).
        
    Returns:
        str: The absolute path to the created video file, or None if failed.
    """
    source_path = Path(source_directory)
    if not source_path.exists() or not source_path.is_dir():
        print(f"❌ Source directory not found: {source_directory}")
        return None

    # Auto-discover and sort video files
    video_extensions = {'.mov', '.mp4', '.mkv', '.avi'}
    video_files = sorted([
        p for p in source_path.iterdir() 
        if p.suffix.lower() in video_extensions
    ])
    
    if not video_files:
        print(f"❌ No video files found in {source_directory}")
        return None

    print(f"🎬 Starting video concatenation from: {source_directory}")
    print(f"   Found {len(video_files)} clips:")
    for v in video_files:
        print(f"   - {v.name}")
    
    valid_clips = []
    loaded_objects = [] # Keep track to close them later

    # 1. Loading
    for path_obj in video_files:
        try:
            print(f"  -> Loading: {path_obj.name}")
            clip = VideoFileClip(str(path_obj))
            print(f"     -> Resolution: {clip.size}")
            loaded_objects.append(clip)
            valid_clips.append(clip)
        except Exception as e:
            print(f"❌ Error loading {path_obj}: {e}")

    if not valid_clips:
        print("⚠️ No valid clips to process.")
        return None

    # 2. Concatenation
    try:
        print(f"🔗 Concatenating {len(valid_clips)} clips...")
        # method="compose" prevents scrambling when resolutions differ
        final_clip = concatenate_videoclips(valid_clips, method="compose") 
        
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