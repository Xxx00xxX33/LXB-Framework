# LXB-WebConsole

Flask-based control console for LXB-Framework.

## Scope
LXB-WebConsole is the unified UI shell for:
- command debugging,
- map building and map inspection,
- Cortex route and task execution.

## Entry
- Main shell: `http://localhost:5000/`
- Internal pages are hosted inside the shell.

## Internal Pages
- `Command Studio` (`/command_studio`)
- `LXB-MapBuilder` (`/map_builder`)
- `Map Viewer` (`/map_viewer`)
- `LXB-Cortex` (`/cortex_route`)

## Shared Navigation + Connection
The shell (`index.html`) owns shared top navigation and global connection controls.

## Start
```bash
cd web_console
python app.py
```

## Key Backend Routes
Page routes:
- `/`
- `/command_studio`
- `/map_builder`
- `/map_viewer`
- `/cortex_route`

Core API groups:
- `/api/connect`, `/api/disconnect`, `/api/status`
- `/api/command/*`
- `/api/explore/*`, `/api/maps/*`
- `/api/cortex/*`

## Frontend Files
- `templates/index.html`
- `templates/command_studio.html`
- `templates/map_builder.html`
- `templates/map_viewer.html`
- `templates/cortex_route.html`
- `static/js/main.js`

## Cross References
- `docs/zh/lxb_web_console.md`
- `docs/en/lxb_web_console.md`
