# Port Viewer

[![Tests](https://github.com/huzaifanur/port-viewer/actions/workflows/tests.yml/badge.svg)](https://github.com/huzaifanur/port-viewer/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Port Viewer is a small native Linux app that shows which TCP and UDP ports are
in use and which process holds each one. It is the readable version of
`ss -tulpn` for developers and admins who just want to know what is sitting on
port 8080: search, filter by protocol, and optionally run a one-time admin scan
to see processes owned by other users. It uses GTK 4 and libadwaita and follows
the system light or dark theme.

**Install:** `git clone` and `./install.sh` (Ubuntu, see below) · **License:** MIT

## Features

- Lists bound TCP and UDP ports, addresses, states, process names, and PIDs
- Filters by search text or protocol
- Handles IPv4, IPv6, wildcard, and interface-scoped bindings
- Offers an optional administrator scan for process details hidden by Linux
- Includes a native desktop launcher and scalable icon
- Scans asynchronously so the interface remains responsive

## Install on Ubuntu

Install the runtime dependencies:

```sh
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 iproute2 policykit-1 desktop-file-utils
```

Clone and install for the current user:

```sh
git clone https://github.com/huzaifanur/port-viewer.git
cd port-viewer
./install.sh
```

Port Viewer will appear in the desktop application menu. The installer places
files only under `~/.local` (or the configured XDG user directories).

## Run from source

```sh
./bin/port-viewer
```

The shield button performs a one-time administrator scan. Authentication is
optional, but it allows Linux to reveal processes belonging to other users.

## Tech stack

Python 3, PyGObject with GTK 4 and libadwaita, and iproute2's `ss` for the
data. The optional admin scan runs `ss` through `pkexec` (polkit).

## How it works

`port_viewer/scanner.py` runs `ss -H -lntup` without a shell and parses its
output into port entries (protocol, port, address, state, process, PID).
`port_viewer/app.py` is the GTK window; scans run off the main thread so the
interface stays responsive.

## Testing

```sh
python3 -m unittest discover -s tests -v
```

The parser tests run in GitHub Actions on every push and pull request.

## Contributing

Issues and pull requests are welcome. Please include parser tests when adding
support for new `ss` output formats.

## License

[MIT](LICENSE)

Author: Huzaifa Nur — https://www.huzaifanur.com
