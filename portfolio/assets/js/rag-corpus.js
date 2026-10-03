// SYNTHETIC CORPUS. "NovaGrid Corp" is fictional; every policy, number and
// name below was invented for this demo and describes no real organization.
export const CORPUS = [
  {
    id: 'IT-SEC-014', title: 'Remote Access & VPN Policy', source: 'SharePoint',
    chunks: [
      { section: 'Scope', text: 'This policy applies to all employees and contractors who access NovaGrid systems from outside the corporate network. Remote access is only permitted through the approved VPN client on a managed device.' },
      { section: 'Credentials', text: 'VPN credentials must be rotated every 90 days. Multi-factor authentication is mandatory for every VPN session. Shared VPN accounts are prohibited.' },
      { section: 'Contractors', text: 'Contractor VPN access expires automatically at the end of the contract and must be sponsored by a NovaGrid manager. Contractors may not access production databases over VPN without a security exception.' },
    ],
  },
  {
    id: 'OPS-RB-007', title: 'Incident Severity & On-call Runbook', source: 'Confluence',
    chunks: [
      { section: 'Severity levels', text: 'A P1 incident is a full outage or data-integrity risk affecting customers. A P2 incident is a major degradation with a workaround. P3 covers minor issues with no customer impact.' },
      { section: 'P1 response', text: 'For a P1 incident the on-call engineer must acknowledge the page within 15 minutes and appoint an incident commander. Status updates are posted to the incident channel every 30 minutes until resolution.' },
      { section: 'Post-incident', text: 'Every P1 and P2 incident requires a blameless postmortem within five business days. Action items are tracked as Jira issues with the label postmortem.' },
    ],
  },
  {
    id: 'FIN-POL-003', title: 'Expense & Travel Policy', source: 'SharePoint',
    chunks: [
      { section: 'Submission', text: 'Expenses must be submitted within 30 days of being incurred, with an itemized receipt for any amount above 25 EUR. Late submissions require approval from a finance controller.' },
      { section: 'Travel', text: 'Economy class is the default for flights under six hours. Hotel bookings should use the corporate travel portal. Meal allowances follow the per-diem table for the destination country.' },
    ],
  },
  {
    id: 'DATA-STD-002', title: 'Data Classification Standard', source: 'Confluence',
    chunks: [
      { section: 'Levels', text: 'NovaGrid classifies data as Public, Internal, Confidential or Restricted. Customer personal data and credentials are always Restricted.' },
      { section: 'Handling', text: 'Restricted data must be encrypted at rest and in transit, may only be stored in approved systems, and must never be pasted into external tools. Confidential data may be shared internally on a need-to-know basis.' },
    ],
  },
  {
    id: 'AI-GOV-001', title: 'Generative AI Usage Guidelines', source: 'Confluence',
    chunks: [
      { section: 'Approved tools', text: 'Employees may use the internal AI assistant for Internal and Confidential data. Public AI chatbots may only be used with Public data. Restricted data must never be sent to any AI model.' },
      { section: 'Review', text: 'AI-generated code must be reviewed by a human before merge and is subject to the same tests and security scans as other code. AI-generated customer communications require human approval before sending.' },
      { section: 'Retention', text: 'Prompts and responses in the internal AI assistant are retained for 30 days for audit purposes and are then deleted automatically.' },
    ],
  },
  {
    id: 'ENG-REL-010', title: 'Release Management Process', source: 'Confluence',
    chunks: [
      { section: 'Cadence', text: 'Production releases happen every two weeks on Tuesday. A code freeze starts on the Thursday before each release.' },
      { section: 'Blockers', text: 'Any open P1 bug tagged with the release fixVersion blocks the release. The release manager may grant an exception only with written sign-off from the engineering director.' },
      { section: 'Rollback', text: 'Every release must have a tested rollback plan. Feature flags are preferred over rollbacks for disabling new functionality.' },
    ],
  },
  {
    id: 'IT-SEC-021', title: 'Password & MFA Standard', source: 'SharePoint',
    chunks: [
      { section: 'Passwords', text: 'Passwords must be at least 14 characters long and stored only in the approved password manager. Password reuse across systems is prohibited.' },
      { section: 'MFA', text: 'Multi-factor authentication is required for email, source control, cloud consoles and VPN. Hardware security keys are required for administrators.' },
    ],
  },
  {
    id: 'HR-ONB-005', title: 'Engineering Onboarding Handbook', source: 'GitHub Wiki',
    chunks: [
      { section: 'First week', text: 'New engineers receive a managed laptop on day one and are paired with an onboarding buddy. Access to source control is granted after security training is completed.' },
      { section: 'Production access', text: 'Production access is granted after 30 days and requires manager approval plus completion of the incident response training.' },
    ],
  },
];

export const SUGGESTED = [
  'How often must VPN credentials be rotated?',
  'What should on-call do for a P1 incident?',
  'Can I paste customer data into a public AI chatbot?',
  'What blocks a production release?',
  'What is the capital of France?',
];

export const SYNONYMS = {
  vpn: ['remote', 'access'],
  remote: ['vpn'],
  mfa: ['multi', 'factor', 'authentication'],
  '2fa': ['multi', 'factor', 'authentication'],
  password: ['credential'],
  credential: ['password'],
  rotate: ['rotat'],
  outage: ['incident'],
  incident: ['outage'],
  sev1: ['p1'],
  p1: ['incident'],
  oncall: ['call'],
  chatgpt: ['public', 'ai', 'chatbot'],
  llm: ['ai', 'model'],
  genai: ['ai', 'generative'],
  pii: ['personal', 'data'],
  customer: ['personal'],
  expense: ['receipt', 'submit'],
  reimburse: ['expense'],
  deploy: ['release'],
  release: ['production'],
  laptop: ['device'],
  contractor: ['contract'],
};
