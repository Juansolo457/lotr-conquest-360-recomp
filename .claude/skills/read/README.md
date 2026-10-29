# read

by rook

`read` is a skill for your AI agent. It gives the agent three habits for moments when a quick answer looks right and is wrong:

1. **Contracts.** Before it sends a body to an API or a form it has not read, it finds the contract the page declares and quotes it.
2. **Cuts.** Before it shortens a text you gave it, it writes a keep list, counts with a script, and shows you every cut.
3. **Newest names.** When you ask it to name the newest model or product, it writes its memory answer and how sure it is, then checks a live page and cites it.

The folder uses the Agent Skills format: a folder with a `SKILL.md` file, which Claude Code, Cursor and Codex read.

## What is in the folder

| File | What it does |
|---|---|
| `SKILL.md` | The rules your agent follows, with a check or a question for each and what "done" looks like. |
| `scripts/find-contract.mjs` | Fetches a page, or reads a saved one, and lists the contracts it declares: `service-desc`, `describedby` and `service-doc` links, JSON or YAML alternates, and each form with its fields and limits. |
| `scripts/cut-diff.mjs` | Compares an original text with a short version. It counts characters and words against a limit, checks that each keep passage is still there character for character, and lists every sentence that was cut. |
| `README.md` | This file. |

The scripts need Node.js 18 or newer. There is nothing to install: no packages and no dependencies.

## Install

Copy the whole `read` folder and keep its name. The folder name must match `name: read` in `SKILL.md`.

**Claude Code**
- One project: `<project>/.claude/skills/read/`
- Every project: `~/.claude/skills/read/`

Start a new session so Claude Code loads the skill.

**Cursor, Codex and other agents that read skill folders:** put the `read` folder in the skills folder named in that agent's own documentation, then start a new session.

**An agent without skill folders:** paste the text of `SKILL.md`, without the part between the two `---` lines, into the agent's instructions file, for example `AGENTS.md`, and keep the `scripts/` folder in the project.

## Check that it works

1. **The scripts run.** From your project folder (Claude Code path shown):

   ```
   node .claude/skills/read/scripts/cut-diff.mjs --self-test
   node .claude/skills/read/scripts/find-contract.mjs --self-test
   ```

   Each prints `self-test ok`. Neither one uses the network.
2. **A real try.** In a new session, paste three or four paragraphs and ask: "Shorten this to 400 characters. Keep the second paragraph exactly as written." The agent should write a keep list, run `cut-diff.mjs`, and show you the counts and the cut list before it gives you the short version.

## Safety

- `find-contract.mjs` sends one GET request to the URL you give it, and with `--open` one GET for each contract it lists. It sends no body, no cookies and no keys. With `--open` it skips a contract on a local or private address, such as `localhost` or `192.168.x.x`, unless the page itself is on that host.
- `cut-diff.mjs` uses no network.
- Both scripts read files only inside the folder you run them from. For a file anywhere else, they stop and tell the agent to ask you first.
- Neither script writes, installs or deletes anything.
