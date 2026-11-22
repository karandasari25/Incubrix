from app.connectors.simulation import SimulationConnector


class KitConnector(SimulationConnector):
    def __init__(self) -> None:
        super().__init__("kit", title_max=150, body_max=40000)
