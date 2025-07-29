class Translator:
    def __init__(self) -> None:
        self.language = "en"
        self.translations = {"en": {}}

    def set_language(self, lang: str) -> None:
        self.language = lang

    def gettext(self, key: str) -> str:
        return self.translations.get(self.language, {}).get(key, key)

translator = Translator()
