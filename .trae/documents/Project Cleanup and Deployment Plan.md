I will help you organize the project, upload it to GitHub, and prepare it for Vercel deployment.

### 1. Organize Project Structure
I will reorganize the folders to make the project standard and easy to deploy:
- **Root**: Move `frontend` code to the root directory (required for Vercel).
- **`api/`**: Move `ml_backend` code to a new `api` folder (Vercel standard for Python backends).
- **`data/`**: Move data files here.
- **`docs/`**: Move documentation here.
- **Cleanup**: Remove temporary files (`.venv`, `__pycache__`, `node_modules`) and the empty `课设材料` folder.

### 2. Configure for Vercel
- Create `vercel.json` to configure the frontend (Vite) and backend (Python Flask) rewrites.
- Rename `app.py` to `index.py` in the `api` folder so Vercel can find the entry point.
- Update `api/requirements.txt` to optimize for Vercel (Note: The AI backend uses `torch` which is very large; Vercel has a 250MB size limit. I will configure it, but deployment might fail on the free tier. I'll try to use a lighter configuration).

### 3. GitHub Upload
- Initialize a Git repository.
- Create a `.gitignore` to exclude large data files (`*.ifc`, `*.rvt`, `*.zip`) and system files.
- Commit all code.
- Add your remote: `https://github.com/pingshengyanyuren-a11y/wesdom-screen.git`.
- Push the code (I will attempt to push; if authentication is needed, you may need to run the final push command).

### 4. Deployment
- Once pushed to GitHub, if your Vercel account is connected, it may auto-deploy.
- I will provide the `vercel.json` configuration to ensure it works.

Do you want me to proceed with these changes?