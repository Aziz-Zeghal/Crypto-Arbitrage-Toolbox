# **Setup**

## **Table of Contents**

- [Configuration](#configuration)
    - [Conda](#conda)
    - [Package Installation](#package-installation)
    - [VSCode](#vscode)
- [Usage](#usage)
    - [API keys](#api-keys)
    - [Jupyter Notebook](#jupyter-notebook)
    - [Scripts](#scripts)


---

## Configuration
### Conda
Set up the environment using Conda:
```
conda env create -f conda_env.yaml
```
Export the environment:
```
conda env export --name sandbox > conda_env.yaml
```

### Package Installation
The project can be packaged using `pyproject.toml`:
```
python -m build
pip install -e .
```

### VSCode
Use VSCode for development:
1. Open the command palette (`Ctrl+Shift+P`).
2. Select "Python: Select Interpreter".
3. Choose the appropriate Conda environment.

For logs, I recommend the `ANSI Color Code` to remove the escape characters.

## Usage
### API keys
I use a keys.py file to store API keys. This file is not included in the repository.

To use it, create a file in the root directory (and the script folder) called `keys.py` and add the following:
```python
# -------------------------------Bybit key-------------------------------
bybitPKey = "XXX"
bybitSKey = "XXX"
# -------------------------------Bybit key-------------------------------

# -------------------------------Bybit Demo Trading key------------------
demobybitPKey = "XXX"
demobybitSKey = "XXX"
# -------------------------------Bybit Demo Trading key------------------
```

The Bybit testnet is not that useful.

### Jupyter Notebook
Run Jupyter Notebooks within your Conda environment:
1. Install the Jupyter extension in VSCode.
2. Open a notebook and select the desired kernel.


### Scripts
There is a folder with scripts for small tasks and testing.
They contain a logger and a main function. To run them:

```bash
nohup python <script>.py &
```

This puts the script in the background and detaches it from the terminal. To stop logging in `nohup.out use:
```bash
nohup python <script>.py > /dev/null 2>&1 &
```

I use nohup because it is most lightweight compared to systemd, screen, tmux, or Docker images.