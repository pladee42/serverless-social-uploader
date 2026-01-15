# Contributing to Universal Social Media Uploader

First off, thank you for considering contributing! 🎉

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues. When creating a bug report, include:

- **Clear title** describing the issue
- **Steps to reproduce** the behavior
- **Expected behavior** vs actual behavior
- **Platform** (YouTube, TikTok, Facebook, Instagram)
- **Error messages** (if any)

### Suggesting Features

Feature suggestions are welcome! Please open an issue with:

- **Use case** — What problem does this solve?
- **Proposed solution** — How should it work?
- **Platform** — Which platform(s) does this affect?

### Pull Requests

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test locally with `uvicorn main:app --reload`
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/pladee42/serverless-social-uploader.git
cd serverless-social-uploader

# Create environment
conda create -n social-mng python=3.14 -c conda-forge
conda activate social-mng

# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn main:app --reload --port 8080
```

## Code Style

- Use [Black](https://github.com/psf/black) for formatting
- Use type hints where possible
- Add docstrings to functions and classes
- Keep functions focused and small

## Adding a New Platform

1. Create `platforms/newplatform.py` with upload logic
2. Add credential types and secret keys
3. Integrate into `main.py` dispatcher
4. Create `tools/get_newplatform_token.py` helper
5. Update `README.md` with authentication docs
6. Test with dry run before actual upload

## Questions?

Feel free to open an issue for any questions!

---

Thank you for contributing! 🙏
