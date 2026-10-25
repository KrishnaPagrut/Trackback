# Demo film (the part after the skit)

`trackback-demo.mp4`: 1920x1080, ~2:41, silent. A title card (Trackback, the 2002 protocol revived) and twelve scenes built from real frames of the running app; each scene blurs and dims everything except the thing being talked about, and moves that focus as the subtitle advances. The subtitles are the script: the presenter reads them aloud (`TELEPROMPTER.md`). Earlier narrated cuts (Cartesia) were dropped as too robotic; `voice.py` and `words.py` remain if a voice track is wanted again. The storyboard and narration are in `../docs/VIDEO_SCRIPT.md` (scenes 1–5 as a story, 6–12 plain technical).

Rebuild:

```bash
make demo                                   # the app on :8000 (frames are captured from it)
backend/.venv/bin/python brag-output-2026-10-24-film/frames.py        # 1920x1080 frames of each beat
backend/.venv/bin/python brag-output-2026-10-24-film/voice.py <voice>  # Cartesia clips (CARTESIA_API_KEY in .env); `list` shows voices
# then trim/tempo the clips as in DECISIONS.md, or re-run the ffmpeg line there
python3 brag-output-2026-10-24-film/words.py                            # word timings for the captions (local whisper)
python3 brag-output-2026-10-24-film/build.py                            # writes composition/index.html and compositions/*.html
cd brag-output-2026-10-24-film/composition && npx hyperframes check && npx hyperframes render --quality delivery --output ../trackback-demo.mp4
```

`build.py` holds the storyboard: which frame each scene shows and when it cuts, the chapter label, the chips and the reconciliation pills in the top band, the spots, the end card. Narration lives in `narration.json`; durations are measured from the clips; captions use the script's words with the transcript's timings.
