# The Node Modules

A beautiful, native GNOME & Libadwaita application to scan, explore, and clean up heavy `node_modules` folders to instantly reclaim your disk space.

The project is currently available at: **[0x1da49.com/0x8h](http://0x1da49.com/0x8h)**

---

## ✨ Features

* **Lightning Fast concurrent scanning** using non-blocking background threads.
* **Disk Analytics** displaying partition capacities, free space, and Node Modules occupancy ratios.
* **Dual Cleanup & Project Explorer Views**:
  * **Cleanup View**: Select and purge heavy `node_modules` in bulk to reclaim storage.
  * **Node Install Products**: A secondary directory tree of your discovered Node projects showing whether their dependencies are actively installed or clean.
* **Fluid GNOME Native UI** powered by GTK4 & Libadwaita.

---

## 🛠️ Build & Install Locally

To build and run the Flatpak application on your system:

```bash
# Rebuild and install the Flatpak package
flatpak-builder --force-clean --user --install build-dir com.x1da49.thenodemodules.json

# Launch the application
flatpak run com.x1da49.thenodemodules
```
