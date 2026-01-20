from quart import Response


async def oauth_callback() -> Response:
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Finanze - Redirecting...</title>
  <style>
    :root {
      --background: #ffffff;
      --foreground: #0a0a0a;
      --card: #ffffff;
      --card-foreground: #0a0a0a;
      --muted-foreground: #737373;
      --border: #e5e5e5;
      --destructive: #ef4444;
      --primary: #0a0a0a;
      --primary-foreground: #ffffff;
      --radius: 0.75rem;
    }

    @media (prefers-color-scheme: dark) {
      :root {
        --background: #0a0a0a;
        --foreground: #fafafa;
        --card: #0a0a0a;
        --card-foreground: #fafafa;
        --muted-foreground: #a3a3a3;
        --border: #262626;
        --destructive: #dc2626;
        --primary: #ffffff;
        --primary-foreground: #0a0a0a;
      }
    }

    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      background-color: var(--background);
      color: var(--foreground);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
    }

    .card {
      background-color: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      width: 100%;
      max-width: 28rem;
      box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
    }

    .card-header {
      padding: 1.5rem 1.5rem 0;
    }

    .card-title {
      font-size: 1.25rem;
      font-weight: 600;
      line-height: 1.75rem;
      color: var(--card-foreground);
    }

    .card-content {
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .status-row {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .error-row {
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
    }

    .spinner {
      width: 1.25rem;
      height: 1.25rem;
      border: 2px solid var(--border);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      flex-shrink: 0;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .icon-error {
      width: 1.25rem;
      height: 1.25rem;
      color: var(--destructive);
      flex-shrink: 0;
      margin-top: 0.125rem;
    }

    .text-muted {
      font-size: 0.875rem;
      color: var(--muted-foreground);
      line-height: 1.5;
    }

    .error-details {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }

    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0.625rem 1rem;
      font-size: 0.875rem;
      font-weight: 500;
      border-radius: calc(var(--radius) - 2px);
      border: none;
      cursor: pointer;
      transition: opacity 0.15s, background-color 0.15s;
      width: 100%;
      background-color: var(--primary);
      color: var(--primary-foreground);
    }

    .button:hover {
      opacity: 0.9;
    }

    .button:focus-visible {
      outline: 2px solid var(--primary);
      outline-offset: 2px;
    }

    .hidden {
      display: none !important;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="card-header">
      <h1 class="card-title" id="title">Redirecting to Finanze...</h1>
    </div>
    <div class="card-content">
      <div id="loading-state" class="status-row">
        <div class="spinner"></div>
        <p class="text-muted">Opening the Finanze app...</p>
      </div>

      <div id="error-state" class="error-row hidden">
        <svg class="icon-error" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <div class="error-details">
          <p class="text-muted">Authentication failed. Please try again.</p>
          <p id="error-message" class="text-muted"></p>
        </div>
      </div>

      <button id="open-app-btn" class="button hidden" type="button">
        Open Finanze
      </button>

      <p class="text-muted">You can close this tab after the app opens.</p>
    </div>
  </div>

  <script>
    (function() {
      var DEEP_LINK_PROTOCOL = 'finanze://auth/callback';

      function getQueryParams() {
        var search = window.location.search;
        return new URLSearchParams(search);
      }

      function buildDeepLink() {
        var queryString = window.location.search;
        return DEEP_LINK_PROTOCOL + queryString;
      }

      function parseError(params) {
        var error = params.get('error');
        if (!error) return null;

        var description = params.get('error_description');
        if (description) {
          description = decodeURIComponent(description.replace(/\+/g, ' '));
        }

        return {
          error: error,
          description: description,
          code: params.get('error_code')
        };
      }

      function showError(errorInfo) {
        document.getElementById('title').textContent = 'Authentication Error';
        document.getElementById('loading-state').classList.add('hidden');
        document.getElementById('error-state').classList.remove('hidden');

        if (errorInfo.description) {
          document.getElementById('error-message').textContent = errorInfo.description;
        } else if (errorInfo.code) {
          document.getElementById('error-message').textContent = 'Error code: ' + errorInfo.code;
        }
      }

      function triggerDeepLink() {
        var deepLink = buildDeepLink();
        window.location.href = deepLink;
      }

      function showManualButton() {
        var btn = document.getElementById('open-app-btn');
        btn.classList.remove('hidden');
        btn.addEventListener('click', triggerDeepLink);
      }

      function init() {
        var params = getQueryParams();
        var errorInfo = parseError(params);

        if (errorInfo) {
          showError(errorInfo);
        }

        triggerDeepLink();

        setTimeout(showManualButton, 2000);
      }

      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
      } else {
        init();
      }
    })();
  </script>
</body>
</html>
"""

    return Response(html_content, mimetype="text/html")
