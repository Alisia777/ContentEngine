# Telegram Playbook

Telegram may be published by bot or manually.

If bot posts, preserve:

- `chat_id`
- `message_id`
- posted time
- final message link if available

If manual, submit `final_url` or message link.

Always place `tracking_link` in post text. Use manual stats fallback when views, reactions, or comments are limited.
