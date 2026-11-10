# Feedback, community and analytics: owner setup

The website ships with all three switched **off**. Each one is turned on by putting a value you created into
`veena-ai/site/config.js`. The website build (`site/build.sh`, run by CI) refuses a value it cannot verify,
and anything that looks like a password or API key.

| Feature | Today | Turned on by | Cost |
| --- | --- | --- | --- |
| Feedback form | Shown, but disabled with "being set up" | `feedback.formUrl` + `feedback.entries` | Free (Google account) |
| Community link ("Join the conversation", footer "Community") | **On** (Discussions verified enabled) | `discussionsEnabled: true` | Free |
| Visitor counts | Off; no analytics script | `cloudflareToken` | Free (Cloudflare account) |
| Download totals | Works now, needs no setup | `python site/tools/release_downloads.py` | Free |

Nothing here needs a paid plan, a server or a secret on the website.

---

## 1. Feedback form (Google Forms + Google Sheets)

The website does **not** post to Google directly: that would need undocumented endpoints. Instead it uses the
documented **pre-filled link** feature. A visitor fills in the VEENA-styled form, VEENA opens your Google Form
in a new tab with the answers filled in, and the visitor presses **Submit** there.

### 1.1 Create the form (about 5 minutes)

At <https://forms.google.com>, signed in to the Google account that should own the feedback:

1. Create a blank form titled **VEENA feedback**.
2. Add these questions **in this order**, using exactly these option labels (the website sends them as text):
   1. **How was your experience?** · *Multiple choice* · options `Excellent`, `Good`, `Needs improvement` · Required
   2. **What is it about?** · *Multiple choice* · options `General feedback`, `Feature request`,
      `Bug or installation issue`, `Other` · Required
   3. **Your message** · *Paragraph* · Required
   4. **Email (optional, for a reply)** · *Short answer* · not required
   5. *(optional)* **Source** · *Short answer* · not required (the site fills in `website` and any campaign label)
3. **Settings → Responses:** leave **Collect email addresses** *off* (the optional question covers it), and
   leave **Limit to 1 response** *off* (that would force visitors to sign in to Google).
4. Add the short privacy line from the website as the form description:
   *"Used only to improve VEENA. Please don't include passwords or private documents. Email is optional."*

### 1.2 Send responses to Google Sheets

**Responses** tab → **Link to Sheets** (or ⋮ → **Select destination for responses**) → **Create a new
spreadsheet** → **Create**. Each response becomes a row in your sheet.
(Google help: "Choose where to save form responses", support.google.com/docs/answer/2917686.)

### 1.3 Email notification for each response

**Responses** tab → ⋮ (More) → **Get email notifications for new responses**. Google emails the form owner's
address; nothing about your email goes into the website. Check the option name in your Google Forms; Google
sometimes moves it.

### 1.4 Connect the website

1. In the form: ⋮ → **Get pre-filled link**. Type a placeholder into every question (e.g. pick `Good`, type
   `MSG`, `EMAIL`, `SRC`), then **Get link** → **Copy link**.
2. The copied link looks like
   `https://docs.google.com/forms/d/e/<FORM-ID>/viewform?usp=pp_url&entry.1234567=Good&entry.2345678=...`
   Each `entry.<number>` belongs to one question, in order.
3. Edit `veena-ai/site/config.js`:

   ```js
   feedback: {
     formUrl: "https://docs.google.com/forms/d/e/<FORM-ID>/viewform",
     entries: { experience: "entry.1234567", type: "entry.2345678", message: "entry.3456789",
                email: "entry.4567890", page: "entry.5678901" },   // email and page may stay null
   },
   ```

4. Commit. CI's website build checks the format; `node site/tools/site_check.mjs` tests the hand-off in a browser.
5. Before announcing it, send yourself one real test response from the website and confirm the row appears in
   the sheet and the notification email arrives.

The form ID is not secret: it is in every public link to the form.

---

## 2. Community: GitHub Discussions

**Done 2026-11-10:** the owner enabled Issues, Discussions and Pages (GitHub API: `has_issues`,
`has_discussions` and `has_pages` all `true`), and `discussionsEnabled` is now `true` in `site/config.js`.
Remaining: the categories and the pinned welcome post (2.2 and 2.3).

### 2.1 Turn them on

**Settings → General → Features**: tick **Issues** and **Discussions**. (Issues matter too: the release
notes, `CONTRIBUTING.md` and `docs/SUPPORT_AND_TROUBLESHOOTING.md` point people to GitHub Issues, and those
links are dead while Issues is off.)

### 2.2 Categories

**Discussions → Categories (pencil icon)**. Edit the defaults or add new ones so the list reads:

| Category | Format | Description |
| --- | --- | --- |
| 📣 Announcements | Announcement | Releases and news from the VEENA team. Only maintainers post. |
| 💬 General Discussion | Open-ended discussion | Talk about VEENA, local AI and how you use it. |
| 💡 Feature Requests | Open-ended discussion | Ideas for VEENA. Upvote the ones you want. |
| ✨ Product Feedback | Open-ended discussion | What works, what doesn't, what surprised you. |
| 🛟 Support & Issues | Question / Answer | Installation and usage help. Mark the answer that solved it. |

The repository already contains form templates in `.github/DISCUSSION_TEMPLATE/` for **feature-requests**,
**product-feedback** and **support-issues**. GitHub matches a template to a category by the category's slug,
which is visible in the category's URL (`.../discussions/categories/<slug>`). If GitHub gives a category a
different slug, rename the template file to match.

### 2.3 Pinned welcome post

Create a discussion in **Announcements** with the text in
[`docs/community/WELCOME_DISCUSSION.md`](community/WELCOME_DISCUSSION.md), then **Pin discussion**.

### 2.4 Show the community links on the website

Set `discussionsEnabled: true` in `site/config.js`. The website build asks the GitHub API whether Discussions
is really on and fails if not, so the link can't go live early.

---

## 3. Visitor counts: Cloudflare Web Analytics (optional)

What Cloudflare documents (developers.cloudflare.com/web-analytics, checked 2026-11-10):

* "free, privacy-first analytics"; works on a site that does not use Cloudflare DNS or proxy, through a
  JavaScript beacon; "does not collect or use your visitors' personal data".
* It counts page views and visits and measures page performance.
* **No custom events** ("Not yet") and **no query strings or UTM parameters** ("do not log query strings").
  So it **cannot** count download clicks or campaigns. Use it for visitors, top pages and referrers only.
* Soft limit of ten sites per account.

Setup: Cloudflare dashboard → **Analytics & Logs → Web Analytics → Add a site** → enter
`florina787.github.io` → copy the token from the snippet (`"token": "…"`, 32 hex characters) → put it in
`cloudflareToken` in `site/config.js`. The site then loads `static.cloudflareinsights.com/beacon.min.js`.
Update the "This website" section of `site/privacy.html` to say analytics is on **in the same commit**.

---

## 4. What each number means

| Number | Source | What it is | What it is not |
| --- | --- | --- | --- |
| **Visitors / page views** | Cloudflare Web Analytics (once on) | Browsers that loaded a page | People; downloads |
| **Download clicks** | Not collected | Clicks on a download button | No tool records them today; see note |
| **Asset downloads** | GitHub `download_count` per release file (`site/tools/release_downloads.py`) | Completed file downloads | People (repeat downloads count) or installs |
| **Installs** | Not measured | | VEENA sends no install ping, by design |
| **Feedback** | Google Sheet rows | Responses people chose to send | A sample of all users |

Note on download clicks: the site raises a page-local `veena:download` event with `{os, version, campaign}` on
every download click, ready for an analytics tool that supports custom events. Nothing is sent today. A
campaign is a short label from a link you share, e.g. `…/Data-sets/?utm_campaign=linkedin-launch`. It is
only read when such a tool is added. Visitors are never fingerprinted, and no cookies or storage are used.

Run `python site/tools/release_downloads.py` (add `--json` for a spreadsheet) after a release is published.
Before then it reports that there is no published release.
