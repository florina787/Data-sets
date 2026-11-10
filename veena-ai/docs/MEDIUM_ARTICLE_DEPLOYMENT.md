# I Shipped a Local AI Desktop App for $0. Here Is Every Deployment Decision — Including the Ones I Got Wrong

*How VEENA.AI went from "works on my machine" to tested installers for Windows, macOS and Linux, a live website and a release pipeline. Every failure, every trade-off, and everything I deliberately did not do.*

By Florina Regius

---

Most launch posts show the finished product. This one shows the plumbing.

VEENA is a private AI companion that runs entirely on your own computer: conversations, meeting notes, interview practice, answers from your documents with citations, and explanations of a screen or window you choose. No account, no subscription, no API key. The AI models run locally through Ollama.

Building the features was the fun part. Getting them **onto other people's computers** was a different problem, and it is the part almost nobody writes about honestly. So here is the full account: the architecture, the pipeline, the eleven things that broke, what I could have done and didn't, and what I refused to do on purpose.

Budget for all of it: **$0**.

---

## Part 1 — What actually has to be deployed

A "desktop AI app" sounds like one thing. It is really five, and each one ships differently:

| Piece | Technology | How it reaches the user |
| --- | --- | --- |
| The app window | Electron, React, TypeScript | Inside the installer |
| The brain | Python, FastAPI, SQLite, FAISS, faster-whisper | Frozen into a single executable with PyInstaller, inside the installer |
| The AI runtime | Ollama | **Not** in the installer: downloaded on first run, with consent |
| The AI models | Qwen 2.5 (text), Qwen3-VL (vision), Whisper (speech) | Downloaded on first run |
| The document-search model | all-MiniLM-L6-v2 | **Bundled** in the installer |
| The website | Static HTML/CSS/JS | GitHub Pages |

The single most important deployment decision was **what goes in the installer and what does not**.

### Decision 1: Don't bundle the AI runtime

Ollama for Windows is about **1.6 GB**; the models are another 1–4 GB. Bundling them would have pushed the installer past 3 GB. Instead the installer is the app only, and the setup wizard downloads the runtime on first launch, *with the user's permission*.

But "download a binary from the internet and run it" is exactly what malware does, so the runtime manager is strict:

- It **pins one version** (Ollama 0.40.11), not "latest". A surprise upstream release cannot break installs that worked yesterday.
- It hard-codes the **expected SHA-256 and byte size** of each official archive, copied from Ollama's own published checksum file, and refuses anything that does not match.
- It **reuses** an Ollama the user already has instead of installing a second copy.

### Decision 2: Do bundle the document-search model

The opposite call for the embedding model. It is small, every document feature depends on it, and downloading it on first use from Hugging Face failed intermittently in CI. Bundling it removed a whole class of "works sometimes" bugs.

**Lesson:** bundle what is small and critical, download what is huge and optional, and verify everything you download.

### Decision 3: Every default model must be commercially usable

My first defaults included models whose licences forbid commercial use. Fine for a hobby, fatal for a product. Every recommended model is now **Apache-2.0**, and a test fails the build if a non-commercial model ever becomes a default again. Deployment is also a legal act.

---

## Part 2 — The installers

| Platform | File | Size |
| --- | --- | --- |
| Windows 10/11, 64-bit | `VEENA.AI-Windows-Setup.exe` (NSIS) | ~570 MB |
| Mac with Apple Silicon | `VEENA.AI-macOS-AppleSilicon.dmg` | ~626 MB |
| Linux x86_64 | `VEENA.AI-Linux-x86_64.AppImage` | ~823 MB |

Why so big for an app that doesn't even contain its AI? The frozen Python backend carries CPU PyTorch for the embedding model, plus Whisper's runtime and FAISS. That is the honest cost of "works offline after setup".

**Stable file names** were a small decision with a big effect. The default electron-builder names include the version number, which breaks every "download" link the moment you release a new version. Fixed names mean a link like `releases/latest/download/VEENA.AI-Windows-Setup.exe` keeps working forever.

---

## Part 3 — The pipeline (GitHub Actions)

Everything runs on GitHub's free hosted runners. One workflow, these jobs:

1. **backend** — lint, format check and the deterministic Python test suite (models simulated, OCR and voice detection real).
2. **frontend** — type check, lint, unit tests, production build.
3. **security** — Python and npm vulnerability audits, a software bill of materials (CycloneDX) and a licence inventory.
4. **package** — a matrix on `windows-latest`, `macos-15` and `ubuntu-latest`. On *each* operating system:
   - freeze the backend with PyInstaller and smoke-test the frozen binary
   - build the real installer
   - **install it** on the fresh machine (silent NSIS install, mount the DMG and copy to /Applications, unpack the AppImage)
   - **launch the installed app**
   - **first run on a machine with no Ollama**: download the pinned runtime, verify its SHA-256, start it, pull a small model and get a **real model answer**, a **cited document answer** and **speech-to-text**
   - **uninstall** it
   - record the installer's SHA-256 and signature status
5. **draft-release** — only when I trigger it by hand: collect the three tested installers and a `SHA256SUMS.txt` into a **draft** GitHub release.

That fourth job is the one that matters. Most projects test the code; very few test **the thing the user actually downloads**, on a clean machine, all the way to a real AI answer. It caught most of the bugs below, every one of which would otherwise have been found by a user.

A fully green run on all three operating systems takes about 17 minutes (runs #19 and #32).

---

## Part 4 — Everything that broke (and the actual fix)

### 1. The macOS job never started
The macOS job sat in "queued" indefinitely while Windows and Linux finished. The generic macOS runner label wasn't getting a machine.
**Fix:** pin an explicit image, `macos-15`. **Lesson:** "queued forever" is a runner-label problem, not a code problem.

### 2. macOS build failed: "not a file"
electron-builder treated an **empty** signing-certificate variable as a path to a certificate. Unset secrets in GitHub Actions arrive as empty strings, not as "missing".
**Fix:** explicitly unset signing variables when they are empty, so the build falls back to ad-hoc signing.

### 3. Windows first run "hung" — but the app was fine
The first-run test started the backend with its output piped back to the test, and never read the pipe. Windows pipe buffers are small; once full, the backend **blocked on its own logging** and every request timed out. It looked exactly like an app bug.
**Fix:** write the backend log to a file. I proved it locally first.

### 4. The same bug, again, in a different test
Weeks later a second smoke test (`smoke_backend.py`) failed on Windows with a timeout on `/api/system/hardware`. Same root cause: an unread pipe. I had fixed the pattern in one file and not looked for it everywhere.
**Fix:** same, plus a longer timeout for the first hardware probe on a fresh Windows runner.
**Lesson:** when you find a class of bug, grep for the whole class.

### 5. Security audit failures from my own tooling
pip-audit flagged vulnerable versions of `filelock`, `setuptools` and later `lxml`. Pinning fixed the first two. Then the SBOM tool forced `lxml` *backwards*, reintroducing the vulnerability into the environment being audited.
**Fix:** run the security tools in **their own virtual environment**, so they can't change what they are auditing.

### 6. A vision model that wouldn't stop talking
On a full-screen capture, the small vision model could generate for minutes. **Fix:** cap OCR context and limit the answer length.

### 7. Speech recognition guessed "Japanese"
Short or quiet clips were sometimes detected as the wrong language and transcribed as gibberish. **Fix:** a fallback language when detection confidence is low.

### 8. The "thinking" model variant
One vision model tag produced long hidden reasoning before every answer, which is unusable on a CPU. **Fix:** use the `-instruct` variant explicitly.

### 9. Leftover model processes ran the machine out of memory
Runner processes from earlier tests stayed resident and the next test was OOM-killed. **Fix:** clean up model processes between heavy runs, and document it.

### 10. The release workflow I wasn't allowed to push
My first release design published releases automatically when CI passed. A safety check blocked pushing it, and it was right to: an automatic pipeline that makes a public release is one bug away from shipping a broken installer to everyone.
**Fix:** releases are **draft-only** and **manual**. CI builds and tests; a human looks at the draft and presses Publish. The job also refuses to overwrite an already-published release.

### 11. GitHub refused to deploy the website
The website workflow built fine, then the deploy job was rejected in two seconds, before it ran a single step. GitHub's `github-pages` environment, by default, only accepts deployments from the repository's **default branch**, and VEENA lives on a development branch.
**Fix:** add the branch under *Settings → Environments → github-pages → Deployment branches*. **Lesson:** a job that fails in two seconds with no steps is a permissions or protection rule, not your code.

---

## Part 5 — The website

The website is static HTML, CSS and a little JavaScript on GitHub Pages: free, HTTPS by default, no server.

Design rules I held to:

- **It never offers a download that doesn't exist.** The page asks GitHub's public API for the newest *published* VEENA release and only shows buttons for installer files actually attached to it. Until a release exists it says **"Public beta coming soon"**. A dead download button is the fastest way to lose a visitor's trust.
- **It detects the visitor's operating system** and offers the right installer first, with the others underneath.
- **No cookies, no trackers, no third-party scripts.** An automated browser test fails the build if any page contacts a host other than the site itself and GitHub's release API.
- **Deploys only by hand.** Every push builds and tests the site; publishing requires a manual run with "deploy" ticked.

The build checks, on every change:

- every local link and image exists
- media stays within a size budget
- no horizontal scrolling at phone (390 px), tablet (820 px) or desktop (1440 px) width
- no serious or critical accessibility violations (axe-core)
- any enabled download link actually returns the file
- the feedback form behaves as configured

That browser test found two real defects before launch: a decorative laptop graphic 13 px wider than a phone screen, and low-contrast decorative numerals.

---

## Part 6 — The demo videos, and the privacy bug I almost shipped

I wanted real demos, not mock-ups. So a script drives the **real app** with **real local models**: it types a question, uploads a sample document, shares a window, plays synthetic meeting speech through a fake microphone, answers an interview question, and records the whole session. Another script cuts it into clips.

Things that went wrong, in order:

1. **A mis-timed meeting clip.** The script waited for a heading called "Summary", but that heading exists *before* notes are generated. The clip would have shown "notes" that hadn't been written yet. I re-recorded and waited for the real signal instead.
2. **Slow hardware.** On a 4-core CPU with no GPU, one screen summary took about 3 minutes to start and 7 to finish. Model waits are shortened in the clips and long answers play faster, and **the website says so next to the clips**.
3. **Sped-up clips ended mid-answer.** At 40× speed, the last seconds showing the *finished* answer lasted less than one frame and were dropped. The fix: every clip ends with 2.5 seconds of the finished result at normal speed.
4. **The video ran about 1.7 seconds behind the script's timestamps**, so cuts landed on the wrong frames.
5. **The private photo.** The app's Home screen can show a personal photo that lives only on my computer and is never committed. The first second of one clip showed that screen.

I caught number 5 by looking at frames, which is not a process. So it became a test: a script reads **two frames per second of every clip** with OCR and fails if the Home screen appears anywhere, and the recorder now **refuses to run** while the photo is in the build. The clips that had already been pushed were checked too; none contained it.

**Lesson:** "I'll be careful" is not a privacy control. A test is.

---

## Part 7 — Feedback and analytics without spying on anyone

- **Feedback** uses a Google Form through its **documented pre-filled link**: the site's form fills in the answers, and the visitor presses Submit on Google's own page. I did not post to Google's undocumented form endpoints, and there is no email password or API key in the website's JavaScript (anything there is public).
- **Community** is GitHub Discussions. The "Join the conversation" link stays hidden until the build has asked GitHub's API whether Discussions is really on.
- **Analytics** — I measured what each tool can actually tell me before choosing:

| Number | Source | What it is not |
| --- | --- | --- |
| Visitors | Cloudflare Web Analytics, optional, cookieless | It can't count download clicks: no custom events, no query strings |
| Downloads | GitHub's own per-file `download_count` | Not people (repeat downloads count), not installs |
| Installs | **Not measured** | The app sends no install ping, by design |

---

## Part 8 — What I could have done, and didn't (yet)

This is the honest list. Each is a real gap, with the reason.

1. **Code signing and notarization.** The installers are unsigned (macOS is only ad-hoc signed and not notarized). Windows shows "Windows protected your PC" and macOS asks the user to allow the app in Privacy & Security. Fixing this needs paid certificates: Apple's Developer Program is a yearly fee, and Windows signing certificates are also paid. On a $0 budget I chose a clearly documented warning over a fake "free" workaround. It is the single biggest barrier to a wide public launch.
2. **Automatic updates.** VEENA *checks* for a newer release (once a day, only if allowed) and tells you. It does not download and install updates itself. Silent self-updating of an unsigned app would be a security liability.
3. **Intel Macs, ARM Linux and Windows on ARM.** Only Apple Silicon, x86_64 Linux and x64 Windows are built and tested.
4. **App stores and package managers** (Microsoft Store, Mac App Store, winget, Homebrew, Flathub). Each needs signing, review or packaging work, and they need the signed builds first.
5. **Smaller installers.** Replacing CPU PyTorch with a lighter embedding runtime would cut hundreds of megabytes.
6. **A custom domain.** The site lives at `github.io`. A domain costs money every year; GitHub Pages supports one when it's worth it.
7. **Crash reporting.** There is none. Users can export a log with secrets redacted, but nothing is collected automatically: a privacy-first product can't phone home by default.
8. **Lighthouse scores.** Accessibility is tested with axe-core in CI, but I have not yet measured Lighthouse, so I don't quote a score.
9. **An independent security audit.** There is an internal audit and automated scanning, but nobody independent has reviewed it, and the security policy says so.
10. **Merging to the default branch.** Everything ships from a development branch, through environment rules, until the work is reviewed and merged.

---

## Part 9 — What I deliberately did not do

These weren't oversights. They were decisions, and they're the ones I'm proudest of.

- **No automatic public releases.** CI builds a *draft*; a human publishes.
- **No fake download buttons.** If the file doesn't exist, the site says "coming soon".
- **No invented numbers.** The README's test count and every performance figure come from real runs; Lighthouse isn't quoted because it wasn't measured.
- **No fabricated demos.** Every clip is the real app, with its real mistakes left in. In the meeting clip the small model files an action item under "key takeaways" and the speech recognizer mishears a name. The page says so.
- **No secrets in the website.** Nothing that needs to stay private goes in public JavaScript.
- **No undocumented APIs.** Google Forms is integrated through its documented feature only.
- **No tracking.** No cookies, no fingerprinting, no install pings.
- **No claim of "fully offline".** Setup needs the internet; after setup the main features run offline, and the site says exactly that.
- **No personal photo in public**, enforced by a test rather than good intentions.

---

## Part 10 — If you're shipping your own local AI app

1. **Test the installer, not just the code**, on a clean machine, all the way to a real answer.
2. **Pin and checksum every binary you download at runtime.**
3. **Decide what to bundle by size × criticality.**
4. **Make releases a human decision.** Draft automatically, publish manually.
5. **Never show a download that doesn't exist.**
6. **When you find a bug, grep for its whole family.**
7. **Turn every "I'll remember to check" into a test** — links, sizes, layouts, accessibility, privacy.
8. **Say what you didn't do.** Users forgive an unsigned beta with clear instructions. They don't forgive surprises.

Total cost of everything above: $0, paid instead in CPU minutes, careful defaults and a lot of reading CI logs.

---

*VEENA.AI is open source under the GPL-3.0. Website: [florina787.github.io/Data-sets](https://florina787.github.io/Data-sets/) · Code: [github.com/florina787/Data-sets](https://github.com/florina787/Data-sets/tree/claude/amazing-babbage-qia83y/veena-ai)*

*© 2026 Florina Regius*
