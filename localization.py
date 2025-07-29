class Translator:
    def __init__(self) -> None:
        self.language = "en"
        self.translations = {
            "en": {},
            "es": {
                "Workouts": "Entrenamientos",
                "Library": "Biblioteca",
                "Progress": "Progreso",
                "Settings": "Configuración",
                "Log": "Registrar",
                "Plan": "Planificar",
                "General Settings": "Configuración General",
                "Display Settings": "Configuración de Pantalla",
                "Language": "Idioma",
                "Save General Settings": "Guardar Configuración",
            },
        }

    def set_language(self, lang: str) -> None:
        self.language = lang

    def gettext(self, key: str) -> str:
        return self.translations.get(self.language, {}).get(key, key)

translator = Translator()
