// VEENA.AI website settings. The ONLY place external services are switched on.
// Every value starts empty: nothing is sent anywhere until the owner fills one in
// with a value they created and verified. No secrets belong here: this file is public.
// Setup steps: veena-ai/docs/FEEDBACK_AND_COMMUNITY_SETUP.md
window.VEENA_CONFIG = {
  // Google Form for feedback (owner's own form). Leave null until it exists.
  // formUrl: the form's public link, ending in /viewform, e.g.
  //   https://docs.google.com/forms/d/e/<FORM-ID>/viewform
  // entries: the entry.<number> IDs, read from the form's "Get pre-filled link".
  feedback: {
    formUrl: null,
    entries: { experience: null, type: null, message: null, email: null, page: null },
  },

  // GitHub Discussions. Set to true ONLY after Discussions is enabled in
  // Settings > General > Features and the categories exist; CI checks the API.
  discussionsEnabled: true,

  // Cloudflare Web Analytics site token (public, cookieless page-view counts).
  // Leave null until the owner creates the site in their Cloudflare dashboard.
  cloudflareToken: null,

  // VEENA Insights (cloud/insights): cookieless page-view and download-click COUNTERS, no identifier.
  // Leave null until the owner deploys the Worker; then set to its https:// URL.
  insightsUrl: null,
};
