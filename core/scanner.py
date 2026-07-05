import os


VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".wmv", ".mov", ".flv"}


def scan_videos(folder):
    print("\n========== SCANNER START ==========")
    print("INPUT FOLDER:", folder)

    if not os.path.exists(folder):
        print("❌ PATH NOT EXISTS")
        return []

    videos = []

    for root, dirs, files in os.walk(folder):
        print("SCAN:", root)

        for f in files:
            ext = os.path.splitext(f)[1].lower()

            if ext in VIDEO_EXTS:
                full = os.path.join(root, f)
                print("FOUND:", full)
                videos.append(full)

    print("TOTAL FOUND:", len(videos))
    print("========== SCANNER END ==========\n")

    return videos