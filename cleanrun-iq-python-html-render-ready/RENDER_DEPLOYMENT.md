# Deploying CleanRun IQ on Render

## Blueprint deployment

1. Put `app.py`, `index.html`, `render.yaml`, `requirements.txt`, and the
   `assets/` directory at the root of the GitHub repository.
2. In Render, choose **New → Blueprint** and select the repository.
3. Render will read `render.yaml`, compile the Python file, and run `python app.py`.

## Existing Render service

If you keep the existing Web Service, change its settings to:

- Runtime: **Python 3**
- Root Directory: blank when `app.py` is in the repository root
- Build Command: `python -m compileall app.py`
- Start Command: `python app.py`
- Health Check Path: `/api/health`

Remove `bun install && bun run build`; this project has no `package.json` and
does not use Bun or Node.js.

## Persistent data

Without a Render persistent disk, `cleanrun_data.json` is ephemeral and may be
reset during restarts or deployments. With a disk mounted at `/var/data`, add:

`CLEANRUN_DATA_FILE=/var/data/cleanrun_data.json`

as an environment variable in the Render service.
