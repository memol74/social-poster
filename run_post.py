"""Run a post from a posts/ folder.

Usage:
    py run_post.py posts/my_post/           # post to all platforms
    py run_post.py posts/my_post/ --only instagram
    py run_post.py posts/my_post/ --only youtube,instagram

Workflow:
  1. Reads post.json from the folder
  2. For Instagram: uploads video directly to Meta, posts reel
  3. For YouTube: uploads video directly via API
"""

import argparse
import json
import os
import sys

# truststore for corporate SSL — harmless on personal laptop
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser(description="Run a post from a posts/ folder")
    parser.add_argument("folder", help="Path to the post folder (e.g. posts/my_post/)")
    parser.add_argument("--only", help="Comma-separated platforms (default: all)")
    args = parser.parse_args()

    # Load post.json
    post_file = os.path.join(args.folder, "post.json")
    if not os.path.exists(post_file):
        print(f"Error: {post_file} not found")
        sys.exit(1)

    with open(post_file) as f:
        post = json.load(f)

    video_path = os.path.join(args.folder, post["video"])
    if not os.path.exists(video_path):
        print(f"Error: video not found: {video_path}")
        sys.exit(1)

    platforms = post.get("platforms", {})
    if args.only:
        selected = [p.strip() for p in args.only.split(",")]
        platforms = {k: v for k, v in platforms.items() if k in selected}

    if not platforms:
        print("No platforms to post to.")
        sys.exit(1)

    # Resolve thumbnail path if present
    thumbnail = post.get("thumbnail")
    if thumbnail:
        thumbnail = os.path.join(args.folder, thumbnail)
        if not os.path.exists(thumbnail):
            print(f"  [warn] Thumbnail not found: {thumbnail}")
            thumbnail = None

    # Always post YouTube first, then others
    ordered = sorted(platforms.keys(), key=lambda p: (0 if p == "youtube" else 1))

    # If Instagram is in the list, ask for token first
    ig_token_override = None
    if "instagram" in platforms:
        print("\n>> Instagram posting:")
        token_input = input("   Paste your Instagram access token (or press Enter to use saved token, 'skip' to skip): ").strip()
        if token_input.lower() == "skip":
            del platforms["instagram"]
            ordered = [p for p in ordered if p != "instagram"]
            print("   Skipping Instagram.")
        elif token_input:
            ig_token_override = token_input

    results = {}
    for platform in ordered:
        config = platforms[platform]
        print(f"\n>> Posting to {platform}...")
        try:
            if platform == "youtube":
                from uploaders.youtube import upload
                vid = upload(
                    video_path,
                    title=config["title"],
                    description=config.get("description", ""),
                    tags=config.get("tags", []),
                    privacy=config.get("privacy", "public"),
                    thumbnail=thumbnail,
                )
                results[platform] = {"success": True, "id": vid}

            elif platform == "instagram":
                from uploaders.instagram import upload_reel
                mid = upload_reel(video_path, caption=config.get("caption", ""), token=ig_token_override)
                results[platform] = {"success": True, "id": mid}

            elif platform == "tiktok":
                from uploaders.tiktok import upload
                tid = upload(
                    video_path,
                    description=config.get("description", ""),
                    privacy=config.get("privacy", "PUBLIC_TO_EVERYONE"),
                )
                results[platform] = {"success": True, "id": tid}

            else:
                print(f"  Skipping unknown platform: {platform}")
                results[platform] = {"success": False, "error": "unknown"}

        except Exception as e:
            print(f"  FAILED: {e}")
            results[platform] = {"success": False, "error": str(e)}

    # Summary
    print("\n" + "=" * 50)
    print("Results:")
    for p, r in results.items():
        mark = "OK" if r["success"] else "FAIL"
        print(f"  [{mark}] {p}: {r.get('id', r.get('error', ''))}")


if __name__ == "__main__":
    main()
