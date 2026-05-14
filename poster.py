"""Social media video poster - YouTube Shorts & Instagram Reels."""

import argparse
import json
import sys
import os


def main():
    parser = argparse.ArgumentParser(description="Post videos to social media")
    subparsers = parser.add_subparsers(dest="command")

    # Post command
    post_parser = subparsers.add_parser("post", help="Post a video using a manifest")
    post_parser.add_argument("manifest", help="Path to post manifest JSON file")
    post_parser.add_argument("--platforms", help="Comma-separated platforms (default: all in manifest)")

    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Setup platform authentication")
    setup_parser.add_argument("platform", choices=["youtube", "instagram", "tiktok", "linkedin"])
    setup_parser.add_argument("--token", help="(unused, kept for compatibility)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "setup":
        run_setup(args)
    elif args.command == "post":
        run_post(args)


def run_setup(args):
    if args.platform == "youtube":
        from uploaders.youtube import authenticate
        authenticate()
        print("YouTube authentication complete!")
    elif args.platform == "instagram":
        from uploaders.instagram import authenticate
        authenticate()
        print("Instagram authentication complete!")
    elif args.platform == "tiktok":
        from uploaders.tiktok import authenticate
        authenticate()
        print("TikTok authentication complete!")
    elif args.platform == "linkedin":
        from uploaders.linkedin import authenticate
        authenticate()
        print("LinkedIn authentication complete!")


def run_post(args):
    with open(args.manifest) as f:
        manifest = json.load(f)

    # Resolve paths relative to the manifest directory
    manifest_dir = os.path.dirname(os.path.abspath(args.manifest))

    video_path = manifest["video"]
    if not os.path.isabs(video_path):
        video_path = os.path.join(manifest_dir, video_path)
    if not os.path.exists(video_path):
        print(f"Error: video not found: {video_path}")
        sys.exit(1)

    # Resolve thumbnail path if present
    thumbnail = manifest.get("thumbnail")
    if thumbnail and not os.path.isabs(thumbnail):
        thumbnail = os.path.join(manifest_dir, thumbnail)
    if thumbnail and not os.path.exists(thumbnail):
        print(f"  [warn] Thumbnail not found: {thumbnail}")
        thumbnail = None

    platforms = manifest.get("platforms", {})
    if args.platforms:
        selected = [p.strip() for p in args.platforms.split(",")]
        platforms = {k: v for k, v in platforms.items() if k in selected}

    results = {}
    for platform, config in platforms.items():
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
                video_url = config.get("video_url", video_path)
                mid = upload_reel(video_url, caption=config.get("caption", ""))
                results[platform] = {"success": True, "id": mid}
            elif platform == "tiktok":
                from uploaders.tiktok import upload
                tid = upload(
                    video_path,
                    description=config.get("description", ""),
                    privacy=config.get("privacy", "PUBLIC_TO_EVERYONE"),
                )
                results[platform] = {"success": True, "id": tid}
            elif platform == "linkedin":
                from uploaders.linkedin import post as linkedin_post
                text = config.get("text", "")
                pid = linkedin_post(text)
                results[platform] = {"success": True, "id": pid}
            else:
                print(f"  Platform '{platform}' not yet supported")
                results[platform] = {"success": False, "error": "not supported"}
        except Exception as e:
            print(f"  FAILED: {e}")
            results[platform] = {"success": False, "error": str(e)}

    print("\n" + "=" * 50)
    print("Results:")
    for p, r in results.items():
        mark = "OK" if r["success"] else "FAIL"
        print(f"  [{mark}] {p}: {r.get('id', r.get('error', ''))}")


if __name__ == "__main__":
    main()
