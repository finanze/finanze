from domain.external_integration import ForwardIntegrationOAuthCallbackRequest
from domain.use_cases.forward_integration_oauth_callback import (
    ForwardIntegrationOAuthCallback,
)
from quart import Response, redirect, request

EXPIRED_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Finanze</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      background: #ffffff;
      color: #0a0a0a;
      min-height: 100vh;
      margin: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
      box-sizing: border-box;
    }
    @media (prefers-color-scheme: dark) {
      body { background: #0a0a0a; color: #fafafa; }
      p { color: #a3a3a3; }
    }
    main { max-width: 28rem; }
    h1 { font-size: 1.25rem; font-weight: 600; margin: 0 0 0.75rem; }
    p { color: #737373; line-height: 1.5; margin: 0; }
  </style>
</head>
<body>
  <main>
    <h1>This sign-in can't be completed</h1>
    <p>The sign-in expired or was already used. Go back to Finanze and try again.</p>
  </main>
</body>
</html>
"""


def _arg(name: str):
    value = request.args.get(name)
    return value or None


async def forward_integration_oauth_callback(
    forward_integration_oauth_callback_uc: ForwardIntegrationOAuthCallback,
):
    state = _arg("state")
    destination = None
    if state:
        destination = await forward_integration_oauth_callback_uc.execute(
            ForwardIntegrationOAuthCallbackRequest(
                state=state,
                code=_arg("code"),
                error=_arg("error"),
                client_id=_arg("client_id"),
            )
        )

    if not destination:
        return Response(EXPIRED_PAGE, status=400, mimetype="text/html")

    response = redirect(destination, code=302)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
