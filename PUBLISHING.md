# Publishing Guide

## 1. Create a Git repository

```bash
cd jenkins-build-mcp
git init
git add .
git commit -m "Initial release"
```

## 2. Push to GitHub

```bash
git remote add origin https://github.com/<your-org>/jenkins-build-mcp.git
git branch -M main
git push -u origin main
```

## 3. Let others install from Git

```bash
pip install git+https://github.com/<your-org>/jenkins-build-mcp.git
```

Or pin a tag:

```bash
pip install git+https://github.com/<your-org>/jenkins-build-mcp.git@v0.2.0
```

## 4. Optional: build a wheel for internal distribution

```bash
pip install -e ".[dev]"
python -m build
```
