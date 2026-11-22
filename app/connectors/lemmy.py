from app.connectors.simulation import SimulationConnector


class LemmyConnector(SimulationConnector):
    def __init__(self) -> None:
        super().__init__("lemmy", title_max=200, body_max=10000)
