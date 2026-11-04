class DropiAPIError(Exception):
    """Raised when the Dropi API returns isSuccess=False or an HTTP error."""

    def __init__(self, message="Error en la API de Dropi", status_code=None):
        self.status_code = status_code
        super().__init__(message)
