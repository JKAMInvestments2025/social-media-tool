# JKAM Social

A Vista Social–style social media management tool for JKAM Investments. Zero dependencies — open `index.html` in a browser (or `python3 -m http.server`).

## Features
- **Dashboard** – KPIs, upcoming posts, follower trend
- **Composer** – multi-profile posting, per-network character limits and previews, best-time suggestion, hashtags, disclaimer insertion
- **Calendar** – monthly view, click a day to create, drag posts to reschedule
- **Content & Approvals** – draft → pending → approved → scheduled → published workflow; Admin/Editor roles
- **Compliance** – flags phrases like "guaranteed returns"/"risk-free", suggests risk disclaimers, optional approval gate
- **Inbox** – unified messages with replies
- **Analytics** – impressions, engagement, growth, top posts, CSV export
- **Social Profiles** – add/disconnect/remove accounts

Data is stored in `localStorage` and metrics/publishing are simulated; real network integrations (OAuth, publish APIs) would need a backend.
