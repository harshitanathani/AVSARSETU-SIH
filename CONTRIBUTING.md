# Contributing to AvsarSetu

Thanks for wanting to contribute! This document explains how to set up the project locally, the workflow we use, and some small guidelines to keep contributions consistent.

Getting started

1. Fork the repository on GitHub and clone your fork:

```bash
git clone git@github.com:YOUR_GITHUB_USERNAME/avsarsetu.git
cd avsarsetu
```

2. Install dependencies

```bash
npm install
```

3. Create a `.env` file from `.env.example` and fill required values.

4. Start backend and frontend (two terminals)

```bash
node server.mjs
npm run dev
```

Branching

- Create a feature branch from `main`: `git checkout -b feat/short-description`
- Keep commits small and focused. Use conventional commit messages when possible.

Pull requests

- Open a PR against the `main` branch.
- Add a clear description of the change and any testing done.
- CI will run tests and linting (if configured).

Code style

- Use TypeScript for frontend files.
- Keep components small and reusable.

Reporting issues

- Open an issue describing the bug, including steps to reproduce and logs or screenshots if helpful.

Thank you for contributing — every improvement helps students find better internships and learn new skills!