from drf_spectacular.extensions import OpenApiAuthenticationExtension


class AdminSessionScheme(OpenApiAuthenticationExtension):
    target_class = "apps.admin_dashboard.authentication.AdminSessionAuthentication"
    name = "AdminSession"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "header", "name": "Authorization",
                "description": "Separate admin session token using the AdminBearer authorization scheme."}
