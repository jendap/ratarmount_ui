# Ratarmount UI (GTK4/Gnome)

Mount archives like .zip, .tar.gz and many more as if they were disk! This is a Gnome / GTK4 (Linux) GUI for the fantastic [ratarmount](https://github.com/mxmlnkn/ratarmount). It works as standalone app as well as a Nautilus (Gnome Files) extension.


## Screenshots

#### Gnome Files Extension

<img width="1947" height="1336" alt="ratarmount_ui_nautilus.png" src="https://github.com/user-attachments/assets/2263f297-948c-4ba5-b27b-bcfcdbd9bd13" />

#### Ratarmount UI

<img width="1656" height="1264" alt="ratarmount_ui.png" src="https://github.com/user-attachments/assets/9d01496a-758e-4304-8e9c-b27ccaf4d7a6" />

#### Ratarmount UI Advanced

<img width="1656" height="1264" alt="ratarmount_ui_advanced.png" src="https://github.com/user-attachments/assets/6e3ea4d9-ee08-4373-9969-42d13230bc37" />

## Installation

### Install Ratarmount

<details>
<summary>Install Ratarmount Ubuntu 25.10</summary>
```bash
sudo apt install -y gcc g++ liblz4-dev liblzo2-dev libzstd-dev pipx python3-dev
pipx install ratarmount[full]
pipx ensurepath
```

**Open new terminal!** (`pipx ensurepath` may have added ~/.local/bin to $PATH)
</details>

<details>
<summary>Install Ratarmount Fedora 43</summary>
```bash
sudo dnf install -y gcc g++ lz4-devel lzo-devel libzstd-devel pipx python3-devel
pipx install ratarmount[full]
```
</details>

### Install the UI

```bash
wget https://raw.githubusercontent.com/jendap/ratarmount_ui/refs/heads/main/ratarmount-ui.py -O ~/.local/bin/ratarmount-ui
chmod +x ~/.local/bin/ratarmount-ui
```

### Install Gnome Files (Nautilus) extension

#### Ubuntu 25.10

```bash
sudo apt install -y python3-nautilus
wget https://raw.githubusercontent.com/jendap/ratarmount_ui/refs/heads/main/ratarmount-ui-nautilus.py -P ~/.local/share/nautilus-python/extensions/
```

#### Fedora 43

```bash
sudo dnf install -y nautilus-python
wget https://raw.githubusercontent.com/jendap/ratarmount_ui/refs/heads/main/ratarmount-ui-nautilus.py -P ~/.local/share/nautilus-python/extensions/
```


## Usage

### Standalone

Instead of `ratarmount ...` simply use `ratarmount-ui ...`.

### Gnome Files (Nautilus) extension

Run the commands above. You should now see a "Mount" option in the context menu of archives.

Note: It can be used as a nautilus script too (without python3-nautilus dependency): `ln -s ~/.local/bin/ratarmount-ui ~/.local/share/nautilus/scripts/'Mount...'`


## Memory Usage

Sadly ratarmount can take quite a bit of memory (as of December 2025). You are recommended to unmount once you're done with it.


## Development

You don't need the .venv. It has only dev dependencies adding typing for gi.repository. You will need `sudo apt install -y libgirepository-2.0-dev` to run `uv sync`.


## TODO - Leave a star or send a pull request if you want to see any future updates!
-  [ ] Offer to upstream this into ratarmount repo (or create separete pip package?)
-  [ ] Use format detection from [ratarmountcore/formats.py](https://github.com/mxmlnkn/ratarmount/blob/7ab3fd8f185e5f7827172069013749f613357e73/core/ratarmountcore/formats.py#L396) or `Nautilus.FileInfo.get_mime_type()` instead of the current extension list. Used it to validate mount source file types in the ui too.
-  [ ] Hints, translations (+help and accessibility)
-  [ ] Simple progress bar (log window in advanced expander) (ratarmount as library or upstream support needed)
-  [ ] Make sure .sqlite files are going to ~/.cache + auto-expire policy (in ratarmount itself?)
-  [ ] Drop parsing and make it use the argparse code from ratarmount itself
-  [ ] Icon and .desktop file
-  [ ] Test(s)
-  [ ] Package to major distributions - ratarmount has to be upstreamed first
-  [ ] Should this follow [Gnome Human Interface Guidelines](https://developer.gnome.org/hig/)? Use [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.8/widget-gallery.html)?
-  [ ] Option to automatically unmount after n seconds of inactivity (in ratarmnout itself)
-  [ ] Add list of mounted archives (to a tab?) and one click unmount them (all of them)
-  [ ] Add systemd-run to create cgroup to limit memory usage (and improve security?)
