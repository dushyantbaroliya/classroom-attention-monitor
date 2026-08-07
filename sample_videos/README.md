# Sample videos

## Included test footage

These clips are used to verify the pipeline end-to-end against real faces
(`python scripts/verify_pipeline.py --source sample_videos/classroom.mp4`):

| File | Purpose |
|---|---|
| `classroom.mp4` | Seated students: detection, tracking, attendance, scoring |
| `head-pose-face-detection-female-and-male.mp4` | Deliberate head turns: head pose, gaze and EAR stages |

Both are from Intel's [sample-videos](https://github.com/intel-iot-devkit/sample-videos)
repository, licensed **CC-BY-4.0** (© Intel Corporation, used with attribution).
They are gitignored; re-download them with:

```bash
BASE=https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master
curl -L -o sample_videos/classroom.mp4 $BASE/classroom.mp4
curl -L -o sample_videos/head-pose-face-detection-female-and-male.mp4 \
  $BASE/head-pose-face-detection-female-and-male.mp4
```

## Adding your own

Put classroom test videos here (`.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`) and
analyze them via the dashboard's **Upload video** button, or:

```bash
curl -X POST http://localhost:8000/video/upload \
  -F "file=@sample_videos/classroom.mp4"
```

## Where to get test footage

- Record your own (best): a laptop webcam pointed at 2–4 consenting people
  around a table is enough to exercise every feature (head pose, blinks,
  phone detection, hand raises).
- Public datasets of classroom/meeting scenes, e.g. search for
  "classroom lecture video dataset" or use meeting-style clips from
  [Pexels](https://www.pexels.com/search/videos/classroom/) (free license).

> Consent reminder: only analyze footage of people who have agreed to it.
> See the Ethics section of the main README.

## No video handy?

Seed the dashboard with a synthetic 10-minute session instead:

```bash
python scripts/seed_demo.py
```
