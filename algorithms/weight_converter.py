class WeightConverter:
    """Utility for converting between kg and lb."""

    KG_TO_LB = 2.20462

    @staticmethod
    def kg_to_lb(kg: float) -> float:
        return round(kg * WeightConverter.KG_TO_LB, 2)

    @staticmethod
    def lb_to_kg(lb: float) -> float:
        return round(lb / WeightConverter.KG_TO_LB, 2)
