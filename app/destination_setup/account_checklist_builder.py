from __future__ import annotations


OFFICIAL_API_PLATFORMS = {"Instagram Reels", "TikTok", "YouTube Shorts"}
MANUAL_FIRST_PLATFORMS = {"Telegram", "VK Clips", "Manual Upload"}


class AccountChecklistBuilder:
    def initial_task_status(self, platform: str) -> str:
        if platform in OFFICIAL_API_PLATFORMS:
            return "needs_manual_setup"
        return "needs_manual_setup"

    def build(self, platform: str) -> list[dict]:
        api_available = platform in OFFICIAL_API_PLATFORMS
        checklist = [
            self._item("owned_account", "Create or confirm an owned account off-platform."),
            self._item("platform_rules", "Confirm the account follows platform rules and brand ownership policy."),
            self._item("profile_name", "Apply the suggested account name and handle or record the final approved variant."),
            self._item("avatar", "Add an approved avatar or product-safe brand visual."),
            self._item("bio", "Add bio text, official storefront link, and safe claim language."),
            self._item("operator_owner", "Assign a human owner for setup and first upload checks."),
            self._item("approval_policy", "Confirm only approved videos can be published."),
        ]
        if api_available:
            checklist.append(
                self._item(
                    "official_api",
                    "Connect official OAuth/API token when available; keep manual-assisted upload until token_valid.",
                )
            )
        else:
            checklist.append(
                self._item("manual_upload", "Use manual-assisted upload pack with final URL capture after publication.")
            )
        checklist.append(self._item("no_external_registration", "Do not run external account auto-registration from ContentEngine."))
        return checklist

    @staticmethod
    def _item(key: str, title: str) -> dict:
        return {"key": key, "title": title, "status": "pending", "required": True}
