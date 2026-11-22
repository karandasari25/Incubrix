from app.connectors.simulation import SimulationConnector


class HashnodeConnector(SimulationConnector):
    def __init__(self) -> None:
        super().__init__("hashnode", title_max=255, body_max=100000)
