# The Node Modules Finder

A beautiful, native GNOME & Libadwaita application to scan, explore, and clean up heavy `node_modules` folders to instantly reclaim your disk space.

The project is officially hosted at: **[0x1da49.com/0x6g](http://0x1da49.com/0x6g)**

---

## 🚀 Quick Installation

You can install the standalone, secure Flatpak bundle directly on any Linux distribution in two ways:

### Option 1: One-Click Terminal Install (Recommended)
Copy and paste this single command into your terminal to automatically download and install the latest release:

```bash
curl -L -o com.x1da49.thenodemodules.flatpak https://github.com/abubakerx1da49/0x6g-the-node-modules/releases/latest/download/com.x1da49.thenodemodules.flatpak && flatpak install --user ./com.x1da49.thenodemodules.flatpak
```

### Option 2: Graphical Install
1. Download the standalone bundle from our [GitHub Releases](https://github.com/abubakerx1da49/0x6g-the-node-modules/releases) (the `.flatpak` asset).
2. **Double-click** the downloaded file to launch your system's App Store (GNOME Software / Discover) and click **Install**.

---

## ✨ Features

* **Lightning Fast concurrent scanning** using non-blocking background threads.
* **Disk Analytics** displaying partition capacities, free space, and Node Modules occupancy ratios.
* **Dual Cleanup & Project Explorer Views**:
  * **Cleanup View**: Select and purge heavy `node_modules` in bulk to reclaim storage.
  * **Node Install Products Explorer**: A secondary list showing all Node projects (`package.json`) and their active installation status.
* **Fluid GNOME Native UI** built strictly on GTK4 & Libadwaita following HIG guidelines.

---

## 🛠️ Local Development & Build

To compile and run the application locally on your machine:

```bash
# Build and install the Flatpak package locally
flatpak-builder --force-clean --user --install build-dir com.x1da49.thenodemodules.json

# Launch the application
flatpak run com.x1da49.thenodemodules
```
