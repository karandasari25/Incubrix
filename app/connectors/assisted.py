from app.connectors.simulation import SimulationConnector


class AssistedConnector(SimulationConnector):
    def __init__(self) -> None:
        super().__init__("assisted")

    def build_assist_pack(self, rendition: dict, destination: dict) -> dict:
        title = rendition.get("title") or "Untitled"
        link = rendition.get("canonical_link") or destination.get("url") or ""
        caption = f"{title}\n\n{rendition.get('body', '')[:280]}"
        return {
            "files": [],
            "caption": caption,
            "deep_link": link,
            "checklist": [
                "Confirm destination-specific link policy",
                "Confirm promotional disclosure",
                "Review and post manually",
            ],
        }
