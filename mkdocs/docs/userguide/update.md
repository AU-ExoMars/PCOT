# Updating PCOT

Updating an existing PCOT install should be fairly simple.

* Go into the PCOT root directory - this is the directory which contains
PCOT on your machine, and is usually called `PCOT`.
It should contain directories called `src` and `tests`.
* Type `git pull` - this should get the latest release
* Type `poetry install` - this should check for any updated packages and download them

## Important: updating to 1.0.0 LITTLE DENNIS

**Updating to the 1.0.0 LITTLE DENNIS release is not this simple.** This release migrates
PCOT from PySide2 (Qt5) to PySide6 (Qt6), which also requires a more recent Python version (3.11),
so you will need to rebuild your Conda environment completely rather than just running
`poetry install` in the existing one.

Follow these instructions while inside the PCOT directory instead of the steps above:

* `git pull` to pull the latest version (if you haven't done so already)
* `conda deactivate` to deactivate any existing environment
* `conda env remove -n pcot` to delete the old environment
* `conda create -n pcot python=3.11 poetry` to create a new environment with Poetry and the right Python version
* `conda activate pcot` to switch to the new environment
* `poetry install` to install PCOT

See the [1.0.0 LITTLE DENNIS release notes](../releases.md#100-2026-09-16-little-dennis)
for the full details, including a fix for `poetry install` errors caused by Python picking up your
system install instead of the Conda sandbox.

