# **Setup**

## **Table of Contents**
- [Environment Setup](#environment-setup)
  - [Conda](#conda)
  - [Package Installation](#package-installation)
  - [VSCode](#vscode)
  - [Jupyter Notebook](#jupyter-notebook)

---

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

### Jupyter Notebook
Run Jupyter Notebooks within your Conda environment:
1. Install the Jupyter extension in VSCode.
2. Open a notebook and select the desired kernel.
