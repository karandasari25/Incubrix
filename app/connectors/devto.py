from app.connectors.simulation import SimulationConnector


class DevToConnector(SimulationConnector):
    def __init__(self) -> None:
        super().__init__("devto", title_max=255, body_max=70000)

    def delete(self, platform_post_id: str, connection: dict) -> dict:
        """Dev.to simulation records unpublish, not an irreversible delete."""
        return {"deleted": False}
