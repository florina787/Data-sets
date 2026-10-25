# Google AI Edge Foresight: Official Feature Set, Requirements, Models, Licensing and Privacy (as of 25 Oct 2026)

Source key:
- **[OFFICIAL]** means Google's own pages: the product page at developers.google.com/edge/foresight, which renders inside an iframe at the `/frame/edge/foresight/...` URL cited below, and the Google Developers Blog.
- **[PRESS]** means third-party reporting.
- **[BUNDLE]** means my own inspection of the public installer `https://dl.google.com/foresight-mac/foresight_mac.dmg`, fetched 25 Oct 2026. I read Info.plist, the bundled component list, and strings in the main binary. These are technical observations, not Google statements. Treat them as indicative and verify them independently before relying on them.

Main official URLs:
- Product page (iframe content): https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame (wrapper page: https://developers.google.com/edge/foresight)
- Launch blog post: https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/

## 1. What Foresight does (features)

### Takeaway
Google officially describes Foresight as an experimental, on-device "intelligent notetaking" meeting companion for Mac. It does five things:
- turns shorthand into polished notes using the live transcript
- builds a local knowledge base from files, Google Drive and calendar
- answers questions through chat
- runs "Live Assistance", which detects spoken questions and auto-answers them with "context cards with exact citations"
- does cross-modal semantic search across images, documents, transcripts and notes

None of the sources I checked mention screen understanding or screen capture.

### Cited Findings
- **[OFFICIAL]** The page tagline is "Intelligent Notetaking Connected to Your Actual Work. Runs locally on your Mac • Works offline." — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[OFFICIAL]** "Automated Synthesis": "Google AI Edge Foresight listens in the background so you don't have to focus on taking detailed notes. Simply scribble shorthand bullets for things you want to remember, and Foresight enriches them into polished notes using the meeting transcript instantly." It "Works for video conferencing or face-to-face meetings." — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[OFFICIAL]** "Local Knowledge": "Simply point Google AI Edge Foresight to your project folders, reference materials, diagrams, and calendar. It automatically understands your work without needing to manually organize your files". The page also says "Easily connect your local folders and Google Drive with minimal setup" and "Understands documents, diagrams, web links, and calendar details." — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[OFFICIAL]** "Meeting Intelligence": "Whether it's through chat, or if you want Live Assistance for automatic answers…". The listed features are "Conversational retrieval and summary with your personal knowledge" and "Live Assistance can listen and automatically answer questions." — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[OFFICIAL]** Citations, from the FAQ: "When questions or topics from your imported files arise in conversation, Foresight displays proactive context cards with exact citations." — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[OFFICIAL]** Supported sources, from the FAQ: "PDFs, Google Docs, Microsoft Office formats, plain text, Markdown, and web bookmarks. You can tag sources with custom labels, filter by category, and semantically search across thousands of pages in milliseconds without cloud indexing." — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[OFFICIAL]** The blog lists two features:
  - "Enriches manual shorthand notes with details retrieved in real-time from your current meeting conversation"
  - "Easily find different types of media (images, documents, transcripts, and notes) using natural language."

  Its demo captions are "Automatic enhancement of shorthand notes" and "Questions detected and answered live by AI." — [Google Developers Blog, 6 Oct 2026](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/)
- **[PRESS]** The feature names "Live Notes Enhancement", "Ambient Audio Query Detection" and "Grounded Q&A" come from a 7 Oct 2026 post on X by Suril Shah, as reported by GIGAZINE. GIGAZINE says Shah called it a Google "Labs" app, described as "an ambient note-taking meeting companion and personal knowledge assistant for Mac." GIGAZINE also says the app can compare current meeting topics with past meetings. — [GIGAZINE](https://gigazine.net/gsc_news/en/20261009-google-ai-edge-foresight/)
- **[PRESS]** In a hands-on test with a simulated meeting, Android Authority found it "quickly and successfully" turned bullets into notes, and that it detected questions and answered them from the transcript. — [Android Authority, Akshay Gangwar, 7 Oct 2026](https://www.androidauthority.com/google-ai-edge-foresight-embedding-gemma-2-3719906/)
- **[PRESS]** eWeek says the knowledge library includes "past conversations, documents, and images", and that the app works independently of any conferencing platform, unlike Gemini notes in Meet. — [eWeek, Liz Ticong, 12 Oct 2026](https://www.eweek.com/news/google-ai-edge-foresight-mac/)
- **[BUNDLE]** The binary contains these strings:
  - UI strings "Add an entire Drive folder" and "Add files from Drive"
  - a function "Adds an event to the calendar (Google or Native)" (`AddCalendarEventIntentExecutor`)
  - a `refresh_calendar_events` background task
  - prompt text that tells the model to answer "based ONLY on the provided context (calendar entries, documents, meeting notes, transcripts, search results)" and that references `[Source:N]` citation tags
  - an `/export` route string

  These suggest calendar write actions and some export function, but I could not confirm either from official text. — inspection of [installer DMG](https://dl.google.com/foresight-mac/foresight_mac.dmg)

### Inferences
- Officially, "citations" means context cards with exact citations pointing to imported files. The bundled prompt also uses `[Source:N]` tags in answers.
- The official "diagrams" and "images" claims, plus EmbeddingGemma 2's multimodal embedding, mean image files can be searched. That is not the same as live screen understanding.

### Gaps
- None of the official text, the press or the bundle strings I checked mention screen capture or screen understanding. The Info.plist declares only microphone and audio-capture usage descriptions, with no screen-recording key. I found no evidence of this feature.
- The official text does not describe export formats such as Markdown, PDF or copy. An `/export` string exists in the binary, but its function is unverified.
- Integrations beyond local folders, Google Drive and calendar (for example Slack, Notion or CRM) are not mentioned anywhere.
- Supported transcription and UI languages are not stated by Google. Notebookcheck says Google has not said whether transcription works in languages other than English. Heise notes that EmbeddingGemma 2 supports more than 100 languages, but it was unclear whether Foresight does. See [Notebookcheck](https://www.notebookcheck.net/Google-AI-Edge-Foresight-Offline-AI-for-meeting-notes-on-Mac.1418337.0.html) and [heise](https://www.heise.de/en/news/Google-s-macOS-app-Local-AI-to-capture-notes-and-work-with-files-11479591.html).

## 2. Hardware/OS requirements, download size, install, price

### Takeaway
Google officially says only that Foresight is "optimized for Apple Silicon". Google publishes no RAM figure and no macOS version. The installer bundle declares macOS 14.2 as the minimum and contains an arm64-only binary. The DMG is about 160 MB, and models download on first launch. It is free, distributed as a direct DMG download outside the Mac App Store.

### Cited Findings
- **[OFFICIAL]** "Foresight is optimized for Apple Silicon. Thanks to lightweight Gemma quantization and memory-efficient vector kernels, Foresight maintains a light footprint with low battery drain." — [Google product page FAQ](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[OFFICIAL]** The "Download for macOS" button links to `https://dl.google.com/foresight-mac/foresight_mac.dmg`. — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[BUNDLE]** File details from the HTTP response:
  - Content-Length 160,266,104 bytes, about 160 MB
  - Last-Modified Tue, 06 Oct 2026 03:04:39 GMT
  - type `application/x-apple-diskimage`

  Source: [installer DMG](https://dl.google.com/foresight-mac/foresight_mac.dmg)
- **[BUNDLE]** Info.plist details:
  - `LSMinimumSystemVersion` = **14.2**, so macOS Sonoma 14.2 or later
  - version 1.0.0, build `1.0.0.28.20261005`
  - bundle ID `com.google.AIEdgeForesight`
  - built with the macOS 26.4 SDK

  The main executable is "Mach-O 64-bit arm64" only, with no Intel slice. Source: [installer DMG](https://dl.google.com/foresight-mac/foresight_mac.dmg)
- **[PRESS]** Heise says Intel Macs are not supported and that the app is a direct download, not from the Mac App Store. — [heise, Ben Schwan, 7 Oct 2026](https://www.heise.de/en/news/Google-s-macOS-app-Local-AI-to-capture-notes-and-work-with-files-11479591.html)
- **[PRESS]** It is free to download from Google's developer site. Android Authority says the first launch downloads the required on-device models, which takes "about a minute". — [Android Authority](https://www.androidauthority.com/google-ai-edge-foresight-embedding-gemma-2-3719906/); see also [GIGAZINE](https://gigazine.net/gsc_news/en/20261009-google-ai-edge-foresight/)
- **[PRESS]** GIGAZINE reports that Google's explanation includes no cloud subscription fees. — [GIGAZINE](https://gigazine.net/gsc_news/en/20261009-google-ai-edge-foresight/)
- **[PRESS, unverified]** A search-result summary of an Italian report (pasqualepillitteri.it) said the required "expert" models total about 800 MB on first launch and that the 12B model downloads separately. I could not open the page (HTTP 502), so this is **unverified**. — [pasqualepillitteri.it](https://pasqualepillitteri.it/news/21913/google-foresight-mac-trascrizione-riunioni-offline)
- **[PRESS]** One outlet's own estimate is 16 GB RAM as a "comfortable" target. This is not a Google figure. — [thetechbasket](https://www.thetechbasket.com/google-ai-edge-foresight/), as surfaced in search
- **[PRESS]** eWeek says published model specs "do not establish Foresight's total memory use across Mac configurations." — [eWeek](https://www.eweek.com/news/google-ai-edge-foresight-mac/)
- **[BUNDLE]** The bundle includes `GoogleUpdater.zip` and Keystone keys (`KSChannelID`=prod), which suggests automatic updates through Google's updater. — [installer DMG](https://dl.google.com/foresight-mac/foresight_mac.dmg)

### Inferences
- The effective hardware floor is an Apple Silicon Mac on macOS 14.2 or later. Note that macOS 14.2 is also the release in which Apple added the Core Audio process-tap API with an `NSAudioCaptureUsageDescription` permission for capturing other apps' audio. That is a plausible reason for this minimum, but it is not confirmed.

### Gaps
- Google publishes no minimum RAM, disk space or chip generation.
- The exact on-disk model sizes after first launch are not stated officially.

## 3. Models: Gemma 4 size, EmbeddingGemma 2, selectability, licenses, source code

### Takeaway
Officially, Foresight uses EmbeddingGemma 2 (740M parameters, multimodal embeddings) for retrieval and "Gemma 4" for generation. Google's page does not name a Gemma 4 size. Secondary reporting and UI strings in the binary point to a user choice between **Gemma 4 E4B (default)** and **Gemma 4 12B**. EmbeddingGemma 2 is open-weight under Apache 2.0. The app itself is proprietary ("All rights reserved"), and I found no source-code release.

### Cited Findings
- **[OFFICIAL]** "EmbeddingGemma 2 is a 740M parameter on-device multimodal embedding model which maps text, image, video, and audio into a single vector space… Combined with Gemma 4, it delivers fully on-device RAG pipelines for real-time local search and contextual grounding with no network latency." — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[OFFICIAL]** The blog gives these EmbeddingGemma 2 specs:
  - about 740M parameters, open-weight
  - modular encoders that can be loaded selectively
  - about 191 MB active RAM for text-only and about 567 MB for full multimodal, measured on a Pixel 11 Pro
  - quantization-aware training to INT4 and INT8
  - 768-dimensional output, with Matryoshka truncation to 128–512
  - shipped as a LiteRT `.litertlm` file on CPU, GPU and NPU, and also via WASM and MediaPipe Tasks
  - about 37.3 ms per image on a MacBook M5 Pro GPU

  Source: [Google Developers Blog](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/)
- **[OFFICIAL]** The Hugging Face model card breaks the parameters down as text about 270M, vision encoder 170M and audio encoder 300M. It lists 100+ languages and the Apache 2.0 license tag, plus the Gemma Prohibited Use Policy. It does not mention Foresight. — [Hugging Face model card](https://huggingface.co/google/embeddinggemma-2)
- **[PRESS]** 9to5Google and Notebookcheck say it is built on the Gemma 4 architecture under Apache 2.0. — [9to5Google, Abner Li, 6 Oct 2026](https://9to5google.com/2026/10/08/google-ai-edge-foresight/); [Notebookcheck](https://www.notebookcheck.net/Google-AI-Edge-Foresight-Offline-AI-for-meeting-notes-on-Mac.1418337.0.html)
- **[PRESS, conflicting]** Heise says EmbeddingGemma 2 is "optimized for Apple's MLX runtime". Google's blog does not mention MLX and names LiteRT instead. The bundle ships LiteRT libraries (`libLiteRt.dylib`, `libLiteRtMetalAccelerator.dylib`, `libLiteRtWebGpuAccelerator.dylib`), a `.litertlm` reference and a Flutter UI framework. I saw no MLX framework. Treat the MLX claim as **doubtful**. — [heise](https://www.heise.de/en/news/Google-s-macOS-app-Local-AI-to-capture-notes-and-work-with-files-11479591.html); [Google Developers Blog](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/); [installer DMG](https://dl.google.com/foresight-mac/foresight_mac.dmg)
- **[PRESS, partly unverified]** According to a search summary of Italian first-launch coverage (page not openable), users choose between Gemma 4 E4B (the default) and Gemma 4 12B, which is described as "more capability and deeper reasoning but requires more storage and memory." — [pasqualepillitteri.it](https://pasqualepillitteri.it/news/21913/google-foresight-mac-trascrizione-riunioni-offline); [aiweekly](https://aiweekly.co/alerts/google-launches-ai-edge-foresight-a-local-macos-meeting-notes-app-running)
- **[BUNDLE, corroborating]** The binary contains UI strings "Gemma 4 E4B" and "Gemma 4 12B". It also has internal enum names including `GEMMA4_4P5B_WITH_DRAFTER`, `GEMMA4_12B_WITH_DRAFTER`, `GEMMA4_2P3B_WITH_DRAFTER`, `GEMMA4_26BA4B_WITH_DRAFTER`, `GEMMA4_31B_WITH_DRAFTER` and `GEMMA4_200M_USM_*`. These are generic LiteRT-LM model types and do not prove the app offers each one. The `USM` entries hint at a Gemma 4 / USM-based speech model for transcription, which is **unverified**. — [installer DMG](https://dl.google.com/foresight-mac/foresight_mac.dmg)
- **[PRESS]** Android Authority mentions that Google released Gemma 4 12B for on-device use, as context. It does not state that Foresight uses it. — [Android Authority](https://www.androidauthority.com/google-ai-edge-foresight-embedding-gemma-2-3719906/)
- **[OFFICIAL]** App licensing: the page footer reads "© 2026 Google LLC. All rights reserved." and links to the Google Terms of Service and Privacy Policy. Info.plist has `NSHumanReadableCopyright` "Copyright © 2026 Google LLC. All rights reserved." — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame); [installer DMG](https://dl.google.com/foresight-mac/foresight_mac.dmg)

### Inferences
- The models (EmbeddingGemma 2 under Apache 2.0, and Gemma 4) are open-weight. The Foresight app is a closed-source Google binary under the standard Google ToS.

### Gaps
- Google has not officially confirmed which Gemma 4 variant is the default, or whether users can choose models.
- I found no GitHub or source repository for Foresight, and no app-specific EULA beyond the Google ToS. Notebookcheck's "Open Source" keyword refers to the model, not the app.
- The Gemma 4 license terms were not separately checked here. The HF card's license link is titled for Gemma 4 while tagged Apache 2.0.

## 4. Audio capture, offline operation, data storage, telemetry, Google account

### Takeaway
Officially, Foresight captures local system audio and microphone audio. Google says it works alongside "Google Meet, Zoom, or offline conversations" and with "any meeting platform". Google claims 100% local inference, says no files, recordings or transcripts are sent to the cloud, and says the app is "completely offline-first". However, the product offers optional Google sign-in for Drive and Calendar, including a Workspace admin FAQ. The bundle also includes Firebase, with the Analytics SDK and messaging, plus Google network endpoints. So "offline" applies to the AI processing, not to every feature, and I found no official statement on whether analytics telemetry runs.

### Cited Findings
- **[OFFICIAL]** "Foresight runs unobtrusively on your desktop alongside Google Meet, Zoom, or offline conversations, transcribing local system audio in real time." — [Google product page FAQ](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[OFFICIAL]** "it works out-of-the-box with any meeting platform, even completely offline." — [Google Developers Blog](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/)
- **[OFFICIAL]** Privacy, from the FAQ: "All AI inference runs 100% locally on your device using on-device Gemma models. Your personal knowledge sources, meeting audio, and notes never leave your computer. No personal files, recordings, or transcripts are ever transmitted to external cloud servers, ensuring strict privacy compliance for confidential documents and proprietary discussions." The page also says "Transcript and audio processed on your computer — not in the cloud" and "Files stay on your Mac". — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[OFFICIAL]** Offline, from the FAQ: "Yes. Foresight is completely offline-first. Both the Gemma model and the local vector embeddings engine run on your hardware without internet. You can travel, fly on airplanes, or work in air-gapped secure facilities with full assistance and query capabilities." — [Google product page FAQ](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[OFFICIAL]** The blog says "your sensitive data never leaves your device." — [Google Developers Blog](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/)
- **[OFFICIAL]** Google account and Workspace FAQ: "Why can't I sign in with my Google Workspace account…? For Google Workspace (enterprise) accounts, Early Access Apps and Core Data Access are turned off by default." Admins must enable "Early Access Apps (Enables Sign-in)" and "Core Data Access (Enables Workspace Data)". The latter is described as "Allow users at your organization to access Google Workspace and Customer Data using Early Access apps". Changes can take up to 24 hours. — [Google product page FAQ](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame); [Workspace Admin Help](https://support.google.com/a/answer/13515709)
- **[BUNDLE]** Info.plist declares two permissions:
  - `NSMicrophoneUsageDescription` ("…capture audio input")
  - `NSAudioCaptureUsageDescription` ("…capture audio output from other apps")

  It also registers Google Sign-In (`GIDClientID`, Google SSO URL schemes). — [installer DMG](https://dl.google.com/foresight-mac/foresight_mac.dmg)
- **[BUNDLE]** OAuth scopes in the binary:
  - `drive.readonly`, `documents.readonly`, `presentations.readonly` and `calendar.events.readonly`
  - `userinfo.email` and `userinfo.profile`
  - a Google-internal `auth/aiedge` scope

  Endpoints in the binary include `odml.pa.googleapis.com/v1/calendar/notification`, Calendar v3, `customsearch.googleapis.com`, and Firebase/FCM registration endpoints. — [installer DMG](https://dl.google.com/foresight-mac/foresight_mac.dmg)
- **[BUNDLE]** Firebase details:
  - The Firebase Analytics Flutter plugin (`FLTFirebaseAnalyticsPlugin`, with `logEvent`, `setUserId` and `setAnalyticsCollectionEnabled`) and Google Analytics for Firebase (APM) classes are compiled in.
  - The bundled `GoogleService-Info.plist` has `IS_ANALYTICS_ENABLED` = false, `IS_ADS_ENABLED` = false, `IS_SIGNIN_ENABLED` = true and `IS_GCM_ENABLED` = true. These flags are config-file defaults and do not by themselves show runtime behavior.
  - The binary also contains strings "Analytics collection deactivated" and "Analytics collection disabled" (SDK messages).

  I made no network-traffic observation, so whether usage analytics are sent is **unverified**. — [installer DMG](https://dl.google.com/foresight-mac/foresight_mac.dmg)
- **[OFFICIAL]** The product page loads Google Analytics (gtag `G-VJ6QGT18F5`). This applies to the website, not necessarily the app. — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[PRESS]** eWeek notes that macOS manages mic and system-audio permissions separately from Google Meet's recording controls. It also says Meet's new participant-consent controls do not block other authorized apps, and that available information does not show how Foresight behaves when Meet recording is disabled. eWeek advises IT to set consent, retention and deletion rules for locally stored transcripts. — [eWeek](https://www.eweek.com/news/google-ai-edge-foresight-mac/)
- **[PRESS]** Heise advises users to remain cautious about what they give the app. — [heise](https://www.heise.de/en/news/Google-s-macOS-app-Local-AI-to-capture-notes-and-work-with-files-11479591.html)

### Inferences
- A Google account appears optional for core local use, since Google says it works offline and in air-gapped facilities. Sign-in is needed for Google Drive, Docs, Slides and Calendar sources. Workspace sign-in requires admin enablement of Early Access Apps, which marks Foresight as an "Early Access app" in Workspace terms.
- With Drive or Calendar connected, the app necessarily makes network calls to Google APIs, for example a calendar-notification service on `odml.pa.googleapis.com`. So "never leave your computer" refers to meeting audio, notes and personal files being processed locally, not to zero network activity.

### Gaps
- There is no official statement on where on disk transcripts, notes and indexes are stored, whether they are encrypted, or retention and deletion controls.
- There is no official statement on app telemetry, crash reporting or analytics, and no Foresight-specific privacy notice. The page links only to the general Google Privacy Policy.
- Google does not say whether sign-in is mandatory at first launch. I did not run the app.
- There is no official list of meeting platforms beyond "Google Meet, Zoom" and "any meeting platform".

## 5. Experimental status, limitations, known issues, roadmap

### Takeaway
Google labels Foresight "an experimental app" launched alongside EmbeddingGemma 2. Notebookcheck frames it as primarily a developer showcase. Google has published no known-issues list and no platform roadmap for Windows, Linux or iOS versions of Foresight. The only roadmap items concern the EmbeddingGemma 2 model, which is coming to ML Kit on Android.

### Cited Findings
- **[OFFICIAL]** "an experimental app that brings a context-aware meeting companion directly to your device" — [Google Developers Blog](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/)
- **[OFFICIAL]** Model roadmap: "In the coming weeks, we will also make this model available as a service on Android, accessible through ML Kit". The blog says EmbeddingGemma 2 itself runs on Android, iOS, macOS, Windows, Linux and the web via LiteRT and MediaPipe. — [Google Developers Blog](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/)
- **[OFFICIAL]** Known restriction: Workspace accounts are blocked by default until an admin enables Early Access Apps and Core Data Access. Support contact: ai-edge-support@google.com. — [Google product page](https://developers.google.com/frame/edge/foresight/index_36bafa421e450bd2f8ebb067988038e9b63aecb4cbea9f3ae27b664cc8b899c8.frame)
- **[PRESS]** Notebookcheck says Google describes it as experimental and "primarily a showcase for developers", and that non-English transcription quality is unaddressed. — [Notebookcheck, Jan Gruber, 7 Oct 2026](https://www.notebookcheck.net/Google-AI-Edge-Foresight-Offline-AI-for-meeting-notes-on-Mac.1418337.0.html)
- **[PRESS]** Search-result summaries say Google has not said how long it will maintain the app, so it should be treated as an early release. I did not open the underlying article. — [thetechbasket](https://www.thetechbasket.com/google-ai-edge-foresight/)
- **[PRESS]** Related Google apps: AI Edge Eloquent (transcription on Mac and iOS) and AI Edge Gallery. — [heise](https://www.heise.de/en/news/Google-s-macOS-app-Local-AI-to-capture-notes-and-work-with-files-11479591.html); [9to5Google](https://9to5google.com/2026/10/08/google-ai-edge-foresight/)

### Gaps
- No official Windows, Linux or iOS plans for Foresight were found. Platform claims in the press about "cross-platform deployment" refer to the EmbeddingGemma 2 model, not the app.
- No official changelog, known-issues list or support duration was found.

## 6. Launch date and announcement wording

### Takeaway
Foresight was announced on **6 October 2026** in the Google Developers Blog post "Bring multimodal semantic search to the edge with EmbeddingGemma 2" (by the Google AI Edge Team and Android ML Team), together with EmbeddingGemma 2. The installer build is dated 5–6 Oct 2026. Most press coverage ran on 6–12 Oct.

### Cited Findings
- **[OFFICIAL]** The blog post is dated Oct. 6, 2026, authored by the Google AI Edge Team and Android ML Team. It introduces Foresight as "an experimental app that brings a context-aware meeting companion directly to your device. Powered by fully local AI processing, Foresight seamlessly assists with note-taking, indexing, and recalling…". It ends with "Download the Google AI Edge Foresight Mac app today." — [Google Developers Blog](https://developers.googleblog.com/google-ai-edge-with-embeddinggemma-2/)
- **[OFFICIAL]** The Google Gemma X post (status 2112657975789949376) reads: "Taking meeting notes is easy; connecting them to your local files in real time is hard. Meet Google AI Edge Foresight, an on-device macOS meeting companion powered by EmbeddingGemma 2. It auto-enhances shorthand notes and searches across local docs, images, and transcripts com…" This text is truncated as shown in the search-result title; the page itself returned HTTP 402 to my fetch. — [X / @googlegemma](https://x.com/googlegemma/status/2112657975789949376)
- **[BUNDLE]** Build `1.0.0.28.20261005`. The DMG was last modified 06 Oct 2026 03:04 GMT. — [installer DMG](https://dl.google.com/foresight-mac/foresight_mac.dmg)
- **[PRESS]** Press dates:
  - 9to5Google, 6 Oct 2026, 10:15 am PT — [9to5Google](https://9to5google.com/2026/10/08/google-ai-edge-foresight/)
  - Android Authority, 7 Oct — [Android Authority](https://www.androidauthority.com/google-ai-edge-foresight-embedding-gemma-2-3719906/)
  - heise, 7 Oct — [heise](https://www.heise.de/en/news/Google-s-macOS-app-Local-AI-to-capture-notes-and-work-with-files-11479591.html)
  - Notebookcheck, 7 Oct — [Notebookcheck](https://www.notebookcheck.net/Google-AI-Edge-Foresight-Offline-AI-for-meeting-notes-on-Mac.1418337.0.html)
  - GIGAZINE, 9 Oct — [GIGAZINE](https://gigazine.net/gsc_news/en/20261009-google-ai-edge-foresight/)
  - eWeek, 12 Oct — [eWeek](https://www.eweek.com/news/google-ai-edge-foresight-mac/)

### Gaps
- The exact posting date and time of the @googlegemma X post could not be retrieved. The fetch was blocked with HTTP 402.
- The Verge and TechCrunch coverage was not found in my searches. How-To Geek was not checked.
