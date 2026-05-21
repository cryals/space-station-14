#!/usr/bin/env python3
"""
Audio Diff Bot for Space Station 14 PRs.
Validates .ogg files against project requirements:
- Codec: Vorbis
- Sample rate: 44100 Hz
- Channels: 1 (mono)

Outputs a Markdown comment body and sets the 'has_errors' output.
"""

import json
import os
import subprocess
import sys

REQUIRED_SAMPLE_RATE = 44100
REQUIRED_CHANNELS = 1
REQUIRED_CODEC = "vorbis"

def run_ffprobe(filepath):
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {filepath}: {result.stderr}")
    return json.loads(result.stdout)

def analyze_file(filepath, owner, repo, head_sha):
    data = run_ffprobe(filepath)
    audio_stream = None
    for stream in data.get("streams", []):
        if stream["codec_type"] == "audio":
            audio_stream = stream
            break
    if not audio_stream:
        return None, "No audio stream found", None

    codec = audio_stream.get("codec_name", "unknown")
    sample_rate = int(audio_stream.get("sample_rate", 0))
    channels = int(audio_stream.get("channels", 0))
    bit_rate = data.get("format", {}).get("bit_rate", "N/A")
    duration = float(data.get("format", {}).get("duration", 0))

    preview_url = f"https://github.com/{owner}/{repo}/blob/{head_sha}/{filepath}"

    errors = []
    if codec != REQUIRED_CODEC:
        errors.append(f"Codec must be {REQUIRED_CODEC}, got {codec}")
    if sample_rate != REQUIRED_SAMPLE_RATE:
        errors.append(f"Sample rate must be {REQUIRED_SAMPLE_RATE} Hz, got {sample_rate}")
    if channels != REQUIRED_CHANNELS:
        errors.append(f"Channels must be {REQUIRED_CHANNELS} (mono), got {channels}")

    status = "Pass" if not errors else " ".join(errors)
    info = {
        "path": filepath,
        "preview_url": preview_url,
        "codec": codec,
        "sample_rate": sample_rate,
        "channels": channels,
        "bit_rate": bit_rate,
        "duration": duration,
        "status": status,
        "errors": errors
    }
    return info, None, preview_url

def build_comment(files_info, owner, repo, head_sha):
    rows = []
    has_errors = False
    for info in files_info:
        if info is None:
            continue
        if info["errors"]:
            has_errors = True
        preview_link = f"[Listen]({info['preview_url']})"
        row = (
            f"| `{info['path']}` "
            f"| {preview_link} "
            f"| {info['codec']} "
            f"| {info['sample_rate']} Hz "
            f"| {info['channels']} "
            f"| {info['bit_rate']} bps "
            f"| {info['duration']:.2f}s "
            f"| {info['status']} |"
        )
        rows.append(row)

    header = (
        "## Audio Diff Bot Report\n\n"
        "The following table summarizes the audio files changed in this PR.\n\n"
        "| Path | Preview | Codec | Sample Rate | Channels | Bitrate | Duration | Status |\n"
        "|------|---------|-------|-------------|----------|---------|----------|--------|\n"
    )
    body = header + "\n".join(rows) + "\n\n"
    if has_errors:
        body += "### Some files do not meet the audio requirements. "
        body += "Please fix them before this PR can be merged.\n"
    else:
        body += "All audio files comply with the project requirements.\n"

    return body, has_errors

def main():
    if len(sys.argv) < 3:
        print("Usage: audio_diff.py <added_files> <modified_files> [removed_files]")
        sys.exit(1)

    added = sys.argv[1].split() if sys.argv[1] else []
    modified = sys.argv[2].split() if sys.argv[2] else []

    all_files = added + modified
    owner = os.environ["GH_OWNER"]
    repo = os.environ["GH_REPO"]
    head_sha = os.environ["HEAD_SHA"]

    files_info = []
    for f in all_files:
        try:
            info, _, _ = analyze_file(f, owner, repo, head_sha)
            files_info.append(info)
        except Exception as e:
            print(f"::warning file={f}::{str(e)}")
            files_info.append({
                "path": f,
                "preview_url": "",
                "codec": "?",
                "sample_rate": "?",
                "channels": "?",
                "bit_rate": "?",
                "duration": 0,
                "status": f"Error reading file: {e}",
                "errors": [f"Error: {e}"]
            })

    comment_body, has_errors = build_comment(files_info, owner, repo, head_sha)

    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"comment_body<<EOF\n{comment_body}\nEOF\n")
        f.write(f"has_errors={'true' if has_errors else 'false'}\n")

if __name__ == "__main__":
    main()