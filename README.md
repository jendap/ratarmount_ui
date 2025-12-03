# Ratarmount UI (GTK4/Gnome)
This is a simple GTK4 UI for Ratarmount. It works as standalone app as well as a Nautilus (GNOME Files) extension.

[Ratarmount](https://github.com/mxmlnkn/ratarmount) is fantastic ([fuse](https://en.wikipedia.org/wiki/Filesystem_in_Userspace) based) tool for mounting archives like .zip, .tar.zst and other formats.

Beware: At this time (December 2025) ratarmount can take quite a bit of memory. You are recommend to unmount once you're done with it! Sadly, that has to be done manually now.

## Installation

#### Ubuntu 25.10 Pre-requisites

```bash
sudo apt install -y gcc g++ liblz4-dev liblzo2-dev libzstd-dev pipx python3-dev python3-nautilus
pipx ensurepath
```

#### Fedora 43 Pre-requisites

```bash
sudo dnf install -y gcc g++ lz4-devel lzo-devel libzstd-devel pipx python3-devel nautilus-python
pipx ensurepath
```

**Open new terminal!** (`pipx ensurepath` may have added ~/.local/bin to $PATH)

### Common for all Linux distributions

```bash
pipx install ratarmount[full]

wget https://raw.githubusercontent.com/jendap/ratarmount_ui/refs/heads/main/ratarmount-ui.py -O ~/.local/bin/ratarmount-ui
chmod +x ~/.local/bin/ratarmount-ui

mkdir -p ~/.local/share/nautilus-python/extensions
ln -s ~/.local/bin/ratarmount-ui ~/.local/share/nautilus-python/extensions/ratarmount-ui
```


## Usage

### Standalone

Instead of `ratarmount ...` simply use `ratarmount-ui ...`.

### Nautilus extension

If you've run the commands above, you should now see a "Mount" option in the context menu of archives.


## Development

You don't need the .venv. It has only dev dependencies adding typing for gi.repository. You will need `sudo apt install -y libgirepository-2.0-dev` to run `uv sync`.

## TODO - Leave a star or send a pull request if you want to see any future updates!
-  [ ] Offer to upstream this into ratarmount repo (or create separete pip package?)
-  [ ] Use format detection from [ratarmountcore/formats.py](https://github.com/mxmlnkn/ratarmount/blob/7ab3fd8f185e5f7827172069013749f613357e73/core/ratarmountcore/formats.py#L396) or `Nautilus.FileInfo.get_mime_type()` instead of the current extension list. Used it to validate mount source file types in the ui too.
-  [ ] Drop parsing and make it use the argparse code from ratarmount itself
-  [ ] Add tab listing mounted archives and one click unmount them (all of them)
-  [ ] Add systemd-run to create cgroup to account and limit memory usage (and improve security?)
-  [ ] Option to automatically unmount after n seconds of inactivity (in ratarmnout itself)
-  [ ] Add progress bar (+ log window?)
-  [ ] Test(s)
-  [ ] Icon and .desktop file
-  [ ] Help, hints, translations and accessibility
-  [ ] Package to major distributions - ratarmount has to be upstreamed first
-  [ ] Should this follow [Gnome Human Interface Guidelines](https://developer.gnome.org/hig/)?
