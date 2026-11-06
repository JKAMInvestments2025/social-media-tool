import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # sources
    feeds: list = field(default_factory=list)
    search_queries: list = field(default_factory=list)
    max_candidates: int = 40
    max_article_age_days: int = 5
    # editorial
    audience: str = "retail and high-net-worth investors"
    voice: str = "clear, professional, no hype"
    topics: str = "markets, macro, personal finance, investing"
    batch_size: int = 5                  # headlines offered per weekly batch
    run_days: list = field(default_factory=lambda: ["mon"])
    run_times: list = field(default_factory=lambda: ["08:00"])
    # posting
    timezone: str = "America/New_York"
    post_times: list = field(default_factory=lambda: ["09:30", "12:30", "17:00"])
    vista_profile_ids: list = field(default_factory=list)
    disclaimer: str = ("Investing involves risk, including loss of principal. "
                       "Past performance does not guarantee future results. Not investment advice.")
    # providers: console|twilio, anthropic|fake, openai|fake|none, vista_api|vista_webhook|dry_run
    whatsapp_provider: str = "console"
    llm_provider: str = "anthropic"
    image_provider: str = "openai"
    vista_mode: str = "dry_run"
    # runtime
    data_dir: Path = Path("data")
    public_base_url: str = ""
    port: int = 8080
    approver: str = ""           # approver's WhatsApp number, e.g. +15551234567
    admin_token: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    openai_image_model: str = "gpt-image-1"
    env: dict = field(default_factory=dict, repr=False)

    def secret(self, name):
        return self.env.get(name) or os.environ.get(name, "")


def load(path="config.toml"):
    data = {}
    p = Path(path)
    if p.exists():
        data = tomllib.loads(p.read_text())
    flat = {}
    for section in data.values():
        if isinstance(section, dict):
            flat.update(section)
    flat.update({k: v for k, v in data.items() if not isinstance(v, dict)})
    names = set(Config.__dataclass_fields__)
    cfg = Config(**{k: v for k, v in flat.items() if k in names and k != "env"})
    cfg.data_dir = Path(cfg.data_dir)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    return cfg
