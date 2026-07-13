class TeamError(Exception):
    code = "team_error"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.code)


class TeamPermissionError(TeamError):
    code = "team_permission_denied"


class TeamValidationError(TeamError):
    code = "team_validation_failed"


class TeamStateError(TeamError):
    code = "team_state_conflict"


class SupabaseAdminError(TeamError):
    code = "supabase_admin_error"
