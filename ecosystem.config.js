module.exports = {
  apps: [
    {
      name: "candidate_bot",
      script: "candidate_bot.py",
      interpreter: ".venv/bin/python", // для Linux/Mac
      // interpreter: ".venv\\Scripts\\python.exe", // для Windows
      interpreter_args: "-u",
      watch: true,
      autorestart: true,
    },
    {
      name: "recruiter_bot",
      script: "recruiter_bot.py",
      interpreter: ".venv/bin/python", // для Linux/Mac
      // interpreter: ".venv\\Scripts\\python.exe", // для Windows
      interpreter_args: "-u",
      watch: true,
      autorestart: true,
    }
  ]
}
