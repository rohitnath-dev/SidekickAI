# Privacy Policy for SidekickAI

**Effective Date:** August 3, 2026

SidekickAI ("we," "our," or "us") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our web application located at https://sidekickai.onrender.com (the "Service").

By accessing or using our Service, you agree to the collection and use of information in accordance with this Privacy Policy. If you do not agree with any terms of this policy, please do not use the Service.

---

## 1. Information Collection

We collect several types of information to provide and improve our Service:

### A. Information You Provide Directly
* **Account Information:** When you register for an account, we collect your full name, email address, password (stored securely using industry-standard hashing algorithms), and user preferences.
* **Communications:** If you contact us directly, we may collect your email address, message contents, and any attachments you send.

### B. Third-Party Integrations & OAuth Authorized Data
To deliver our AI assistant functionalities, SidekickAI connects with external platforms via OAuth protocol. We access only the permissions you explicitly grant during authentication:
* **Google Workspace APIs (Gmail & Calendar):**
  * **Gmail Scopes:** We access Gmail messages (read, modify, send, and compose permissions) to pull email history, synthesize summaries, detect priority threads, and generate draft responses. 
  * **Google Calendar Scopes:** We access calendar events (read and write permissions) to retrieve your schedule timeline, update calendar entries, and compile your daily executive briefing.
  * **OAuth Tokens:** We receive and securely store encrypted Google refresh and access tokens to synchronize your data in the background.
* **LinkedIn API:**
  * **Scopes Used:** We request profile information access and post-sharing scopes (`w_member_social`). 
  * **Access Limitations:** The API only allows us to synchronize your profile metadata and share auto-generated professional posts. We do not (and cannot) read LinkedIn messages, direct chats, or private inbox content.
* **WhatsApp Cloud API:**
  * **Embedded Signup flow:** Integrates strictly with Meta's official WhatsApp Business Platform. We access your registered WhatsApp Business Account (WABA) ID, connected phone numbers, and customer chats.
  * **Access Limitations:** This integration requires a dedicated business number. It **cannot** connect personal WhatsApp profiles, read personal chats, or sync standard private numbers.

---

## 2. How We Use Your Information

We use the collected information for various purposes, including to:
* **Operate the Service:** Sync email lists, calendar schedules, WhatsApp customer chats, and LinkedIn profiles.
* **Generate AI Assist Capabilities:** Analyze email headers and body texts using LLMs to prioritize threads, draft proposed reply templates, and build your Daily Briefing.
* **Improve & Personalize:** Track application performance, resolve configuration bugs, and enhance user experience layouts.
* **Security & Authentication:** Verify user accounts, secure API sessions, and maintain OAuth credential token rotations.

---

## 3. Data Sharing & Disclosure

We do not sell, trade, or rent your personal information to third parties. We may disclose data under the following circumstances:
* **With Service Providers:** We share content with verified sub-processors (such as LLM endpoint providers like OpenRouter) solely to process your prompts and draft summaries. These providers are bound by strict confidentiality obligations and do not use your data to train their public models.
* **Legal Requirements:** If required by law, subpoena, or government regulation, we may disclose information to comply with valid legal processes.
* **Business Transfers:** If SidekickAI undergoes a merger, acquisition, or asset sale, your personal information may be transferred. We will notify you before your data becomes subject to a different policy.

---

## 4. Data Security

We implement robust administrative, technical, and physical security measures to safeguard your credentials and data:
* **Encryption:** All OAuth credentials (tokens) are stored in our database using strong AES-256 encryption. All network communications use secure HTTPS/TLS transport protocols.
* **Access Control:** System database sessions are restricted to authenticated service layers. Database engines are isolated from direct external internet access.
* **No Cache Retention for LLMs:** When we send email or chat content to LLM endpoints for synthesis, the data is passed securely and is not cached or used for training.

---

## 5. User Rights

Depending on your jurisdiction (such as under GDPR or CCPA), you may have the following rights regarding your data:
* **Access & Sync:** You can view all linked data and integrations directly on the dashboard.
* **Data Rectification:** You can modify your profile details and connection settings at any time in the Settings portal.
* **Data Erasure (Right to be Forgotten):** You can delete your account or disconnect specific integrations. Disconnecting a service instantly deletes the corresponding OAuth credentials, synced messages, and cached indexes from our database.
* **Contact:** To request complete account erasure or export your details, email us at humammoin09@gmail.com.

---

## 6. Cookies & Tracking Technologies

We use basic HTTP cookies and local storage tokens to manage user sessions and login authentication states:
* **Auth Cookies:** Secure JWT cookie tokens are stored in your browser to maintain your session state.
* **Preferences Storage:** Local storage is used to save theme states and interface layouts.
* **No Third-Party Ad Trackers:** We do not host third-party advertisement trackers, analytics beacons, or retargeting scripts.

---

## 7. Changes to This Privacy Policy

We may update our Privacy Policy from time to time. We will notify you of any changes by posting the new Privacy Policy on this page and updating the "Effective Date" at the top. We recommend checking this page periodically for updates.

---

## 8. Contact Us

If you have any questions or suggestions about this Privacy Policy, please contact us:
* **By Email:** humammoin09@gmail.com
* **Official Website:** https://sidekickai.onrender.com