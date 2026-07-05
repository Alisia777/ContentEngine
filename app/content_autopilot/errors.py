class ContentAutopilotError(Exception):
    pass


class ContentAutopilotDataError(ContentAutopilotError):
    pass


class ContentAutopilotSafetyError(ContentAutopilotError):
    pass
