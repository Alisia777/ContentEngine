from __future__ import annotations


class PlatformStrategyBuilder:
    def build(self, *, primary_platform: str = "Instagram Reels", offer_type: str = "value") -> dict:
        strategies = {
            "Instagram Reels": {
                "hook_style": "personal creator hook with immediate product visibility",
                "pacing": "quick but polished",
                "cta": "save/share or product card",
                "proof_bias": "visual texture, pack-in-hand, routine fit",
                "avoid": ["long intro", "generic announcer voice"],
            },
            "TikTok": {
                "hook_style": "fast conflict or now-I-show-you setup",
                "pacing": "faster cuts, direct creator speech",
                "cta": "comment or product card",
                "proof_bias": "try-on/try-bite/demo moment",
                "avoid": ["overproduced ad tone", "slow product reveal"],
            },
            "YouTube Shorts": {
                "hook_style": "slightly clearer explanatory promise",
                "pacing": "retention-led explanation",
                "cta": "watch-to-end or product link",
                "proof_bias": "reason-to-believe and comparison clarity",
                "avoid": ["unclear payoff", "empty texture shot"],
            },
            "Telegram": {
                "hook_style": "context-led short post plus video",
                "pacing": "clear copy, less visual noise",
                "cta": "link in post",
                "proof_bias": "written context, price/value, usage notes",
                "avoid": ["caption-only video without post context"],
            },
            "VK": {
                "hook_style": "benefit plus practical situation",
                "pacing": "straightforward social video",
                "cta": "open product or community link",
                "proof_bias": "use case and product clarity",
                "avoid": ["platform-agnostic meme framing"],
            },
            "Marketplace card video": {
                "hook_style": "product clarity first, minimal blogger setup",
                "pacing": "proof and usage clarity over personality",
                "cta": "product card action",
                "proof_bias": "pack, size, texture/use case, expectation setting",
                "avoid": ["long lifestyle story", "unreadable generated text"],
            },
        }
        if primary_platform not in strategies:
            strategies[primary_platform] = {
                "hook_style": "platform-safe creator hook",
                "pacing": "short vertical video",
                "cta": "product card",
                "proof_bias": "product clarity",
                "avoid": ["generic ad voice"],
            }
        return {
            "primary_platform": primary_platform,
            "offer_type": offer_type,
            "rules": strategies,
            "selected": strategies[primary_platform],
        }
