from app.connectors.simulation import SimulationConnector


class MrssConnector(SimulationConnector):
    def __init__(self) -> None:
        super().__init__("mrss")
