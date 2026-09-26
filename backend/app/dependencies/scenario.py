from app.crud import ScenarioCRUD


def get_scenario_crud() -> ScenarioCRUD:
    return ScenarioCRUD()