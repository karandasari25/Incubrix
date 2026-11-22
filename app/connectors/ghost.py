from app.connectors.simulation import SimulationConnector


class GhostConnector(SimulationConnector):
    def __init__(self) -> None:
        super().__init__("ghost", title_max=300, body_max=100000)
